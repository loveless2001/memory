import unittest
from experiments.context_policy.reader_state_protocol import parse_events, resolve, record_for_question, state_messages


class ReaderStateTest(unittest.TestCase):
    def test_withdrawal_is_unknown_and_reinstatement_restores_same_value(self):
        history = [{'role': 'user', 'content': s} for s in
                   ('I prefer tea.', 'Forget my drink preference.', 'I again prefer tea.')]
        import json
        events = [[0,'user','set','tea',history[0]['content']],
                  [1,'user','withdraw',None,history[1]['content']],
                  [2,'user','set','tea',history[2]['content']]]
        parsed = parse_events(json.dumps({'events': events}), history)
        self.assertTrue(parsed['valid'])
        withdrawn = resolve(parsed['events'][:2], 'drink preference')
        self.assertEqual((withdrawn['status'],withdrawn['value'],withdrawn['polarity']), ('unknown',None,None))
        restored = resolve(parsed['events'], 'drink preference')
        self.assertEqual((restored['status'],restored['value'],restored['support_turns']), ('known','tea',[2]))

    def test_other_owner_cannot_overwrite_user_and_assistant_is_rejected(self):
        history = [{'role':'user','content':'I prefer tea.'},
                   {'role':'user','content':'Mira says, "I prefer coffee."'},
                   {'role':'assistant','content':'You prefer coffee.'}]
        import json
        events = [[0,'user','set','tea',history[0]['content']], [1,'other','set','coffee',history[1]['content']]]
        parsed = parse_events(json.dumps({'events':events}),history)
        self.assertEqual(resolve(parsed['events'],'drink')['value'],'tea')
        events.append([2,'user','set','coffee',history[2]['content']])
        self.assertFalse(parse_events(json.dumps({'events':events}),history)['valid'])

    def test_negative_none_and_unknown_are_three_distinct_states(self):
        import json
        history = [{'role':'user','content':'I do not enjoy running.'},
                   {'role':'user','content':'I have no exercise preference.'}]
        negative = parse_events(json.dumps({'events':[[0,'user','deny','running',history[0]['content']]]}),history)
        none = parse_events(json.dumps({'events':[[1,'user','no_preference',None,history[1]['content']]]}),history)
        states = [resolve(negative['events'],'exercise'),resolve(none['events'],'exercise'),resolve([],'exercise')]
        self.assertEqual([(s['status'],s['polarity']) for s in states], [('known','negative'),('known','none'),('unknown',None)])

    def test_invalid_json_source_and_chronology_fail_closed(self):
        import json
        history = [{'role':'user','content':'I prefer tea.'},{'role':'user','content':'Forget tea.'}]
        variants = ['{"events":[],"events":[]}', '```json\n{"events":[]}\n```',
            json.dumps({'events':[[0,'user','set','coffee','I prefer tea.']]}),
            json.dumps({'events':[[1,'user','withdraw',None,'Forget tea.'],[0,'user','set','tea','I prefer tea.']]}),
            json.dumps({'events':[[False,'user','set','tea','I prefer tea.']]}),
            json.dumps({'events':[[0,'user','set','tea','I like tea.']]})]
        for text in variants:
            parsed = parse_events(text,history)
            self.assertFalse(parsed['valid'],text)
            self.assertEqual(resolve(parsed['events'],'drink')['status'],'unknown')

    def test_current_record_hides_old_value_but_historical_scope_retains_source(self):
        import json
        history = [{'role':'user','content':'I prefer tea.'},{'role':'user','content':'Forget that preference.'}]
        parsed = parse_events(json.dumps({'events':[[0,'user','set','tea',history[0]['content']],
                    [1,'user','withdraw',None,history[1]['content']]]}),history)
        state = resolve(parsed['events'],'drink preference')
        current = record_for_question(state,history,{'scope':'current'})
        self.assertNotIn('tea',json.dumps(current))
        historical = record_for_question(state,history,{'scope':'historical','target_turn':0,'property':'drink preference'})
        self.assertEqual(historical['original_passage']['quote'],'I prefer tea.')
        self.assertNotIn('tea',state_messages(current,'What is my preference?')[1]['content'])


if __name__ == '__main__': unittest.main()

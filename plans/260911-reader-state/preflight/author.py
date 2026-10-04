"""Author regression annotations and twelve varied new histories before inference."""
import copy
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PARENT = ROOT / 'plans/260911-reader-repair/preflight'


def msg(role, content): return {'role': role, 'content': content}


def make_cases():
    cases = copy.deepcopy(json.loads((PARENT / 'cases.json').read_text()))
    properties = {'D01': 'enjoyment of urban sketching', 'D02': 'enjoyment of amateur astronomy',
                  'D03': 'preferred breakfast fruit', 'D04': 'preferred tea',
                  'F01': 'preferred weekend activity', 'F02': 'preferred evening activity',
                  'F03': 'preferred snack fruit', 'F04': 'preferred cold drink'}
    for c in cases:
        c['prior_split'] = c['split']; c['split'] = 'regression'
        c['scope'] = 'historical' if c['kind'] == 'historical' else 'current'
        c['target_turn'] = 0 if c['scope'] == 'historical' else None
        c['property'] = properties[c['family']]
        old = {'D01': 'urban sketching', 'D02': 'amateur astronomy'}.get(c['family'], c['reference']['old_value'])
        events = [[0, 'other' if c['kind'] == 'ownership' else 'user', 'set', old, c['history'][0]['content']]]
        if c['kind'] in ('withdrawal', 'different', 'same', 'historical'):
            events.append([2, 'user', 'withdraw', None, c['history'][2]['content']])
        if c['kind'] in ('different', 'same'):
            negative = c['kind'] == 'different' and c['family'] in ('D01', 'D02')
            value = old if c['kind'] == 'same' or negative else c['reference']['new_value']
            events.append([4, 'user', 'deny' if negative else 'set', value, c['history'][4]['content']])
        c['gold_events'] = {'events': events}

    def add(n, prop, kind, turns, events, questions, current, forbidden=()):
        history = [msg(role, text) for role, text in turns]
        raw = {'events': [[t, owner, op, value, history[t]['content']] for t, owner, op, value in events]}
        for qi, q in enumerate(questions):
            query, form, scope, answer, truth = q
            cases.append({'id': f'N{n:02d}-{qi+1}', 'family': f'N{n:02d}', 'kind': kind,
                'split': 'new', 'prior_split': None, 'question_form': form, 'topic_group': 'varied',
                'history': copy.deepcopy(history), 'query': query, 'property': prop, 'scope': scope,
                'target_turn': 0 if scope == 'historical' else None, 'gold_events': copy.deepcopy(raw),
                'reference': {'answer': answer, 'mode': 'historical' if scope == 'historical' else current[0],
                    'current_value': current[1], 'polarity': current[2], 'binary_truth': truth,
                    'forbidden_old_values': list(forbidden)}})

    add(1, 'preferred exercise', 'withdrawal_assistant_echo', [
        ('user', 'When I need exercise, my first choice is swimming.'),
        ('assistant', 'I will keep swimming in mind for exercise suggestions.'),
        ('user', 'Remove my exercise preference from the personal details you use about me.'),
        ('assistant', 'Understood; I have removed your preference for swimming.')],
        [(0,'user','set','swimming'),(2,'user','withdraw',None)], [
        ('Would it be accurate to say swimming is my preferred exercise now?','binary','current','My current exercise preference is unknown.',None),
        ('Which exercise is currently my first choice?','open','current','My current exercise preference is unknown.',None)],
        ('unknown',None,None), ['swimming'])

    add(2, 'enjoyment of trail running', 'explicit_negative', [
        ('user', 'I do not enjoy trail running. Please retain that as a current fact about me.'),
        ('assistant', 'Understood.')], [(0,'user','deny','trail running')], [
        ('Do I enjoy trail running?','binary','current','No. You explicitly do not enjoy trail running.',False),
        ('What have I told you about whether I enjoy trail running?','open','current','You do not enjoy trail running.',None)],
        ('known','trail running','negative'))

    add(3, 'preferred hot drink', 'selective_withdrawal', [
        ('user', 'My preferred hot drink is espresso. My usual writing tool is a mechanical pencil.'),
        ('assistant', 'Noted both details.'),
        ('user', 'Forget only the hot-drink preference. Keep the writing-tool detail.'),
        ('assistant', 'I will retain the writing-tool detail.')],
        [(0,'user','set','espresso'),(2,'user','withdraw',None)], [
        ('Do I currently prefer espresso over other hot drinks?','binary','current','Your current hot-drink preference is unknown.',None),
        ('What hot drink do I currently prefer?','open','current','Your current hot-drink preference is unknown.',None)],
        ('unknown',None,None), ['espresso'])

    add(4, 'preferred writing tool', 'unrelated_withdrawal', [
        ('user', 'For writing, I prefer a fountain pen. For breakfast, I prefer toast.'),
        ('assistant', 'Both preferences are noted.'),
        ('user', 'Please forget my breakfast preference; leave the writing-tool preference in place.'),
        ('assistant', 'The breakfast preference has been removed.')],
        [(0,'user','set','fountain pen')], [
        ('Do I currently prefer a fountain pen for writing?','binary','current','Yes. Your preferred writing tool is a fountain pen.',True),
        ('Which writing tool do I prefer?','open','current','A fountain pen.',None)],
        ('known','fountain pen','positive'))

    add(5, 'preferred laptop brand', 'quoted_then_personal', [
        ('user', 'Here is a fictional review by Mira: "My preferred laptop brand is Framework." Please fix its punctuation.'),
        ('assistant', 'The sentence is grammatically fine.'),
        ('user', 'For my own laptop purchases, my preferred brand is Lenovo.'),
        ('assistant', 'Noted your personal preference.')],
        [(0,'other','set','Framework'),(2,'user','set','Lenovo')], [
        ('Is Framework my preferred laptop brand?','binary','current','No. Your preferred laptop brand is Lenovo.',False),
        ('Which laptop brand do I personally prefer?','open','current','Lenovo.',None)],
        ('known','Lenovo','positive'))

    add(6, 'preferred music genre', 'quote_after_withdrawal', [
        ('user', 'The music genre I prefer is ambient.'),
        ('assistant', 'Understood.'),
        ('user', 'Forget my music-genre preference.'),
        ('assistant', 'I acknowledge that request.'),
        ('user', 'My friend Eli wrote, "The music genre I prefer is ambient." Could you shorten Eli\'s sentence?'),
        ('assistant', 'Eli prefers ambient music.')],
        [(0,'user','set','ambient'),(2,'user','withdraw',None),(4,'other','set','ambient')], [
        ('Is ambient my current preferred genre of music?','binary','current','Your current music-genre preference is unknown.',None),
        ('What genre of music do I currently prefer?','open','current','Your current music-genre preference is unknown.',None)],
        ('unknown',None,None), ['ambient'])

    add(7, 'usual bus route', 'same_reinstatement', [
        ('user', 'My usual bus route is 17.'),
        ('assistant', 'I have noted that.'),
        ('user', 'Please remove my usual bus route from your personal notes.'),
        ('assistant', 'Removed.'),
        ('user', 'I want to give you that detail again: my usual bus route is 17.'),
        ('assistant', 'Understood.')],
        [(0,'user','set','17'),(2,'user','withdraw',None),(4,'user','set','17')], [
        ('Is 17 my usual bus route now?','binary','current','Yes. Your usual bus route is 17.',True),
        ('Which bus route do I usually take?','open','current','Route 17.',None)],
        ('known','17','positive'))

    add(8, 'language currently studying', 'multiple_updates', [
        ('user', 'The language I am studying is Spanish.'),
        ('assistant', 'Understood.'),
        ('user', 'Forget which language I am studying.'),
        ('user', 'Here is a new current detail: the language I am studying is German.'),
        ('assistant', 'Noted.'),
        ('user', 'Remove that language-study detail again.'),
        ('user', 'For future answers, the language I am studying is Polish.')],
        [(0,'user','set','Spanish'),(2,'user','withdraw',None),(3,'user','set','German'),
         (5,'user','withdraw',None),(6,'user','set','Polish')], [
        ('Is German the language I am currently studying?','binary','current','No. You are currently studying Polish.',False),
        ('Which language am I studying at present?','open','current','Polish.',None)],
        ('known','Polish','positive'), ['Spanish','German'])

    add(9, 'pronunciation of my name', 'assistant_conflict', [
        ('user', 'My name is pronounced MAH-ree.'),
        ('assistant', 'I will pronounce your name MAY-ree.'),
        ('user', 'Please use the pronunciation I gave you, rather than your version.')],
        [(0,'user','set','MAH-ree')], [
        ('Is MAY-ree the pronunciation I supplied for my name?','binary','current','No. You supplied MAH-ree.',False),
        ('How should you pronounce my name based on what I told you?','open','current','MAH-ree.',None)],
        ('known','MAH-ree','positive'))

    add(10, 'preferred reading format', 'historical_scope', [
        ('user', 'For novels, I prefer paper books.'),
        ('assistant', 'Noted.'),
        ('user', 'Forget my preference about reading format.'),
        ('assistant', 'Understood.')],
        [(0,'user','set','paper books'),(2,'user','withdraw',None)], [
        ('Do I currently prefer paper books for novels?','binary','current','Your current reading-format preference is unknown.',None),
        ('What reading format did my first message say I preferred, before the withdrawal?','open','historical','Your original message said you preferred paper books for novels.',None)],
        ('unknown',None,None), ['paper books'])

    add(11, 'default coffee order', 'other_person_distractor', [
        ('user', 'My default coffee order is decaf.'),
        ('assistant', 'Got it.'),
        ('user', 'My coworker Sal says, "My default coffee order is regular." Help me reply politely to Sal.'),
        ('assistant', 'You could say: Thanks for letting me know, Sal.')],
        [(0,'user','set','decaf'),(2,'other','set','regular')], [
        ('Is regular my default coffee order?','binary','current','No. Your default coffee order is decaf.',False),
        ('What is my default coffee order?','open','current','Decaf.',None)],
        ('known','decaf','positive'))

    add(12, 'preferred dessert', 'explicit_no_preference', [
        ('user', 'I do not have a preferred dessert. This is an explicit personal fact, not a request to forget anything.'),
        ('assistant', 'Understood.')], [(0,'user','no_preference',None)], [
        ('Have I explicitly said that I have no preferred dessert?','binary','current','Yes. You explicitly said you have no preferred dessert.',True),
        ('What is my dessert preference?','open','current','You explicitly have no preferred dessert.',None)],
        ('known',None,'none'))

    assert len(cases) == 96
    return cases

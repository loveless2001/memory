"""Freeze a source-bound, manually annotated representation regression set."""
import json
from pathlib import Path
from transformers import AutoTokenizer
from experiments.context_policy.preflight import digest
from experiments.context_policy.personamem import sha256
from experiments.context_policy.relabel import canonical, draft_reference, evidence, validate_reference
from experiments.context_policy.grounded_notes import source_candidates, render_notes
from experiments.context_policy.memory_probe import validate_reused_notes
from experiments.context_policy.reader_regression import paired_views, validate_topics, reader_messages, append_evidence, answer_prefix_ids

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
OLD = OUT.parent / '20260910-v2-memory-dev'
TOPICS = {
 '150': (26, 'pen type'), '29': (132, 'clothing fabric'),
 '642': (64, 'blockchain/cryptocurrency interest'), '651': (60, 'jigsaw-puzzle enjoyment'),
 '746': (116, 'snowboarding enjoyment'), '750': (164, 'Nordic vacation preference'),
 '839': (104, 'AR-game enjoyment'), '945': (80, 'coffee-versus-tea preference'),
 '954': (48, 'aquarium-visit enjoyment'), '990': (150, 'reading format'),
}


def user(text): return {'role': 'user', 'content': text}
def assistant(text): return {'role': 'assistant', 'content': text}


SYNTHETIC = [
 ('s01', 'later_different_value', [user('I prefer coffee to tea.'), assistant('Understood.'),
   user('Please forget my preference for coffee over tea.'), assistant('Understood.'),
   user('My current drink preference is tea.'), assistant('Understood.')],
  [(2, 'beverage preference')], 'What is my current drink preference?', 'Your current preference is tea.',
  (4, 'My current drink preference is tea.'), 'user'),
 ('s02', 'later_same_value', [user('I prefer paper books over e-readers.'), assistant('Understood.'),
   user('Please forget my preference for paper books over e-readers.'), assistant('Understood.'),
   user('I have decided again: my current preference is paper books over e-readers.'), assistant('Understood.')],
  [(2, 'reading format')], 'Which reading format do I currently prefer?', 'You currently prefer paper books over e-readers.',
  (4, 'my current preference is paper books over e-readers'), 'user'),
 ('s03', 'assistant_cannot_restore', [user('I enjoy spicy food.'), assistant('Understood.'),
   user('Please forget that I enjoy spicy food.'), assistant('You enjoy spicy food, so spicy dishes should suit you.')],
  [(2, 'food spiciness preference')], 'What level of food spiciness do I prefer?',
  'Your current spiciness preference is unknown. What do you prefer now?', None, None),
 ('s04', 'unrelated_topic_survives', [user('My preferred writing instrument is a fountain pen.'), assistant('Understood.'),
   user('I prefer coffee to tea.'), assistant('Understood.'), user('Please forget my preference for coffee over tea.'), assistant('Understood.')],
  [(4, 'beverage preference')], 'What writing instrument do I prefer?', 'You prefer a fountain pen.',
  (0, 'My preferred writing instrument is a fountain pen.'), 'user'),
 ('s05', 'named_character_survives', [user('Please polish this fictional scene: Ari prefers coffee to tea.'),
   assistant('In the scene, Ari chooses coffee.'), user('My own drink preference is tea.'), assistant('Understood.'),
   user('Please forget my drink preference.'), assistant('Understood.')],
  [(4, 'user beverage preference')], 'In the fictional scene I supplied, which drink did Ari prefer?',
  'In the fictional scene, Ari preferred coffee.', (0, 'Ari prefers coffee to tea.'), 'quoted_text_only'),
 ('s06', 'draft_not_biography', [user('Please polish a fictional first-person monologue: "I prefer tea."'),
   assistant('Polished fictional monologue: "Tea is my preference."')], [],
  'Which drink do I personally prefer?', 'Your personal drink preference is not established by the fictional monologue.', None, None),
 ('s07', 'later_factual_update', [user('The planning meeting is on Tuesday.'), assistant('Understood.'),
   user('Please forget the meeting day I told you.'), assistant('Understood.'),
   user('The planning meeting is now on Thursday.'), assistant('Understood.')],
  [(2, 'planning meeting day')], 'On which day is the planning meeting now?', 'The planning meeting is now on Thursday.',
  (4, 'The planning meeting is now on Thursday.'), 'user'),
 ('s08', 'passage_attribution', [user('Please translate my Lantern Stage paragraph: I helped carry props and adjust lights backstage.'),
   assistant('The Lantern Stage passage describes backstage work.'),
   user('Please polish a different paragraph about River Hall: I helped actors run lines and set up chairs.'),
   assistant('At River Hall, I helped actors run lines and set up chairs.')], [],
  'Which two tasks appeared in my Lantern Stage paragraph?', 'Carrying props and adjusting lights.',
  (0, 'I helped carry props and adjust lights backstage.'), 'quoted_text_only'),
]


def main():
    import datetime
    if (OUT / 'freeze.json').exists(): raise RuntimeError('already frozen; create another explicit revision')
    old_reader = json.loads((OLD / 'reader-input.json').read_text())
    old_records = {x['id']: x for x in map(json.loads, (OLD / 'records.jsonl').read_text().splitlines())}
    old_refs = {x['id']: x for x in map(json.loads, (OLD / 'references.jsonl').read_text().splitlines())}
    old_notes = json.loads((OUT.parent / '20260910-v2-repair-r4/artifacts/notes.json').read_text())
    tokenizer = AutoTokenizer.from_pretrained('Qwen/Qwen3-4B-Instruct-2507',
        revision='cdbee75f17c01a7cc42f958dc650907174af0554', local_files_only=True)
    config = json.loads((ROOT / 'experiments/context_policy/design.json').read_text())
    histories = dict(old_reader['histories']); notes = dict(old_notes)
    topics = {pid: [dict(turn=t, topic=topic, source_sha256=digest(histories[pid][t]))] for pid, (t, topic) in TOPICS.items()}
    selected = [(f'memory-dev-v1-{pid}-4', 'existing_withdrawal', 1) for pid in TOPICS]
    selected += [('memory-dev-v1-150-3', 'retained_fact_control', 1),
                 ('memory-dev-v1-746-2', 'existing_wrong_passage', 1),
                 ('memory-dev-v1-150-5', 'missing_information_format', 0)]
    records = [old_records[rid] for rid, _, _ in selected]
    refs = [old_refs[rid] for rid, _, _ in selected]
    for pid, kind, history, topic_pairs, query, answer, span, ownership in SYNTHETIC:
        histories[pid] = history
        topics[pid] = [dict(turn=t, topic=topic, source_sha256=digest(history[t])) for t, topic in topic_pairs]
        (OUT / f'source-{pid}.json').write_bytes(canonical(history))
        record = dict(id=f'withdrawal-regression-v1-{pid}', persona_id=pid,
                      history_path=str((OUT / f'source-{pid}.json').relative_to(ROOT)),
                      source_sha256=sha256(canonical(history)), visible_history_sha256=sha256(canonical(history)),
                      history=history, query=user(query), query_sha256=sha256(canonical(user(query))))
        claims = [] if span is None else [dict(claim=answer, ownership=ownership, current_status='current',
                                              evidence=[evidence(history, *span)])]
        constraints = [dict(kind='withdrawal', rule='The topic becomes unknown at this turn; do not repeat its old value or infer the opposite. A later explicit user statement may establish a new value.',
                            evidence=[evidence(history, t, history[t]['content'])]) for t, _ in topic_pairs]
        if kind in ('named_character_survives', 'draft_not_biography', 'passage_attribution'):
            constraints.append(dict(kind='ownership', rule='Fictional or supplied text does not establish user biography. Match the specific requested original passage.', evidence=[evidence(history, 0, history[0]['content'])]))
        ref = draft_reference(record, answer, 'personalized' if claims else 'clarify', claims, constraints,
                              'Hand-authored source fixture; resolve chronology and ownership from user turns.')
        ref['semantic_review'].update(status='author_reviewed_independent_pending', reviewer='Codex, same author')
        quotes, ledger = source_candidates(tokenizer, history)
        text = render_notes(quotes, ledger)
        notes[pid] = dict(history_sha256=digest(history), selected=quotes, withdrawals=ledger, text=text,
                          tokens=len(tokenizer.encode(text, add_special_tokens=False)), semantic_review='author_reviewed')
        records.append(record); refs.append(ref); selected.append((record['id'], kind, 1))
    questions = [{k: r[k] for k in ('id', 'persona_id', 'query')} for r in records]
    reader = dict(histories=histories, questions=questions,
                  scope='21 development regression cases; source-bound topic annotations; 8 hand-authored fixtures, 13 unchanged earlier queries; no reference answers')
    validate_reused_notes(tokenizer, reader, notes)
    schedules, contexts = [], []
    max_input = 0
    for index, (record, ref, (rid, kind, rounds)) in enumerate(zip(records, refs, selected)):
        assert rid == record['id']; validate_reference(record, ref)
        pid = record['persona_id']; validate_topics(histories[pid], topics[pid])
        views = paired_views(tokenizer, histories[pid], notes[pid], topics[pid], record['query']['content'], config)
        order = ['raw', 'neutral'] if index % 2 == 0 else ['neutral', 'raw']
        schedules.append(dict(id=rid, kind=kind, retrieval_rounds=rounds, arm_order=order))
        for arm in order:
            view = views[arm]
            messages = reader_messages(view['notes'], view['recent'], record['query']['content'])
            if rounds: messages = append_evidence(messages, view['retrieval']['text'], record['query']['content'])
            tokens = len(answer_prefix_ids(tokenizer, messages)); max_input=max(max_input,tokens)
            assert tokens+192<=8192
            contexts.append(dict(id=rid, arm=arm, retrieval_rounds=rounds, messages=messages,
                                 input_tokens=tokens, view=view))
    for name, data in [('reader-input.json', reader), ('notes.json', notes), ('topics.json', topics),
                       ('schedule.json', schedules), ('expected-contexts.json', contexts)]:
        (OUT / name).write_bytes(canonical(data))
    for name, data in [('records.jsonl', records), ('references.jsonl', refs)]:
        (OUT / name).write_bytes(b''.join(canonical(x) for x in data))
    paths = [p for p in OUT.iterdir() if p.is_file()]
    paths += [ROOT / 'experiments/context_policy/reader_regression.py', ROOT / 'experiments/context_policy/design.json',
              OLD / 'freeze.json', OLD / 'reader-input.json', OLD / 'references.jsonl',
              OUT.parent / '20260910-v2-repair-r4/artifacts/notes.json']
    frozen = dict(version='withdrawal-regression-v1', created_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                  questions=21, captures=42, arms=['raw','neutral'], old_source_histories=10, synthetic_histories=8,
                  topic_annotations=sum(len(x) for x in topics.values()), max_input_tokens=max_input,
                  manual_topic_annotations=True, independent_review=False, training_allowed=False,
                  files={str(p.relative_to(ROOT)):sha256(p.read_bytes()) for p in paths})
    (OUT / 'freeze.json').write_bytes(canonical(frozen)); print(json.dumps({k:v for k,v in frozen.items() if k!='files'}))


if __name__ == '__main__': main()

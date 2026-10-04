"""Author and freeze paired source-exact reader inputs without model inference."""
import copy
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from transformers import AutoTokenizer
from experiments.context_policy.broader_protocol import reader_messages, source_span, render_spans, answer_prefix_ids
from experiments.context_policy.reader_repair import SYSTEMS

HERE = Path(__file__).resolve().parent
PARENT = ROOT / 'plans/260911-reader-diagnostic'
ARMS = ['baseline', 'repair']
KINDS = ('baseline', 'withdrawal', 'different', 'same', 'historical', 'ownership')
TOPICS = [
    ('F01', 'weekend activity', 'bouldering', 'kayaking', 'activity'),
    ('F02', 'evening activity', 'origami', 'chess', 'activity'),
    ('F03', 'snack fruit', 'mango', 'kiwi', 'food_drink'),
    ('F04', 'cold drink', 'lemonade', 'iced coffee', 'food_drink'),
]


def read(p): return json.loads(p.read_text())
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def write(name, value): (HERE / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
def msg(role, content): return {'role': role, 'content': content}


def render(history, query, arm):
    spans = [source_span(history, i, 0, len(m['content'])) for i, m in enumerate(history)]
    messages = reader_messages(render_spans(spans), '', query)
    messages[0] = msg('system', SYSTEMS[arm])
    return messages, spans


def make_cases():
    cases = copy.deepcopy(read(PARENT / 'preflight/cases.json'))
    for c in cases:
        c.update(split='development', question_form='original', topic_group='original')
    for family, topic, old, new, group in TOPICS:
        positive = f'My preferred {topic} is {old}.'
        different = f'My preferred {topic} is {new}.'
        original = [msg('user', positive), msg('assistant', 'Understood.')]
        withdrawn = original + [msg('user', 'Please forget this personal detail: ' + positive), msg('assistant', 'I acknowledge your request.')]
        for kind in KINDS:
            history = copy.deepcopy(original if kind == 'baseline' else withdrawn)
            state = old; evidence = [0]; mode = 'known'
            if kind == 'withdrawal': state = None; evidence = [2]; mode = 'unknown'
            if kind in ('different', 'same'):
                history += [msg('user', 'Here is my current personal detail for future replies: ' + (different if kind == 'different' else positive)), msg('assistant', 'Understood.')]
                state = new if kind == 'different' else old; evidence = [2, 4]
            if kind == 'historical': evidence = [0, 2]; mode = 'historical'
            if kind == 'ownership':
                history = [msg('user', 'Please copy-edit this fictional first-person line spoken by the character Vale: "' + positive + '"'), msg('assistant', 'This is a line attributed to the fictional character Vale.')]
                state = None; evidence = [0]; mode = 'unknown'
            for form in ('binary', 'open'):
                query = f'Is {old} my current preferred {topic}?' if form == 'binary' else f'What is my current preferred {topic}?'
                if kind == 'historical':
                    query = (f'Did my original first message say that my preferred {topic} was {old}, before I withdrew it?' if form == 'binary' else f'What {topic} did my original first message say I preferred, before I withdrew it?')
                    answer = ('Yes. ' if form == 'binary' else '') + 'The original message stated: ' + positive
                elif state is None: answer = 'The current user preference is unknown.'
                else: answer = (('Yes. ' if state == old else 'No. ') if form == 'binary' else '') + f'Your current preferred {topic} is {state}.'
                cases.append({'id': f'{family}-{kind}-{form}', 'family': family, 'kind': kind,
                    'split': 'fresh', 'question_form': form, 'topic_group': group,
                    'history': history, 'query': query, 'reference': {'answer': answer, 'mode': mode,
                        'evidence_turns': evidence, 'old_value': old, 'new_value': new if kind == 'different' else None,
                        'current_value': state if kind != 'historical' else None,
                        'binary_truth': (state == old) if state is not None and kind != 'historical' else (True if kind == 'historical' else None)}})
    return cases


def main():
    if (HERE / 'freeze.json').exists(): raise RuntimeError('Preflight is frozen')
    config = read(PARENT / 'preflight/runtime-config.json')
    config.update(planned_captures=144)
    tok = AutoTokenizer.from_pretrained(config['model_id'], revision=config['model_revision'], local_files_only=True)
    cases = make_cases(); inputs = []
    for c in cases:
        for arm in ARMS:
            messages, spans = render(c['history'], c['query'], arm)
            assert [s['turn'] for s in spans] == list(range(len(c['history'])))
            count = len(answer_prefix_ids(tok, messages)); assert count + 192 <= 8192
            inputs.append({'id': c['id'], 'arm': arm, 'messages': messages, 'input_tokens': count})
    inputs.sort(key=lambda r: (r['id'], hashlib.sha256((r['id'] + r['arm']).encode()).hexdigest()))
    gate = []
    for arm in ARMS:
        pool = sorted((i for i, r in enumerate(inputs) if r['arm'] == arm), key=lambda i: hashlib.sha256(('gate' + inputs[i]['id']).encode()).hexdigest())
        gate += pool[:20]
    assert len(gate) == len(set(gate)) == 40
    parent_inputs = {(r['id'], r['arm']): r for r in read(PARENT / 'preflight/inputs.json')}
    for row in inputs:
        if row['id'].startswith('D') and row['arm'] == 'baseline':
            assert row['messages'] == parent_inputs[row['id'], 'json_chronological']['messages']
    sources = read(PARENT / 'preflight/runtime-sources.json')
    sources.pop('experiments/context_policy/reader_diagnostic.py')
    sources['experiments/context_policy/reader_repair.py'] = None
    sources = {n: sha(ROOT / n) for n in sources}
    protected = {}
    for directory in ('plans/260910-context-policy', 'plans/260911-reader-diagnostic', 'experiments/context_policy', 'modal-runners'):
        for p in (ROOT / directory).rglob('*'):
            if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc' and p.name not in ('reader_repair.py', 'modal-reader-repair.py'):
                protected[str(p.relative_to(ROOT))] = sha(p)
    for name, value in [('cases.json', cases), ('inputs.json', inputs), ('runtime-config.json', config),
                        ('gate-indices.json', gate), ('runtime-sources.json', sources), ('protected.json', protected)]:
        write(name, value)
    write('cpu-checks.json', {'status': 'PASS', 'cases': len(cases), 'conditions': len(inputs),
        'splits': dict(Counter(c['split'] for c in cases)), 'gate_per_arm': 20,
        'max_input_tokens': max(r['input_tokens'] for r in inputs), 'protected_files': len(protected),
        'unchanged_previous_baseline_inputs': 24, 'reference_review': 'author-authored before generation'})
    frozen = [p for p in HERE.iterdir() if p.is_file()] + [ROOT / n for n in ('experiments/context_policy/reader_repair.py', 'modal-runners/modal-reader-repair.py')]
    write('freeze.json', {'files': {str(p.relative_to(ROOT)): sha(p) for p in frozen}, 'references_mounted': False})
    print((HERE / 'cpu-checks.json').read_text())


if __name__ == '__main__': main()

"""Read-only replay of frozen paired inputs and source/question crossing."""
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(HERE))
from prepare import read, sha, render, make_cases, ARMS, KINDS, TOPICS, PARENT
from transformers import AutoTokenizer
from experiments.context_policy.broader_protocol import answer_prefix_ids


def main():
    for n, h in read(HERE / 'freeze.json')['files'].items(): assert sha(ROOT / n) == h, n
    protected = read(HERE / 'protected.json')
    for n, h in protected.items(): assert sha(ROOT / n) == h, n
    cases = read(HERE / 'cases.json'); inputs = read(HERE / 'inputs.json')
    assert cases == make_cases() and len(cases) == 72 and len(inputs) == 144
    assert Counter(c['split'] for c in cases) == {'development': 24, 'fresh': 48}
    index = {c['id']: c for c in cases}; assert len(index) == 72
    for family, *_ in TOPICS:
        for kind in KINDS:
            a, b = [index[f'{family}-{kind}-{f}'] for f in ('binary', 'open')]
            assert a['history'] == b['history'] and a['query'] != b['query']
            assert a['reference']['current_value'] == b['reference']['current_value']
    config = read(HERE / 'runtime-config.json')
    tok = AutoTokenizer.from_pretrained(config['model_id'], revision=config['model_revision'], local_files_only=True)
    seen = set()
    for r in inputs:
        assert set(r) == {'id', 'arm', 'messages', 'input_tokens'}
        key = r['id'], r['arm']; assert key not in seen; seen.add(key)
        case = index[r['id']]; messages, spans = render(case['history'], case['query'], r['arm'])
        assert r['messages'] == messages and r['input_tokens'] == len(answer_prefix_ids(tok, messages))
        assert r['input_tokens'] + 192 <= 8192
        assert [s['turn'] for s in spans] == list(range(len(case['history'])))
    assert Counter(r['arm'] for r in inputs) == {a: 72 for a in ARMS}
    for cid in index:
        pair = [r for r in inputs if r['id'] == cid]
        assert pair[0]['messages'][1:] == pair[1]['messages'][1:]
    gate = read(HERE / 'gate-indices.json'); assert len(gate) == len(set(gate)) == 40
    assert Counter(inputs[i]['arm'] for i in gate) == {a: 20 for a in ARMS}
    old = {r['id']: r for r in read(PARENT / 'preflight/inputs.json') if r['arm'] == 'json_chronological'}
    assert all(r['messages'] == old[r['id']]['messages'] for r in inputs if r['arm'] == 'baseline' and r['id'] in old)
    print(json.dumps({'status': 'PASS', 'cases': 72, 'conditions': 144,
        'fresh_source_pairs': 24, 'only_system_differs_between_arms': True,
        'cache_fixtures': 40, 'protected_files': len(protected), 'training_labels': 0}))


if __name__ == '__main__': main()

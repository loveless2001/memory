"""Validate author decisions and replay every prospective paired comparison."""
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIELDS = ('task_complete', 'source_consistent', 'supported_in_visible_state',
          'withdrawal_compliant', 'ownership_correct', 'body_valid', 'within_90_words')


def read(p): return json.loads(p.read_text())
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()


def summarize():
    artifact = read(HERE / 'combined/artifact-verification.json')
    assert artifact['status'] == 'PASS' and artifact['complete']
    captures = read(HERE / 'combined/captures.json')
    cases = {c['id']: c for c in read(HERE / 'preflight/cases.json')}
    review = read(HERE / 'review.json')
    assert review['captures_sha256'] == sha(HERE / 'combined/captures.json')
    assert review['cases_sha256'] == sha(HERE / 'preflight/cases.json')
    assert review['reviewer'] and review['model_version'] and review['process_notes']
    assert len(review['answers']) == len(captures) == 144
    counts = defaultdict(lambda: defaultdict(Counter))
    classes = defaultdict(lambda: defaultdict(lambda: defaultdict(Counter)))
    forms = defaultdict(lambda: defaultdict(Counter))
    topics = defaultdict(lambda: defaultdict(lambda: defaultdict(Counter)))
    criteria = defaultdict(lambda: defaultdict(lambda: defaultdict(Counter)))
    fresh_cells = defaultdict(lambda: defaultdict(lambda: defaultdict(Counter)))
    states = {}; task_states = {}
    for capture, judgment in zip(captures, review['answers']):
        key = capture['id'], capture['arm']
        assert key == (judgment['id'], judgment['arm']) and key not in states
        assert all(judgment[k] is None or type(judgment[k]) is bool for k in FIELDS)
        assert judgment['body_valid'] == capture['body_structurally_valid']
        assert judgment['within_90_words'] == capture['within_90_words']
        verdict = judgment['verdict']
        assert verdict in ('pass', 'fail', 'ambiguous') and judgment['reason'] and judgment['evidence']
        expected = 'fail' if any(judgment[k] is False for k in FIELDS) else ('ambiguous' if any(judgment[k] is None for k in FIELDS) else 'pass')
        assert verdict == expected
        case = cases[capture['id']]
        for e in judgment['evidence']:
            assert set(e) == {'where', 'index', 'quote'} and type(e['index']) is int and e['quote']
            if e['where'] == 'history': rows = case['history']
            elif e['where'] == 'reader_message': rows = capture['messages']
            elif e['where'] == 'answer': rows = [{'content': capture['text']}]
            else: raise ValueError('Invalid evidence location')
            assert 0 <= e['index'] < len(rows) and e['quote'] in rows[e['index']]['content']
        split, arm, kind = case['split'], capture['arm'], case['kind']
        counts[split][arm][verdict] += 1
        classes[split][kind][arm][verdict] += 1
        for field in FIELDS: criteria[split][arm][field][str(judgment[field]).lower()] += 1
        if split == 'fresh':
            form = case['question_form']; topic = case['topic_group']
            forms[form][arm][verdict] += 1
            topics[topic][form][arm][verdict] += 1
            fresh_cells[kind][form][arm][verdict] += 1
        states[key] = verdict; task_states[key] = judgment['task_complete']
    effects = {}
    for split in ('development', 'fresh'):
        ids = [cid for cid, c in cases.items() if c['split'] == split]
        transitions = Counter(states[cid, 'baseline'] + ' -> ' + states[cid, 'repair'] for cid in ids)
        fixes = sum(states[cid, 'baseline'] != 'pass' and states[cid, 'repair'] == 'pass' for cid in ids)
        regressions = sum(states[cid, 'baseline'] == 'pass' and states[cid, 'repair'] != 'pass' for cid in ids)
        effects[split] = {'transitions': transitions, 'strict_corrections': fixes, 'strict_regressions': regressions,
            'task_corrections': sum(task_states[cid, 'baseline'] is not True and task_states[cid, 'repair'] is True for cid in ids),
            'task_regressions': sum(task_states[cid, 'baseline'] is True and task_states[cid, 'repair'] is not True for cid in ids)}
    gates = {'development_24_of_24': counts['development']['repair']['pass'] == 24,
             'fresh_48_of_48': counts['fresh']['repair']['pass'] == 48}
    gates['both_pass'] = all(gates.values())
    return {'status': 'review_validated', 'captures': 144, 'cases': 72, 'author_review_only': True,
        'counts_by_split_and_arm': counts, 'counts_by_split_class_arm': classes,
        'fresh_counts_by_form_arm': forms, 'fresh_counts_by_topic_form_arm': topics,
        'fresh_counts_by_class_form_arm': fresh_cells, 'criterion_counts_by_split_arm': criteria,
        'paired_effects': effects, 'gates': gates, 'training_admission': False, 'training_labels': 0,
        'source_hashes': {'captures.json': sha(HERE / 'combined/captures.json'),
            'cases.json': sha(HERE / 'preflight/cases.json'), 'review.json': sha(HERE / 'review.json'),
            'preflight-freeze.json': sha(HERE / 'preflight/freeze.json')}}


def main():
    summary = summarize()
    if (HERE / 'result-manifest.json').exists():
        assert read(HERE / 'summary.json') == summary
    else:
        (HERE / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__': main()

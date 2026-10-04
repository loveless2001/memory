"""Prepare a source-bound answer review after terminal artifact verification."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
OUT = BASE / '20260911-v2-broader-answer-review'
PREP = BASE / '20260911-v2-broader-reader-preflight'
REFS = BASE / '20260910-v2-broader-eval-v2'
CRITERIA = ('task_complete', 'source_consistent', 'supported_in_visible_state',
            'withdrawal_compliant', 'ownership_correct', 'body_valid', 'within_90_words')
CAPTURE_FIELDS = ('text', 'token_ids', 'ended_at_eos', 'collection_mode', 'supplied_prefix',
                  'body_structurally_valid', 'word_count_whitespace', 'within_90_words',
                  'extra_action_markers', 'input_tokens', 'fresh_prefill')


def read(p):
    return json.loads(p.read_text())


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def write(p, x):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(x, ensure_ascii=False, indent=2) + '\n')


def opaque_order(items, domain):
    return sorted(items, key=lambda s: hashlib.sha256((domain + s).encode()).hexdigest())


def main():
    verified = read(HERE / 'artifact-verification.json')
    assert verified['status'] == 'PASS'
    captures = read(HERE / 'captures.json')
    assert len(captures) == verified['captures_verified'] and captures
    # Independently bind the consumed files again; do not trust a stale PASS.
    for name, expected in read(HERE / 'artifact-hashes.json').items():
        assert sha(HERE / name) == expected, name
    launch = read(HERE / 'launch.json')
    for name, expected in launch['input_hashes'].items():
        assert sha(PREP / name) == expected, name
    acceptance_path = BASE / '20260911-v2-broader-eval-acceptance/acceptance.json'
    acceptance = read(acceptance_path)
    repo = HERE.parents[2]
    for name, expected in acceptance['artifact_hashes'].items():
        assert sha(repo / name) == expected, name
    for name, expected in read(REFS / 'freeze.json')['files'].items():
        assert sha(repo / name) == expected, name
    coverage = {r['id']: r for r in acceptance['case_review_coverage']}
    assert len(coverage) == 120
    bundle = read(PREP / 'reader-input.json')
    questions = {q['id']: q for q in bundle['questions']}
    refs = {r['id']: r for r in map(json.loads, (REFS / 'references.jsonl').read_text().splitlines())}
    grouped = {}
    for n, c in enumerate(captures):
        grouped.setdefault(c['id'], []).append((n, c))
    assert not (OUT / 'packet-manifest.json').exists(), 'Never overwrite a frozen review packet'
    OUT.mkdir(exist_ok=True)
    hmap = {h: f'H{i:03d}' for i, h in enumerate(opaque_order(bundle['histories'], 'history'), 1)}
    for hid, anon in hmap.items():
        write(OUT / f'packet/histories/{anon}.json', {'history_id': anon,
            'turns': [{'turn': i, **m} for i, m in enumerate(bundle['histories'][hid])]})
    index, sealed, template = [], [], []
    for i, qid in enumerate(opaque_order(grouped, 'case'), 1):
        cid = f'C{i:03d}'; q = questions[qid]; ref = refs[qid]
        hid = hmap[q['persona_id']]
        answers, mappings, judgments = [], [], []
        by_key = {str(c['retrieval_rounds']): (n, c) for n, c in grouped[qid]}
        for j, k in enumerate(opaque_order(by_key, qid + '-answer')):
            n, c = by_key[k]; aid = cid + '-' + chr(65 + j)
            answers.append({'answer_id': aid, 'actual_messages': c['messages'],
                            **{f: c[f] for f in CAPTURE_FIELDS}})
            mappings.append({'answer_id': aid, 'capture_index': n, 'retrieval_rounds': c['retrieval_rounds']})
            judgments.append({'answer_id': aid, 'verdict': None, **dict.fromkeys(CRITERIA),
                              'reason': '', 'evidence': []})
        case = {'case_id': cid, 'history_file': f'histories/{hid}.json', 'query': q['query'],
                'reviewed_reference': {k: ref[k] for k in ('answer', 'constraints', 'personal_claims')},
                'answers': answers}
        write(OUT / f'packet/cases/{cid}.json', case)
        index.append({'case_id': cid, 'file': f'cases/{cid}.json', 'answer_ids': [a['answer_id'] for a in answers]})
        sealed.append({'case_id': cid, 'original_id': qid, 'original_history_id': q['persona_id'],
                       'history_id': hid, 'reference_review_coverage': coverage[qid], 'answers': mappings})
        template.append({'case_id': cid, 'reference_issue_if_any': None, 'answers': judgments})
    write(OUT / 'packet/index.json', index)
    write(OUT / 'sealed-map.json', sealed)
    write(OUT / 'review-template.json', {'reviewer': '', 'model_version': '', 'reviewed_at': '',
        'blinding_notes': '', 'process_notes': '', 'status': 'partial', 'cases': template})
    bound = [HERE / n for n in ('launch.json', 'status.json', 'captures.json', 'artifact-hashes.json', 'artifact-verification.json')]
    bound += [PREP / 'reader-input.json', REFS / 'references.jsonl', REFS / 'freeze.json', acceptance_path]
    bound += [repo / 'CLAUDE-BROADER-ANSWERS.md', HERE / 'prepare_review.py']
    files = {str(p.relative_to(OUT)): sha(p) for p in OUT.rglob('*.json')}
    files['validate.py'] = sha(OUT / 'validate.py')
    write(OUT / 'packet-manifest.json', {'schema': 'broader-answer-review-v1',
        'cases': len(index), 'answers': len(captures), 'histories': len(hmap),
        'planned_answers': 360, 'missing_answers': 360 - len(captures),
        'planned_questions': 120, 'complete_three_view_questions': sum(len(v) == 3 for v in grouped.values()),
        'collection_complete': verified['collection_complete'],
        'coverage_caveat': 'Any partial collection is a prefix of the fixed family/question schedule, not a random sample.',
        'files': files, 'source_files': {str(p.relative_to(repo)): sha(p) for p in bound},
        'semantic_judgments_included': False, 'reference_coverage': {'delta_accepts': 12, 'inherited_accepts': 108},
        'blinding': 'Case and condition labels masked; actual messages reveal evidence depth. References visible.'})
    print(json.dumps({'packet': str(OUT), 'cases': len(index), 'answers': len(captures)}))


if __name__ == '__main__':
    main()

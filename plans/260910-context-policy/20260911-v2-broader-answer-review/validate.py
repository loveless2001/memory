"""Check packet provenance and reviewer structure/quotes, never semantic truth."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
CRITERIA = ('task_complete', 'source_consistent', 'supported_in_visible_state',
            'withdrawal_compliant', 'ownership_correct', 'body_valid', 'within_90_words')
CAPTURE_FIELDS = ('text', 'token_ids', 'ended_at_eos', 'collection_mode', 'supplied_prefix',
                  'body_structurally_valid', 'word_count_whitespace', 'within_90_words',
                  'extra_action_markers', 'input_tokens', 'fresh_prefill')


def read(p):
    return json.loads(p.read_text())


def require(ok, why):
    if not ok:
        raise ValueError(why)


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def safe(base, name):
    p = Path(name)
    require(not p.is_absolute() and '..' not in p.parts, 'unsafe path')
    return base / p


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--review', type=Path)
    args = parser.parse_args()
    manifest = read(HERE / 'packet-manifest.json')
    for name, expected in manifest['files'].items():
        require(sha(safe(HERE, name)) == expected, 'packet hash mismatch: ' + name)
    for name, expected in manifest['source_files'].items():
        require(sha(safe(ROOT, name)) == expected, 'source hash mismatch: ' + name)
    # Read bindings internally without printing labels or results to the reviewer.
    run = HERE.with_name('20260911-v2-broader-reader')
    prep = HERE.with_name('20260911-v2-broader-reader-preflight')
    refs_dir = HERE.with_name('20260910-v2-broader-eval-v2')
    captures = read(run / 'captures.json')
    bundle = read(prep / 'reader-input.json')
    questions = {q['id']: q for q in bundle['questions']}
    refs = {r['id']: r for r in map(json.loads, (refs_dir / 'references.jsonl').read_text().splitlines())}
    mapping = {x['case_id']: x for x in read(HERE / 'sealed-map.json')}
    index = read(HERE / 'packet/index.json')
    require(len(index) == manifest['cases'] == len(mapping), 'case coverage mismatch')
    cases, visited = {}, []
    for item in index:
        cid = item['case_id']; case = read(safe(HERE / 'packet', item['file'])); m = mapping[cid]
        require(cid not in cases and case['case_id'] == cid, 'duplicate/mismatched case')
        q = questions[m['original_id']]; r = refs[m['original_id']]
        require(case['query'] == q['query'], 'question changed')
        require(case['reviewed_reference'] == {k: r[k] for k in ('answer', 'constraints', 'personal_claims')}, 'reference changed')
        history = read(safe(HERE / 'packet', case['history_file']))
        require(history['history_id'] == m['history_id'], 'history ID mismatch')
        require(history['turns'] == [{'turn': i, **t} for i, t in enumerate(bundle['histories'][q['persona_id']])], 'source turns changed')
        am = {x['answer_id']: x for x in m['answers']}
        require([a['answer_id'] for a in case['answers']] == item['answer_ids'], 'answer order changed')
        require(set(am) == set(item['answer_ids']), 'answer map coverage changed')
        for answer in case['answers']:
            a = am[answer['answer_id']]; c = captures[a['capture_index']]
            require(c['id'] == m['original_id'] and c['retrieval_rounds'] == a['retrieval_rounds'], 'capture mapping changed')
            require(answer['actual_messages'] == c['messages'], 'actual messages changed')
            require(all(answer[k] == c[k] for k in CAPTURE_FIELDS), 'captured output changed')
            visited.append(a['capture_index'])
        cases[cid] = (case, history)
    require(sorted(visited) == list(range(len(captures))), 'omitted/duplicated capture')
    require(len(captures) == manifest['answers'], 'answer count mismatch')
    result = {'status': 'PASS', 'cases': len(cases), 'answers': len(visited),
              'collection_complete': manifest['collection_complete'], 'semantic_truth_certified': False}
    if args.review:
        review = read(args.review)
        for field in ('reviewer', 'model_version', 'reviewed_at', 'blinding_notes', 'process_notes'):
            require(isinstance(review.get(field), str) and review[field].strip(), 'missing reviewer provenance: ' + field)
        require(review['status'] in ('partial', 'complete'), 'invalid review status')
        require([r['case_id'] for r in review['cases']] == [i['case_id'] for i in index], 'review case coverage/order mismatch')
        counts = Counter()
        for row in review['cases']:
            case, history = cases[row['case_id']]
            answers = {a['answer_id']: a for a in case['answers']}
            require([a['answer_id'] for a in row['answers']] == list(answers), 'review answer coverage/order mismatch')
            issue = row.get('reference_issue_if_any')
            require(issue is None or isinstance(issue, str) and issue.strip(), 'reference issue must be text or null')
            for judgment in row['answers']:
                aid = judgment['answer_id']; answer = answers[aid]; v = judgment['verdict']
                require(v in (None, 'pass', 'fail', 'ambiguous', 'insufficient_source'), 'invalid verdict')
                require(all(judgment[k] is None or type(judgment[k]) is bool for k in CRITERIA), 'criteria must be booleans/null')
                if v is None:
                    require(review['status'] == 'partial', 'unreviewed answer in complete review')
                    counts['unreviewed'] += 1
                    continue
                require(isinstance(judgment['reason'], str) and judgment['reason'].strip(), 'missing reason')
                require(judgment['body_valid'] == answer['body_structurally_valid'], 'body criterion disagrees with capture')
                require(judgment['within_90_words'] == answer['within_90_words'], 'word criterion disagrees with capture')
                if v == 'pass':
                    require(all(judgment[k] is True for k in CRITERIA), 'pass with unresolved/failed criterion')
                if v == 'fail':
                    require(any(judgment[k] is False for k in CRITERIA), 'fail without failed criterion')
                require(isinstance(judgment['evidence'], list) and judgment['evidence'], 'missing evidence')
                for e in judgment['evidence']:
                    require(set(e) == {'where', 'index', 'quote'} and type(e['index']) is int, 'evidence schema')
                    require(isinstance(e['quote'], str) and e['quote'], 'empty evidence quote')
                    if e['where'] == 'history':
                        rows = history['turns']
                    elif e['where'] == 'reader_message':
                        rows = answer['actual_messages']
                    elif e['where'] == 'answer':
                        rows = [{'content': answer['text']}]
                    else:
                        raise ValueError('unknown evidence location')
                    require(0 <= e['index'] < len(rows), 'evidence index outside source')
                    require(e['quote'] in rows[e['index']]['content'], 'evidence quote is not exact')
                counts[v] += 1
        result.update(review_status=review['status'], verdict_counts=dict(counts))
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()

"""Validate audit bindings and optional separately authored review corrections."""
import argparse
import copy
import hashlib
import json
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PACKET = HERE.with_name('20260911-v2-broader-answer-review')


def read(p):
    return json.loads(p.read_text())


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def require(ok, why):
    if not ok:
        raise ValueError(why)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--corrections', type=Path)
    parser.add_argument('--write-merged', type=Path)
    args = parser.parse_args()
    require(not args.write_merged or args.corrections, 'corrections required')
    for name, expected in read(HERE / 'freeze.json')['files'].items():
        p = Path(name)
        require(not p.is_absolute() and '..' not in p.parts, 'unsafe frozen path')
        require(sha(ROOT / p) == expected, 'audit/source file changed: ' + name)
    audit = read(HERE / 'audit.json')
    for name, expected in audit['source_hashes'].items():
        require(sha(ROOT / name) == expected, 'review source changed: ' + name)
    checked = subprocess.run([sys.executable, str(PACKET / 'validate.py'), '--review',
        str(PACKET / 'claude-review/review.json')], capture_output=True, text=True, check=True)
    result = {'status': 'PASS', 'parent_review': json.loads(checked.stdout),
              'target_answers': len(audit['target_answers']), 'semantic_reconciliation': 'pending'}
    if args.corrections:
        correction = read(args.corrections)
        require(correction['parent_review_sha256'] == sha(PACKET / 'claude-review/review.json'), 'parent hash mismatch')
        require(correction['audit_sha256'] == sha(HERE / 'audit.json'), 'audit hash mismatch')
        for k in ('reviewer', 'model_version', 'reviewed_at', 'process_notes'):
            require(isinstance(correction.get(k), str) and correction[k].strip(), 'missing correction provenance: ' + k)
        require(correction['status'] in ('partial', 'complete'), 'invalid correction status')
        require([r['answer_id'] for r in correction['decisions']] == [r['answer_id'] for r in audit['target_answers']], 'correction target coverage/order mismatch')
        merged = copy.deepcopy(read(PACKET / 'claude-review/review.json'))
        original = {a['answer_id']: a for c in merged['cases'] for a in c['answers']}
        packet_cases = {r['case_id']: read(PACKET / 'packet' / r['file']) for r in read(PACKET / 'packet/index.json')}
        judgments = {}; counts = Counter(); seen = set()
        for group, rows in (('target', correction['decisions']), ('additional', correction['additional_findings'])):
            for row in rows:
                aid = row['answer_id']; decision = row['decision']
                require(aid in original and aid not in seen, 'invalid/duplicate correction ID')
                seen.add(aid)
                require(decision in (None, 'retain', 'replace'), 'invalid correction decision')
                if decision is None:
                    require(group == 'target' and correction['status'] == 'partial', 'unfinished correction marked complete')
                    require(row['replacement'] is None, 'pending correction has replacement')
                    counts['pending'] += 1
                    continue
                require(isinstance(row['reason'], str) and row['reason'].strip(), 'correction reason missing')
                require(row['evidence'], 'correction evidence missing')
                case = packet_cases[aid.rsplit('-', 1)[0]]
                answer = next(a for a in case['answers'] if a['answer_id'] == aid)
                history = read(PACKET / 'packet' / case['history_file'])['turns']
                for e in row['evidence']:
                    require(set(e) == {'where', 'index', 'quote'} and type(e['index']) is int, 'correction evidence schema')
                    require(isinstance(e['quote'], str) and e['quote'], 'empty correction quote')
                    if e['where'] == 'history': source = history
                    elif e['where'] == 'reader_message': source = answer['actual_messages']
                    elif e['where'] == 'answer': source = [{'content': answer['text']}]
                    else: raise ValueError('invalid correction evidence location')
                    require(0 <= e['index'] < len(source) and e['quote'] in source[e['index']]['content'], 'correction evidence not exact')
                if decision == 'retain':
                    require(row['replacement'] is None, 'retain with replacement')
                else:
                    require(isinstance(row['replacement'], dict) and row['replacement'].get('answer_id') == aid, 'replacement identity mismatch')
                    require(row['replacement'] != original[aid], 'unchanged replacement; use retain')
                    judgments[aid] = row['replacement']
                counts[decision] += 1
        for c in merged['cases']:
            c['answers'] = [judgments.get(a['answer_id'], a) for a in c['answers']]
        merged['reviewer'] += '; corrections by ' + correction['reviewer']
        merged['model_version'] += '; correction reviewer: ' + correction['model_version']
        merged['reviewed_at'] = correction['reviewed_at']
        merged['blinding_notes'] += ' Correction pass was exposed to the Codex audit and original labels; not a new blinded review.'
        merged['process_notes'] += ' Correction scope: ' + correction['process_notes']
        merged['correction_provenance'] = {'parent_review_sha256': correction['parent_review_sha256'],
            'corrections_sha256': sha(args.corrections), 'correction_status': correction['status']}
        with tempfile.TemporaryDirectory(prefix='broader-correction-') as d:
            p = Path(d) / 'merged.json'; p.write_text(json.dumps(merged))
            checked = subprocess.run([sys.executable, str(PACKET / 'validate.py'), '--review', str(p)], capture_output=True, text=True)
            require(checked.returncode == 0, 'merged review invalid: ' + checked.stderr)
            validation = json.loads(checked.stdout)
        result.update(correction_status=correction['status'], correction_decisions=dict(counts),
                      candidate_merged_counts=validation['verdict_counts'], semantic_reconciliation='independent correction supplied; inspect findings')
        if args.write_merged:
            require(correction['status'] == 'complete', 'cannot publish merged review from partial corrections')
            require(not args.write_merged.exists(), 'refuse to overwrite a review')
            args.write_merged.parent.mkdir(parents=True, exist_ok=True)
            args.write_merged.write_text(json.dumps(merged, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()

"""Reconcile the saved model review without changing any reviewer judgment."""
import hashlib
import json
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PACKET = HERE.with_name('20260911-v2-broader-answer-review')
FIELDS = ('task_complete', 'source_consistent', 'supported_in_visible_state',
          'withdrawal_compliant', 'ownership_correct', 'body_valid', 'within_90_words')
CLASSES = {1: 'historical_recall', 2: 'historical_recall', 3: 'withdrawal',
           4: 'attribution', 5: 'different_value', 6: 'same_value'}


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    if (HERE / 'freeze.json').exists():
        raise RuntimeError('Audit is frozen; use verify_corrections.py, not the builder')
    validated = subprocess.run([sys.executable, str(PACKET / 'validate.py'), '--review',
        str(PACKET / 'claude-review/review.json')], check=True, capture_output=True, text=True)
    review = read(PACKET / 'claude-review/review.json')
    mapping = {x['case_id']: x for x in read(PACKET / 'sealed-map.json')}
    totals = Counter(); by_round = defaultdict(Counter); by_class = defaultdict(lambda: defaultdict(Counter))
    criteria = {f: Counter() for f in FIELDS}; paired = {str(n): Counter() for n in (1, 2)}
    families = defaultdict(lambda: defaultdict(Counter)); rows = []; flagged = defaultdict(set)
    findings = []
    for case in review['cases']:
        m = mapping[case['case_id']]; original = m['original_id']; family = original.split('-')[0]
        number = int(original.split('Q')[1]); kind = CLASSES[number]
        am = {a['answer_id']: a for a in m['answers']}; states = {}
        for answer in case['answers']:
            aid = answer['answer_id']; n = am[aid]['retrieval_rounds']; v = answer['verdict']
            totals[v] += 1; by_round[str(n)][v] += 1; by_class[kind][str(n)][v] += 1
            families[family][str(n)][v] += 1; states[n] = v
            for f in FIELDS:
                criteria[f][str(answer[f]).lower()] += 1
            rows.append({'case_id': case['case_id'], 'answer_id': aid, 'original_id': original,
                         'retrieval_rounds': n, 'class': kind, 'verdict': v})
            reason = answer['reason']
            wrong_core = (number == 3 and reason.startswith('Treats the withdrawal')) or reason.startswith((
                'Ignores', 'States the correct current value and then reverses',
                'Asserts specific content that is neither', 'Substitutes a detail', 'Reverses the direction'))
            if wrong_core and answer['task_complete'] is True:
                flagged[aid].add('task_complete_conflicts_with_reviewer_reason')
            if answer['source_consistent'] is False and answer['supported_in_visible_state'] is True:
                flagged[aid].add('check_claim_support_not_just_evidence_availability')
        if set(states) == {0, 1, 2}:
            for n in (1, 2):
                paired[str(n)][states[0] + ' -> ' + states[n]] += 1
    manual = {
        'C079-B': ('false_chronology_in_parent_pass',
            'Says the preference at T267 was later withdrawn at T172. The source order is T172 withdrawal then T267 reinstatement; compare rejected C069-A/B.'),
        'C026-A': ('withdrawn_value_referent_in_parent_pass',
            'Correct negative conclusion, but says this preference was withdrawn. T136 withdraws liking; T199 establishes not liking. Check whether the explanation attributes withdrawal to the current negative value.'),
        'C036-A': ('withdrawal_vs_later_negative_in_parent_pass',
            'Cites T260 withdrawal and T262 explicit negative as if the latter confirms the withdrawal. Check the explanation consistently against rejected C036-C; a later negative can support the answer independently.'),
        'C073-B': ('unresolved_question_scope',
            'Names the Real Estate degree and internship, omitting Temple. Preserve ambiguity unless the existing question independently requires the university name; reference wording alone does not decide that.'),
    }
    for aid, (tag, why) in manual.items():
        flagged[aid].add(tag)
        findings.append({'answer_id': aid, 'issue': tag, 'author_audit_note': why,
                         'independently_adjudicated': False})
    lookup = {x['answer_id']: x for x in rows}
    targets = [{**lookup[aid], 'audit_flags': sorted(flags)} for aid, flags in sorted(flagged.items())]
    paths = [PACKET / 'packet-manifest.json', PACKET / 'sealed-map.json',
             PACKET / 'claude-review/review.json', PACKET / 'claude-review/REVIEW.md',
             ROOT / 'CLAUDE-BROADER-ANSWERS.md', Path(__file__).resolve()]
    result = {'status': 'structural_review_valid_semantic_reconciliation_pending',
        'validator': json.loads(validated.stdout), 'review_provenance': {k: v for k, v in review.items() if k != 'cases'},
        'source_hashes': {str(p.relative_to(ROOT)): sha(p) for p in paths},
        'raw_reviewer_counts': dict(totals), 'raw_counts_by_retrieval': by_round,
        'raw_counts_by_frozen_class_and_retrieval': by_class,
        'raw_counts_by_family_and_retrieval': families, 'raw_criterion_counts': criteria,
        'paired_complete_questions': {'count': sum(paired['1'].values()), 'transitions_from_zero': paired},
        'audit_flag_counts': Counter(flag for row in targets for flag in row['audit_flags']),
        'target_answers': targets, 'author_spot_checks': findings,
        'raw_review_edited': False, 'author_replacements_applied': False, 'training_labels': 0,
        'interpretation': 'Counts reproduce the saved reviewer verdicts, not accepted corrected scores. Flags request semantic reinspection, not automatic boolean flips.'}
    (HERE / 'audit.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    template = {'reviewer': '', 'model_version': '', 'reviewed_at': '', 'status': 'partial',
        'parent_review_sha256': sha(PACKET / 'claude-review/review.json'),
        'audit_sha256': sha(HERE / 'audit.json'), 'process_notes': '', 'decisions': [
            {'answer_id': r['answer_id'], 'decision': None, 'reason': '', 'evidence': [], 'replacement': None}
            for r in targets], 'additional_findings': []}
    (HERE / 'correction-template.json').write_text(json.dumps(template, indent=2) + '\n')
    print(json.dumps({'raw_counts': totals, 'by_round': by_round,
                      'flag_counts': result['audit_flag_counts'], 'target_answers': len(targets)}, indent=2))


if __name__ == '__main__':
    main()

"""Aggregate explicit author judgments; never infer semantics from reference text."""
import datetime
import json
import re
import statistics
from collections import Counter
from pathlib import Path
from experiments.context_policy.preflight import canonical, digest

PLAN = Path(__file__).resolve().parent
RUN = PLAN.parent / '20260910-v2-memory-probe'
DATA = PLAN.parent / '20260910-v2-memory-dev'


def main():
    captures = json.loads((RUN / 'artifacts/captures.json').read_text())
    references = {x['id']: x for x in map(json.loads, (DATA / 'references.jsonl').read_text().splitlines())}
    packets = {x['id']: x for x in map(json.loads, (DATA / 'audit-packets.jsonl').read_text().splitlines())}
    manual = json.loads((RUN / 'manual-judgments.json').read_text())
    by_key = {(x['id'], x['retrieval_rounds']): x for x in manual}
    assert len(by_key) == len(manual) == len(captures) == 150
    judgments = []
    for capture in captures:
        key = (capture['id'], capture['retrieval_rounds']); given = by_key[key]
        assert given['capture_sha256'] == digest(capture)
        assert all(type(given[k]) is bool for k in ('task_complete', 'source_consistent', 'supported_in_visible_state'))
        assert given['reason'].strip()
        words = len(capture['text'].split())
        row = dict(given, reference_sha256=digest(references[capture['id']]),
                   reviewer='Codex, reference author; independent review pending',
                   kind=packets[capture['id']]['kind'], body_structurally_valid=capture['body_structurally_valid'],
                   generated_action_protocol_valid=None, word_count_whitespace=words, within_90_words=words <= 90)
        # The legacy runtime helper only rejects a LEADING marker. The frozen
        # review rule excludes repeated markers anywhere, including a trailing
        # RETRIEVE. Preserve the runtime flag and report this discrepancy.
        row['extra_action_marker'] = bool(re.search(r'(?<!\w)(?:ANSWER|RETRIEVE)(?!\w)', capture['text']))
        row['frozen_body_rule_pass'] = row['body_structurally_valid'] and not row['extra_action_marker']
        row['source_content_acceptable'] = all(row[k] for k in ('task_complete', 'source_consistent', 'supported_in_visible_state'))
        row['admissible_development_answer'] = row['source_content_acceptable'] and row['frozen_body_rule_pass'] and row['within_90_words']
        judgments.append(row)
    grouped = {}
    for row in judgments: grouped.setdefault(row['id'], []).append(row)
    routing = []
    for rid, group in grouped.items():
        group.sort(key=lambda r: r['retrieval_rounds'])
        assert [x['retrieval_rounds'] for x in group] == [0, 1, 2]
        for n in (0, 1):
            target = ('ANSWER' if group[n]['admissible_development_answer'] else
                      'RETRIEVE' if any(x['admissible_development_answer'] for x in group[n+1:]) else None)
            routing.append(dict(id=rid, kind=group[n]['kind'], retrieval_rounds=n, diagnostic_target=target,
                                training_exported=False, actual_policy_action=False,
                                current_judgment_sha256=digest(group[n]),
                                later_judgment_sha256=[digest(x) for x in group[n+1:]]))
    fields = ['task_complete', 'source_consistent', 'supported_in_visible_state',
              'body_structurally_valid', 'frozen_body_rule_pass', 'within_90_words', 'source_content_acceptable', 'admissible_development_answer']
    by_type = {}
    for kind in ('all', 'fact_recall', 'withdrawal', 'missing_information', 'generic_control'):
        rows = [x for x in judgments if kind == 'all' or x['kind'] == kind]
        by_type[kind] = dict(questions=len(rows)//3,
                            **{f: [sum(x[f] for x in rows if x['retrieval_rounds'] == n) for n in range(3)] for f in fields})
    summary = dict(reviewed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                   status='development_review_complete_independent_pending', questions=50, captures=150,
                   by_type=by_type, routing_diagnostic_counts=dict(Counter(str(x['diagnostic_target']) for x in routing)),
                   tags=dict(Counter(tag for j in judgments for tag in j.get('tags', []))),
                   generation_seconds=sum(c['elapsed_seconds'] for c in captures),
                   mean_capture_seconds=[statistics.mean(c['elapsed_seconds'] for c in captures if c['retrieval_rounds']==n) for n in range(3)],
                   mean_input_tokens=[statistics.mean(c['input_tokens'] for c in captures if c['retrieval_rounds']==n) for n in range(3)],
                   word_limit_failures=sum(not j['within_90_words'] for j in judgments),
                   extra_action_marker_count=sum(j['extra_action_marker'] for j in judgments),
                   corpus_admitted=False, corpus_trained=False, training_traces_exported=0,
                   independent_review=False, generated_action_protocol_valid=None,
                   limitations=['same ten seen source histories', 'mostly draft recall with explicit lexical cues',
                                'author also reviews', 'forced-answer collection, not learned actions or adaptive timing'])
    for name, value in [('judgments.json', judgments), ('routing-diagnostics.json', routing), ('judgment-summary.json', summary)]:
        (RUN / name).write_bytes(canonical(value))
    print(json.dumps(summary, indent=2))


if __name__ == '__main__': main()

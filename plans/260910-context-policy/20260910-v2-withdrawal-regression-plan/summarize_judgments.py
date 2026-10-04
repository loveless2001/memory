"""Aggregate explicit source-based author decisions, retaining paired identities."""
import json,datetime
from pathlib import Path
from collections import Counter
from experiments.context_policy.preflight import canonical,digest
PLAN=Path(__file__).resolve().parent
RUN=PLAN.parent/'20260910-v2-withdrawal-regression'
DATA=PLAN.parent/'20260910-v2-withdrawal-regression-data'
def main():
    captures=json.loads((RUN/'artifacts/captures.json').read_text())
    refs={r['id']:r for r in map(json.loads,(DATA/'references.jsonl').read_text().splitlines())}
    manual=json.loads((RUN/'manual-judgments.json').read_text())
    by_key={(r['id'],r['arm']):r for r in manual}
    assert len(manual)==len(by_key)==len(captures)==42
    judgments=[]
    for c in captures:
        given=by_key[(c['id'],c['arm'])]
        assert given['capture_sha256']==digest(c) and given['reference_sha256']==digest(refs[c['id']])
        assert given['reason'].strip()
        assert all(type(given[k]) is bool for k in ('task_complete','source_consistent','supported_in_visible_state'))
        row=dict(given,kind=c['kind'],retrieval_rounds=c['retrieval_rounds'],body_structurally_valid=c['body_structurally_valid'],within_90_words=c['within_90_words'],word_count=c['word_count_whitespace'],reviewer='Codex, reference author; independent review pending')
        row['pass']=all(row[k] for k in ('task_complete','source_consistent','supported_in_visible_state','body_structurally_valid','within_90_words'))
        judgments.append(row)
    grouped={}
    for kind in ['all']+list(dict.fromkeys(c['kind'] for c in captures)):
        grouped[kind]={}
        for arm in ('raw','neutral'):
            rows=[j for j in judgments if j['arm']==arm and (kind=='all' or j['kind']==kind)]
            grouped[kind][arm]=dict(passed=sum(j['pass'] for j in rows),total=len(rows))
    paired=[]
    for rid in refs:
        arms={j['arm']:j for j in judgments if j['id']==rid}
        paired.append(dict(id=rid,raw=arms['raw']['pass'],neutral=arms['neutral']['pass']))
    summary=dict(reviewed_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),status='author_review_complete_independent_pending',by_kind=grouped,paired=paired,
        paired_counts=dict(Counter(f"raw={p['raw']},neutral={p['neutral']}" for p in paired)),
        body_valid=sum(c['body_structurally_valid'] for c in captures),within_90_words=sum(c['within_90_words'] for c in captures),
        neutral_clean_regression=grouped['all']['neutral']['passed']==21,
        failures=[dict(id=j['id'],arm=j['arm'],reason=j['reason']) for j in judgments if not j['pass']],
        training_performed=False,corpus_admitted=False,training_exported=False,independent_review=False,generated_action_protocol_valid=None)
    (RUN/'judgments.json').write_bytes(canonical(judgments));(RUN/'judgment-summary.json').write_bytes(canonical(summary))
    print(json.dumps(summary,indent=2))
if __name__=='__main__':main()

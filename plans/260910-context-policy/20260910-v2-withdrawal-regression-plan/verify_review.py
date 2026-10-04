"""Bind the completed semantic review, sources, billing and output files."""
import json
from decimal import Decimal
from pathlib import Path
from experiments.context_policy.preflight import canonical,digest
from experiments.context_policy.personamem import sha256,reader_history
from experiments.context_policy.relabel import validate_reference
PLAN=Path(__file__).resolve().parent
ROOT=PLAN.parents[2]
RUN=PLAN.parent/'20260910-v2-withdrawal-regression'
DATA=PLAN.parent/'20260910-v2-withdrawal-regression-data'
def read(p):return json.loads(p.read_text())
def main():
    refs=list(map(json.loads,(DATA/'references.jsonl').read_text().splitlines()))
    records=list(map(json.loads,(DATA/'records.jsonl').read_text().splitlines()))
    bundle=read(DATA/'reader-input.json')
    assert len(refs)==len(records)==len(bundle['questions'])==21
    for ref,record,q in zip(refs,records,bundle['questions']):
        validate_reference(record,ref)
        assert record['history']==bundle['histories'][q['persona_id']]
        assert {k:record[k] for k in ('id','persona_id','query')}==q
        raw=ROOT/record['history_path'] if q['persona_id'].startswith('s') else ROOT/'data/context-policy/personamem-v2'/record['history_path']
        assert sha256(raw.read_bytes())==record['source_sha256']
        source=read(raw)
        assert (source if q['persona_id'].startswith('s') else reader_history(source))==record['history']
    captures=read(RUN/'artifacts/captures.json');judgments=read(RUN/'judgments.json');summary=read(RUN/'judgment-summary.json')
    by_ref={r['id']:r for r in refs}
    assert len(captures)==len(judgments)==42
    for c,j in zip(captures,judgments):
        assert (c['id'],c['arm'])==(j['id'],j['arm'])
        assert j['capture_sha256']==digest(c) and j['reference_sha256']==digest(by_ref[c['id']])
        assert j['pass']==all(j[k] for k in ('task_complete','source_consistent','supported_in_visible_state','body_structurally_valid','within_90_words'))
    assert summary['by_kind']['all']=={'raw':{'passed':8,'total':21},'neutral':{'passed':17,'total':21}}
    assert not summary['neutral_clean_regression'] and not summary['training_performed']
    assert read(RUN/'source-capture-verification.json')['status']=='pass'
    assert read(RUN/'remote-status.json')==read(RUN/'artifacts/status.json')
    status=read(RUN/'completed-app-status.json');launch=read(RUN/'launch.json')
    assert status['app_id']==launch['app_id'] and status['state']=='stopped' and str(status['tasks'])=='0'
    billing=read(RUN/'billing.json');assert billing['app_id']==launch['app_id']
    cost=sum(Decimal(r['cost']) for r in billing['rows'])
    assert all(r['object_id']==launch['app_id'] for r in billing['rows'])
    previous=read(PLAN.parent/'20260910-v2-memory-probe/verification.json')
    total=Decimal(previous['cumulative_cost_usd'])+cost
    result=dict(status='pass',reference_source_checks=21,judgment_bindings=42,raw_passes=8,neutral_passes=17,clean_regression_pass=False,app_stopped=True,cost_usd=str(cost),cumulative_cost_usd=str(total),maximum_generated_words=max(c['word_count_whitespace'] for c in captures),training_performed=False,training_exported=False,independent_review=False,
        postprocessing_sources={str(p.relative_to(ROOT)):sha256(p.read_bytes()) for p in sorted(PLAN.glob('*.py'))},
        output_hashes={str(p.relative_to(RUN)):sha256(p.read_bytes()) for p in sorted(RUN.rglob('*')) if p.is_file() and p.name!='verification.json'})
    (RUN/'verification.json').write_bytes(canonical(result))
    print(json.dumps({k:v for k,v in result.items() if k not in ('postprocessing_sources','output_hashes')}))
if __name__=='__main__':main()

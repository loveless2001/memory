"""Store explicit author judgments; this helper performs no answer grading."""
import json
from pathlib import Path
HERE=Path(__file__).resolve().parent
FIELDS={'task_complete','source_consistent','supported_in_visible_state','withdrawal_compliant','ownership_correct'}
RF={'state_correct','query_interpretation_correct','decision_correct','evidence_sufficient','record_ownership_correct'}
def load():
 p=HERE/'review-decisions.json'
 return json.loads(p.read_text()) if p.exists() else {'review_complete':False,'answers':{},'result_notes':[],'interpretation_notes':[]}
def add(d,arm,ids,reason,answer_fail=(),record_fail=()):
 assert not d['review_complete'];assert set(answer_fail)<=FIELDS and set(record_fail)<=RF
 if isinstance(ids,str):ids=[ids]
 for cid in ids:
  key=arm+':'+cid;assert key not in d['answers'],key
  d['answers'][key]={'failed_fields':list(answer_fail),'reason':reason,'record':{k:k not in record_fail for k in sorted(RF)} if arm.endswith('decision') else None}
def save(d):
 (HERE/'review-decisions.json').write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
 print('EXPLICIT JUDGMENTS',len(d['answers']))

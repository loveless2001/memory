"""Compute descriptive matched comparisons from explicit author judgments."""
import json,sys,runpy
from pathlib import Path
from collections import Counter
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE.parents[1]))
from experiments.context_policy.reader_factor_protocol import project
read=lambda p:json.loads(p.read_text())
ARMS=['direct','extracted_fact','oracle_fact','oracle_query']
def summarize():
 verification=runpy.run_path(str(HERE/'verify_artifacts.py'))['verify']()
 review=read(HERE/'review.json');assert review==runpy.run_path(str(HERE/'record_review.py'))['materialize']()
 cases=read(HERE/'preflight/cases.json');streams=read(HERE/'preflight/streams-gold.json');xm={x['id']:x for x in review['extractions']};am={(a['arm'],a['id']):a for a in review['answers']}
 def score(ids,arm):
  js=[am[arm,cid] for cid in ids]
  return {'total':len(js),'strict_correct':sum(j['verdict']=='pass' for j in js),'required_answer_correct':sum(j['task_complete'] for j in js),'strict_failures':[j['id'] for j in js if j['verdict']=='fail'],'required_answer_failures':[j['id'] for j in js if not j['task_complete']]}
 groups={'all':[c['id'] for c in cases]}
 for field in ('split','kind','question_form'):
  for value in sorted({c[field] for c in cases}):groups[field+':'+value]=[c['id'] for c in cases if c[field]==value]
 scores={name:{arm:score(ids,arm) for arm in ARMS} for name,ids in groups.items()}
 transitions={}
 for before,after in [('direct','extracted_fact'),('direct','oracle_fact'),('oracle_fact','oracle_query'),('extracted_fact','oracle_fact')]:
  transitions[before+'->'+after]={}
  for metric in ('strict','required'):
   ok=lambda j:j['verdict']=='pass' if metric=='strict' else j['task_complete']
   transitions[before+'->'+after][metric]={'corrected':[c['id'] for c in cases if not ok(am[before,c['id']]) and ok(am[after,c['id']])],'regressed':[c['id'] for c in cases if ok(am[before,c['id']]) and not ok(am[after,c['id']])]}
 extraction={k:sum(x[k] for x in xm.values()) for k in ('schema_and_spans_valid','raw_semantic_meaning_correct','record_state_correct','evidence_sufficient_for_true_state','ownership_correct','literal_record_matches_gold','usable_correct_record')};extraction['total']=16
 pathway={}
 for label,flag in [('correct_record',True),('incorrect_record',False)]:
  ids=[c['id'] for c in cases if xm[c['stream_id']]['usable_correct_record']==flag];pathway[label]=score(ids,'extracted_fact')
 mechanical=[]
 for c in cases:
  x=xm[c['stream_id']];rec=x['evidence']['parsed'];gold=next(s['record'] for s in streams if s['id']==c['stream_id'])
  assert project(gold,c['query_record'])==c['reference']['projection']
  actual=project(rec['record'],c['query_record']) if rec['valid'] else None
  mechanical.append({'id':c['id'],'stream_id':c['stream_id'],'actual':actual,'reference':c['reference']['projection'],'usable':rec['valid'],'correct':rec['valid'] and actual==c['reference']['projection']})
 consistency={arm:{'fully_strict_correct_histories':[s['id'] for s in streams if all(am[arm,c['id']]['verdict']=='pass' for c in cases if c['stream_id']==s['id'])],'fully_required_correct_histories':[s['id'] for s in streams if all(am[arm,c['id']]['task_complete'] for c in cases if c['stream_id']==s['id'])]} for arm in ARMS}
 sensitivity={}
 for arm in ARMS:
  ids=[c['id'] for c in cases if c['kind']=='unknown' and not am[arm,c['id']]['task_complete']]
  sensitivity[arm]={'categorical_no_failures':ids,'strict_correct_if_all_read_as_epistemic_refusal':scores['all'][arm]['strict_correct']+len(ids),'total':64}
 return {'status':'complete','descriptive_only':True,'independent_review':False,'answer_captures':256,'extraction_captures':16,'scores':scores,'extraction':extraction,'matched_transitions':transitions,'extracted_answer_pathway':pathway,'record_faithfulness':{a:sum(am[a,c['id']]['record_faithful'] for c in cases) for a in ARMS[1:]},'typed_status_followed':{a:sum(am[a,c['id']]['typed_status_followed'] for c in cases) for a in ARMS[1:]},'history_consistency':consistency,'mechanical_selector':{'oracle_query_required':True,'gold_record_correct':64,'model_record_correct':sum(r['correct'] for r in mechanical),'total':64,'rows':mechanical,'normalization':'Frozen case-folded literal equality only; no post hoc alias normalization.'},'withdrawal_wording_sensitivity':sensitivity,'verification':verification}
if __name__=='__main__':
 r=summarize()
 if (HERE/'result-manifest.json').exists():assert r==read(HERE/'summary.json')
 else:(HERE/'summary.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({k:r[k] for k in ('extraction','matched_transitions','extracted_answer_pathway')}));print(json.dumps(r['scores']['all']))

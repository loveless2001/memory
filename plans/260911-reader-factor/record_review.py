"""Bind explicit inspected author judgments to captured prompts and complete sources."""
import hashlib,json
from pathlib import Path
from datetime import datetime,timezone
HERE=Path(__file__).resolve().parent
read=lambda p:json.loads(p.read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
FIELDS=('task_complete','source_consistent','supported_in_visible_state','withdrawal_compliant','ownership_correct')
def materialize():
 d=read(HERE/'review-decisions.json');assert d['review_complete'];cases={c['id']:c for c in read(HERE/'preflight/cases.json')};reused=read(HERE/'preflight/reused-ids.json')
 prior=HERE.parent/'260911-reader-sft-v2';oc={c['id']:c for c in read(prior/'run/captures.json') if c['arm']=='adapted'};oj={c['id']:c for c in read(prior/'review.json')['answers'] if c['arm']=='adapted'}
 answers=[];used=set()
 for c in read(HERE/'run/captures.json'):
  key=c['arm']+':'+c['id'];case=cases[c['id']];fields=dict.fromkeys(FIELDS,True)
  if c['arm']=='direct' and c['id'] in reused:
   assert all(c[k]==oc[c['id']][k] for k in ('messages','token_ids','text'));j=oj[c['id']];fields={k:j[k] for k in FIELDS};reason='Exact previous messages, tokens and text reproduced; retain the prior source-reviewed judgment. '+j['reason'];rf=ts=None
  else:
   j=d['answers'][key];used.add(key)
   for k in j['failed_fields']:assert k in FIELDS;fields[k]=False
   reason=j['reason'];rf=j['record_faithful'];ts=j['typed_status_followed']
  fields.update(body_valid=c['body_structurally_valid'],within_90_words=c['within_90_words'])
  answers.append({'id':c['id'],'arm':c['arm'],**fields,'record_faithful':rf,'typed_status_followed':ts,'verdict':'pass' if all(fields.values()) else 'fail','reason':reason,'evidence':{'answer':c['text'],'actual_messages':c['messages'],'history':case['history'],'query':case['query'],'reference':case['reference']}})
 assert used==set(d['answers']) and len(answers)==256
 streams={s['id']:s for s in read(HERE/'preflight/streams-gold.json')};extracts=[]
 for c in read(HERE/'run/extractions.json'):
  j=d['extractions'][c['id']];valid=c['parsed']['valid']
  extracts.append({'id':c['id'],**j,'schema_and_spans_valid':valid,'usable_correct_record':valid and j['record_state_correct'] and j['evidence_sufficient_for_true_state'] and j['ownership_correct'],'evidence':{'raw':c['text'],'parsed':c['parsed'],'actual_messages':c['messages'],'history':streams[c['id']]['history'],'gold':streams[c['id']]['record']}})
 return {'status':'complete','reviewer':'Codex, experiment author','independent':False,'process':'Unblinded author inspection of all sixteen extraction outputs and all 256 final answers against source, reference and actual prompt; 12 exact previous direct judgments retained, 244 new explicit answer decisions. No keyword-derived semantic grading. Quotes are part of record prompts and can preserve facts lost by the typed status.','captures_sha256':sha(HERE/'run/captures.json'),'extractions_sha256':sha(HERE/'run/extractions.json'),'cases_sha256':sha(HERE/'preflight/cases.json'),'decisions_sha256':sha(HERE/'review-decisions.json'),'prior_review_sha256':sha(prior/'review.json'),'answers':answers,'extractions':extracts,'interpretation_notes':d['interpretation_notes']}
if __name__=='__main__':
 r=materialize()
 if (HERE/'result-manifest.json').exists():assert r==read(HERE/'review.json')
 else:(HERE/'review.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({'answers':len(r['answers']),'extractions':len(r['extractions'])}))

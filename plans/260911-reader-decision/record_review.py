"""Materialize explicit author decisions with complete source and capture evidence."""
import json,hashlib
from pathlib import Path
HERE=Path(__file__).resolve().parent
read=lambda p:json.loads(p.read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
FIELDS=('task_complete','source_consistent','supported_in_visible_state','withdrawal_compliant','ownership_correct')
RECORD_FIELDS=('state_correct','query_interpretation_correct','decision_correct','evidence_sufficient','record_ownership_correct')

def materialize():
 d=read(HERE/'review-decisions.json');assert d['review_complete']
 cases={c['id']:c for c in read(HERE/'preflight/eval-cases.json')};caps=read(HERE/'run/captures.json');renders={(r['arm'],r['id']):r for r in read(HERE/'rendered-decisions.json')}
 old_c={c['id']:c for c in read(HERE.parent/'260911-reader-sft-v2/run/captures.json') if c['arm']=='adapted'}
 old_j={c['id']:c for c in read(HERE.parent/'260911-reader-sft-v2/review.json')['answers'] if c['arm']=='adapted'}
 old_c.update({c['id']:c for c in read(HERE.parent/'260911-reader-factor/run/captures.json') if c['arm']=='direct'})
 old_j.update({c['id']:c for c in read(HERE.parent/'260911-reader-factor/review.json')['answers'] if c['arm']=='direct'})
 answers=[];used=set();retained=[]
 for c in caps:
  key=c['arm']+':'+c['id'];case=cases[c['id']];fields=dict.fromkeys(FIELDS,True);structured=c['format']=='decision';record_fields=None
  if c['arm']=='current_direct' and case['split']=='regression':
   oc=old_c[c['id']];oj=old_j[c['id']]
   assert all(c[k]==oc[k] for k in ('messages','token_ids','text'))
   fields={k:oj[k] for k in FIELDS};reason='Exact previous v2 messages, tokens and text reproduced; retain the prior source-reviewed judgment. '+oj['reason'];retained.append(c['id'])
  else:
   j=d['answers'][key];used.add(key)
   assert len(j['failed_fields'])==len(set(j['failed_fields']))
   for k in j['failed_fields']:assert k in FIELDS;fields[k]=False
   reason=j['reason']
   if j.get('method')=='canonical_reference_equality_plus_rendered_review':
    assert structured and case['split']=='test' and c['arm']=='trained_decision'
    rr=renders[(c['arm'],c['id'])];assert rr['parsed']['valid'] and rr['parsed']['record']==case['reference']['decision']
    assert not j['failed_fields'] and all(j['record'].values())
   if structured:
    assert set(j['record'])==set(RECORD_FIELDS);record_fields=j['record']
    assert all(type(v) is bool for v in record_fields.values())
   else:assert j.get('record') is None
  r=renders[(c['arm'],c['id'])] if structured else None
  text=r['rendered_text'] if structured else c['text']
  schema=r['parsed']['valid'] if structured else None
  if structured and not schema:assert not fields['task_complete'],'invalid decisions must fail the requested task'
  fields.update(body_valid=c['body_structurally_valid'],within_90_words=len(text.split())<=90)
  rendered_ok=all(fields.values());semantic=all(record_fields.values()) if structured else None
  strict=rendered_ok and (not structured or schema and semantic)
  answers.append({'id':c['id'],'arm':c['arm'],'format':c['format'],**fields,'schema_valid':schema,'record_criteria':record_fields,
   'record_semantically_correct':semantic,'rendered_verdict':'pass' if rendered_ok else 'fail','verdict':'pass' if strict else 'fail','reason':reason,
   'evidence':{'raw_model_text':c['text'],'rendered_answer':text,'parsed_record':r['parsed'] if structured else None,'actual_messages':c['messages'],
    'history':case['history'],'query':case['query'],'reference':case['reference']}})
 assert used==set(d['answers']) and len(used)==1420 and len(retained)==260 and len(answers)==1680
 return {'status':'complete','reviewer':'Codex, experiment author','independent':False,
  'process':'Unblinded author review against complete source, actual prompt, original reference, raw model output and rendered answer. Review started after both fixed trainings finished. All 260 exactly reproduced previous direct judgments are retained; 1420 new explicit decisions cover 580 prose answers and 840 structured decisions. For 140 new trained-decision answers, all nine parsed fields exactly reproduce canonical records already reviewed against the source before inference; equality is verified and each rendered answer is reviewed. All noncanonical records are inspected individually. Structured semantic criteria are independent of schema/span validity and include the complete record even if rendering hides a mistake.',
  'captures_sha256':sha(HERE/'run/captures.json'),'cases_sha256':sha(HERE/'preflight/eval-cases.json'),'rendered_decisions_sha256':sha(HERE/'rendered-decisions.json'),
  'decisions_sha256':sha(HERE/'review-decisions.json'),'prior_review_sha256':{n:sha(HERE.parent/n/'review.json') for n in ('260911-reader-sft-v2','260911-reader-factor')},
  'canonical_reference_equality_reviews':sum(j.get('method')=='canonical_reference_equality_plus_rendered_review' for j in d['answers'].values()),'retained_prior_ids':retained,'interpretation_notes':d.get('interpretation_notes',[]),'answers':answers}
if __name__=='__main__':
 r=materialize()
 if (HERE/'result-manifest.json').exists():assert r==read(HERE/'review.json')
 else:(HERE/'review.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({'answers':len(r['answers']),'strict_passes':sum(j['verdict']=='pass' for j in r['answers'])}))

"""Build and freeze the authorized matched decision-supervision experiment."""
import argparse,copy,hashlib,json,random,sys
from pathlib import Path
from datetime import datetime,timezone
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2];PARENT=ROOT/'plans/260911-reader-factor'
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(HERE))
from author import make_training,make_test
from transformers import AutoTokenizer
from experiments.context_policy.reader_state_protocol import archive_messages
from experiments.context_policy.reader_decision_protocol import decision_messages,parse_decision,render_decision
from experiments.context_policy.reader_sft_protocol import encode_answer
from experiments.context_policy.broader_protocol import answer_prefix_ids
read=lambda p:json.loads(p.read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def digest(x):return hashlib.sha256(json.dumps(x,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
def write(n,x):(HERE/n).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')

def regression_cases():
 rows=copy.deepcopy(read(ROOT/'plans/260911-reader-sft-v2/preflight/eval-cases.json'));seen={r['id']:r for r in rows}
 for c in read(PARENT/'preflight/cases.json'):
  if c['id'] in seen:
   old=seen[c['id']];assert old['history']==c['history'] and old['query']==c['query']
  else:rows.append(copy.deepcopy(c));seen[c['id']]=c
 for c in rows:c['previous_split']=c['split'];c['split']='regression'
 assert len(rows)==260
 return rows

def prior_passes(cases):
 bycontent={digest([c['history'],c['query']]):c['id'] for c in cases};positive={c['id']:[] for c in cases};bindings={}
 for dirname in ('260911-reader-diagnostic','260911-reader-repair','260911-reader-qwen3-8b','260911-reader-state','260911-reader-sft','260911-reader-sft-v2','260911-reader-factor'):
  p=ROOT/'plans'/dirname;rf=p/'review.json';cf=p/'preflight/eval-cases.json'
  if not cf.exists():cf=p/'preflight/cases.json'
  local={c['id']:c for c in read(cf)};bindings[str(rf.relative_to(ROOT))]=sha(rf);bindings[str(cf.relative_to(ROOT))]=sha(cf)
  for j in read(rf)['answers']:
   if j['verdict']!='pass' or 'oracle' in j['arm']:continue
   c=local[j['id']];key=digest([c['history'],c['query']])
   if key in bycontent:positive[bycontent[key]].append({'review':str(rf.relative_to(ROOT)),'id':j['id'],'arm':j['arm']})
 return {'rule':'Preserve every strict-correct non-oracle answer on an identical source history/question from the seven prior reader experiments. This includes previous direct and extracted pipelines, all sizes; oracle outputs are excluded.','source_hashes':bindings,'required_ids':[cid for cid,sources in positive.items() if sources],'sources_by_id':positive}

def audit_new(rows):
 for c in rows:
  r=c['reference'];g=r['decision'];p=parse_decision(json.dumps(g),c['history'],c['query']);assert p['valid'],(c['id'],p)
  assert g['scope']==c['scope'];assert (g['operation']=='lookup')==(c['question_form']=='open')
  assert r['binary_truth']==(True if g['decision']=='supported' else False if g['decision']=='contradicted' else None)
  if g['status']=='unknown':assert g['decision']=='unknown' and g['value'] is None
  elif g['operation']=='lookup':assert g['decision']=='answer'
  elif g['operation']=='states_none':assert g['status']=='none' and g['decision']=='supported'
  elif g['operation']=='states_negative':assert g['status']=='negative' and g['decision']=='supported'
  else:
   expected=('supported' if g['status']=='value' and g['candidate']==g['value'] else
             'unknown' if g['candidate']!=g['value'] and (g['status']=='negative' or g['relation']=='enjoyment' and g['scope']=='current') else 'contradicted')
   assert g['decision']==expected,(c['id'],g)
  for answer in (r['answer'],render_decision(p)):
   assert len(answer.split())<=90
   if g['status']=='unknown':assert not answer.startswith(('Yes.','No.'))
   if g['scope']=='current':assert not any(v.casefold() in answer.casefold() for v in r['forbidden_old_values'])
  assert g['quote']==c['history'][g['turn']]['content']
 assert len({c['id'] for c in rows})==len(rows)

def construct(tok):
 train=make_training();test=make_test();audit_new(train);audit_new(test);regression=regression_cases();cases=regression+test
 old_train=read(ROOT/'plans/260911-reader-sft-v2/preflight/train-cases.json')
 for field in ('history','query'):
  assert {digest(c[field]) for c in train}.isdisjoint({digest(c[field]) for c in cases}),field
  assert {digest(c[field]) for c in test}.isdisjoint({digest(c[field]) for c in old_train+regression}),field
 assert {c['property'] for c in train}.isdisjoint({c['property'] for c in old_train+cases})
 assert {c['property'] for c in test}.isdisjoint({c['property'] for c in old_train+regression})
 encoded=[]
 for c in train:
  row={'id':c['id'],'family':c['family']}
  for fmt,fn,target,cap in [('prose',archive_messages,c['reference']['answer'],192),('decision',decision_messages,json.dumps(c['reference']['decision'],ensure_ascii=False,separators=(',',':')),256)]:
   m=fn(c['history'],c['query']);row[fmt]={'messages':m,'answer':target,**encode_answer(tok,m,target,max_answer_tokens=cap)}
  assert row['prose']['messages'][1]==row['decision']['messages'][1];encoded.append(row)
 inputs=[]
 prior={c['id']:c for c in read(ROOT/'plans/260911-reader-sft-v2/run/captures.json') if c['arm']=='adapted'}
 prior.update({c['id']:c for c in read(PARENT/'run/captures.json') if c['arm']=='direct'})
 for c in cases:
  row={'id':c['id'],'split':c['split']}
  for fmt,fn in [('prose',archive_messages),('decision',decision_messages)]:
   m=fn(c['history'],c['query']);row[fmt]={'messages':m,'input_tokens':len(answer_prefix_ids(tok,m))}
  assert row['prose']['messages'][1]==row['decision']['messages'][1]
  if c['split']=='regression':assert row['prose']['messages']==prior[c['id']]['messages']
  inputs.append(row)
 gates=[]
 for split in ('regression','test'):
  gates += sorted([c['id'] for c in cases if c['split']==split],key=lambda cid:digest(['decision-gate',cid]))[:10]
 orders=[]
 for epoch in range(2):
  ids=[c['id'] for c in train];random.Random(2301+epoch).shuffle(ids);orders.append(ids)
 return train,cases,encoded,inputs,gates,orders,prior_passes(regression)

def main(freeze=False):
 assert not (HERE/'freeze.json').exists()
 config=read(ROOT/'plans/260911-reader-sft-v2/preflight/runtime-config.json')
 factor=read(PARENT/'preflight/runtime-config.json')
 config.update(planned_captures=1680,planned_training_examples=512,optimizer_steps=64,
  max_gpu_seconds=3600,internal_deadline_seconds=3500,initialization='two independent continuations from the same frozen v2 adapter',
  prior_adapter_files=factor['adapter_files'],prior_base_tensors=factor['base_tensors'],prior_adapter_tensors=factor['adapter_tensors'],
  arms=['current_direct','current_decision','trained_direct','trained_decision'],output_cap_by_format={'prose':192,'decision':256},
  training_runs=2,training_examples_per_adapter=512,optimizer_steps_per_adapter=64,
  success_rule={'new_strict_minimum':152,'new_total':160,'strictly_beat_current_direct':True,'strictly_beat_trained_direct':True,
   'protected_regression_losses':0,'structured_semantics_required':True,'invalid_decision_fails':True},
  checkpoint_selection='fixed final after two epochs for each continuation; no search')
 tok=AutoTokenizer.from_pretrained(config['model_id'],revision=config['model_revision'],local_files_only=True)
 values=construct(tok);train,cases,encoded,inputs,gates,orders,positive=values
 sources=read(PARENT/'preflight/runtime-sources.json')
 for n in ('experiments/context_policy/reader_factor.py','experiments/context_policy/reader_factor_protocol.py'):sources.pop(n)
 for n in ('experiments/context_policy/reader_decision.py','experiments/context_policy/reader_decision_protocol.py'):sources[n]=sha(ROOT/n)
 for n,h in sources.items():assert sha(ROOT/n)==h,n
 protected=read(PARENT/'preflight/protected.json');protected.update(read(PARENT/'result-manifest.json')['files'])
 protected[str((PARENT/'result-manifest.json').relative_to(ROOT))]=sha(PARENT/'result-manifest.json')
 for n in ('experiments/context_policy/reader_factor.py','experiments/context_policy/reader_factor_protocol.py','modal-runners/modal-reader-factor.py','tests/test_context_policy_reader_factor.py'):protected[n]=sha(ROOT/n)
 for n,h in protected.items():assert sha(ROOT/n)==h,n
 names=('train-cases.json','eval-cases.json','train-inputs.json','eval-inputs.json','gate-ids.json','training-order.json','prior-passes.json')
 for n,x in zip(names,values):write(n,x)
 for n,x in [('runtime-config.json',config),('runtime-sources.json',sources),('protected.json',protected)]:write(n,x)
 stats={'status':'PASS','training_examples_per_adapter':512,'training_histories':len({digest(c['history']) for c in train}),
  'training_properties':len({c['property'] for c in train}),'new_questions':160,'new_histories':40,'regression_questions':260,'previously_correct_regression_questions':len(positive['required_ids']),
  'planned_captures':1680,'training_runs':2,'optimizer_steps_per_adapter':64,'exposures_per_adapter':1024,'eval_answers_mounted':False,'oracle_metadata_mounted':False,
  'same_user_message_by_format':True,'train_eval_history_query_property_overlap':0,'new_prior_history_query_property_overlap':0,
  'max_train_tokens':{f:max(len(r[f]['input_ids']) for r in encoded) for f in ('prose','decision')},
  'training_target_tokens_per_epoch':{f:sum(r[f]['supervised_tokens'] for r in encoded) for f in ('prose','decision')},
  'training_prefix_tokens_per_epoch':{f:sum(r[f]['prefix_tokens'] for r in encoded) for f in ('prose','decision')},
  'max_eval_input_tokens':{f:max(r[f]['input_tokens'] for r in inputs) for f in ('prose','decision')},'protected_files':len(protected)}
 write('cpu-checks.json',stats)
 if freeze:
  assert read(HERE/'test-results.json')['passed'] and (HERE/'REFERENCE-REVIEW.md').exists()
  paths=[p for p in HERE.iterdir() if p.is_file()]+[ROOT/n for n in (*sources,'modal-runners/modal-reader-decision.py','tests/test_context_policy_reader_decision.py')]+[HERE.parent/'authorization.json']
  write('freeze.json',{'frozen_at':datetime.now(timezone.utc).isoformat(),'files':{str(p.relative_to(ROOT)):sha(p) for p in paths},
   'parent_manifest_sha256':sha(PARENT/'result-manifest.json'),'training_targets_mounted':True,'evaluation_references_mounted':False,'prior_outputs_mounted':False})
 print(json.dumps(stats,indent=2))
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--freeze',action='store_true');main(ap.parse_args().freeze)

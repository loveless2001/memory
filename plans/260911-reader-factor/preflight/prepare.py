import argparse,json,hashlib,sys
from pathlib import Path
from datetime import datetime,timezone
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2];PARENT=ROOT/'plans/260911-reader-sft-v2'
sys.path.insert(0,str(ROOT))
from author import make
from transformers import AutoTokenizer
from experiments.context_policy.reader_state_protocol import archive_messages
from experiments.context_policy.reader_factor_protocol import extraction_messages,record_messages,parse_record,project
from experiments.context_policy.broader_protocol import answer_prefix_ids
read=lambda p:json.loads(p.read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
digest=lambda x:hashlib.sha256(json.dumps(x,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
def write(n,x):(HERE/n).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def construct(tok):
 streams,cases=make();sm={s['id']:s for s in streams};inputs=[];extract=[]
 prior={c['id']:c for c in read(PARENT/'run/captures.json') if c['arm']=='adapted'}
 reused=[]
 for s in streams:
  assert parse_record(json.dumps(s['record']),s['history'])['valid'],s['id']
  extract.append({'id':s['id'],'property':s['property'],'history':s['history'],'messages':extraction_messages(s['history'],s['property'])})
 for c in cases:
  g=project(sm[c['stream_id']]['record'],c['query_record'])
  if c['reference']['binary_truth'] is not None:assert g=={'kind':'boolean','value':c['reference']['binary_truth']},c['id']
  c['reference']['projection']=g
  m=archive_messages(c['history'],c['query'])
  if c['id'] in prior:
   assert m==prior[c['id']]['messages'];reused.append(c['id'])
  for arm,messages in [('direct',m),('oracle_fact',record_messages(c['property'],sm[c['stream_id']]['record'],c['query'])),
                       ('oracle_query',record_messages(c['property'],sm[c['stream_id']]['record'],c['query'],c['query_record']))]:
   inputs.append({'id':c['id'],'arm':arm,'request_id':arm+':'+c['id'],'messages':messages})
 for r in inputs+extract:r['input_tokens']=len(answer_prefix_ids(tok,r['messages']))
 new=[s for s in streams if s['split']=='new'];oldcases=read(PARENT/'preflight/eval-cases.json');train=read(PARENT/'preflight/train-cases.json')
 assert len(reused)==12
 assert {s['property'] for s in new}.isdisjoint({c['property'] for c in oldcases+train})
 assert {digest(s['history']) for s in new}.isdisjoint({digest(c['history']) for c in oldcases+train})
 assert {c['query'] for c in cases if c['split']=='new'}.isdisjoint({c['query'] for c in oldcases+train})
 questions=[{k:c[k] for k in ('id','stream_id','property','query')} for c in cases]
 gates={a:sorted([c['id'] for c in cases],key=lambda cid:digest([a,cid]))[:5] for a in ('direct','oracle_fact','oracle_query','extracted_fact')}
 gates['extract']=sorted(sm,key=lambda sid:digest(['extract',sid]))[:5]
 return streams,cases,inputs,extract,questions,gates,reused

def main(freeze=False):
 assert not (HERE/'freeze.json').exists()
 base=read(PARENT/'preflight/runtime-config.json');trained=read(PARENT/'run/training.json')
 cfg={k:base[k] for k in ('model_id','model_revision','active_context_max_tokens','max_message_output_tokens','seed')}
 cfg.update(max_gpu_seconds=1200,internal_deadline_seconds=1100,retries=0,planned_answers=256,planned_extractions=16,
  adapter_files={n:sha(PARENT/'run/adapter'/n) for n in ('adapter_model.safetensors','adapter_config.json')},
  base_tensors=trained['base_tensors_after'],adapter_tensors=trained['trained_adapter_tensors'])
 tok=AutoTokenizer.from_pretrained(cfg['model_id'],revision=cfg['model_revision'],local_files_only=True)
 values=construct(tok)
 for n,x in zip(('streams-gold.json','cases.json','static-inputs.json','extraction-inputs.json','questions.json','gate-ids.json','reused-ids.json'),values):write(n,x)
 sources=read(PARENT/'preflight/runtime-sources.json');sources.pop('experiments/context_policy/reader_sft_v2.py')
 for n in ('experiments/context_policy/reader_factor.py','experiments/context_policy/reader_factor_protocol.py','experiments/context_policy/reader_sft.py'):sources[n]=sha(ROOT/n)
 for n,h in sources.items():assert sha(ROOT/n)==h
 protected=read(PARENT/'preflight/protected.json');protected.update(read(PARENT/'result-manifest.json')['files'])
 for n in ('plans/260911-reader-sft-v2/result-manifest.json','experiments/context_policy/reader_sft_v2.py','modal-runners/modal-reader-sft-v2.py'):protected[n]=sha(ROOT/n)
 for n,h in protected.items():assert sha(ROOT/n)==h,n
 for n,x in [('runtime-config.json',cfg),('runtime-sources.json',sources),('protected.json',protected)]:write(n,x)
 stats={'status':'PASS','histories':16,'questions':64,'new_histories':12,'new_questions':48,'reused_history_questions':16,
  'exact_prior_questions':12,'planned_model_answers':256,'planned_extractions':16,'cache_checks':25,
  'max_static_input_tokens':max(r['input_tokens'] for r in values[2]),'max_extract_input_tokens':max(r['input_tokens'] for r in values[3]),
  'protected_files':len(protected),'training':False}
 write('cpu-checks.json',stats)
 if freeze:
  assert read(HERE/'test-results.json')['passed'] and (HERE/'REFERENCE-REVIEW.md').exists()
  paths=[p for p in HERE.iterdir() if p.is_file()]+[ROOT/n for n in (*sources,'modal-runners/modal-reader-factor.py','tests/test_context_policy_reader_factor.py')]+[HERE.parent/'authorization.json']
  write('freeze.json',{'frozen_at':datetime.now(timezone.utc).isoformat(),'files':{str(p.relative_to(ROOT)):sha(p) for p in paths},'parent_manifest_sha256':sha(PARENT/'result-manifest.json'),
    'gold_records_mounted_for_oracle_arms':True,'gold_query_interpretations_mounted_for_oracle_query_arm':True,'final_answer_references_mounted':False})
 print(json.dumps(stats,indent=2))
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--freeze',action='store_true');main(ap.parse_args().freeze)

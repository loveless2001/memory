"""Verify frozen prompts, derived records, token accounting and numerical gates."""
import hashlib,json,sys
from pathlib import Path
from collections import defaultdict,Counter
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];P=HERE/'preflight';R=HERE/'run'
sys.path.insert(0,str(ROOT))
from experiments.context_policy.preflight import digest
from experiments.context_policy.broader_protocol import answer_prefix_ids,strict_body_capture
from experiments.context_policy.reader_factor_protocol import parse_record,record_messages
from transformers import AutoTokenizer
read=lambda p:json.loads(p.read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def verify():
 l=read(R/'launch.json');m=read(R/'manifest.json');s=read(R/'status.json');cfg=read(P/'runtime-config.json')
 for n,h in read(R/'artifact-hashes.json').items():
  assert not Path(n).is_absolute() and '..' not in Path(n).parts
  assert sha(R/n)==h,n
 for k in ('source_hashes','input_hashes','runner_sha256','freeze_sha256'):assert l[k]==m[k]
 assert m['source_hashes']==read(P/'runtime-sources.json')
 assert m['gold_records_for_oracle_arms'] and m['gold_query_interpretations_for_oracle_query']
 assert not m['final_answer_references_mounted'] and not m['prior_model_outputs_mounted'] and not m['training']
 assert m['dedicated_output_volume'] and m['planned_answers']==256 and m['planned_extractions']==16
 assert m['hard_timeout_seconds']==1200 and m['retries']==0
 assert set(m['input_hashes'])=={'runtime-config.json','static-inputs.json','extraction-inputs.json','questions.json','gate-ids.json'}
 assert sha(P/'freeze.json')==l['freeze_sha256']
 for files in (read(P/'freeze.json')['files'],read(P/'protected.json')):
  for n,h in files.items():assert sha(ROOT/n)==h,n
 for n,h in l['source_hashes'].items():assert sha(R/'source-snapshot'/n)==h
 assert sha(R/'source-snapshot/modal-runners/modal-reader-factor.py')==l['runner_sha256']
 for n,h in l['input_hashes'].items():assert sha(P/n)==h
 tok=AutoTokenizer.from_pretrained(cfg['model_id'],revision=cfg['model_revision'],local_files_only=True)
 rt=read(R/'runtime.json');tv=read(R/'tensor-verification.json')
 assert rt['model_revision']==cfg['model_revision'] and rt['template_sha256']==digest(tok.chat_template)
 assert rt['torch'].split('+')[0]=='2.7.1' and rt['transformers']=='4.55.2' and rt['peft']=='0.17.0'
 assert rt['dtype']=='float32' and rt['attention']=='math' and not rt['tf32'] and rt['trainable_parameters']==0
 assert tv['status']=='PASS' and tv['before']==tv['after']==rt['tensor_hashes_before']=={'base':cfg['base_tensors'],'adapter':cfg['adapter_tensors']}
 streams=read(P/'extraction-inputs.json');sm={x['id']:x for x in streams};qs=read(P/'questions.json');st={x['request_id']:x for x in read(P/'static-inputs.json')}
 xs=read(R/'extractions.json');cs=read(R/'captures.json');ds=read(R/'derived-inputs.json');account=defaultdict(Counter)
 def capture(c,row,arm):
  assert c['id']==row['id'] and c['arm']==arm and c['messages']==row['messages']
  assert c['input_tokens']==len(answer_prefix_ids(tok,c['messages']))
  assert 0<len(c['token_ids'])<=192 and tok.eos_token_id not in c['token_ids'][:-1]
  for k,v in strict_body_capture(tok,c['token_ids'],tok.eos_token_id).items():assert c[k]==v,(c['id'],arm,k)
  assert c['fresh_prefill'] and c['actual_forwarded_tokens']==c['input_tokens']+len(c['token_ids'])-int(c['ended_at_eos'])
  assert c['input_tokens']+192<=8192
  a=account[arm];a['calls']+=1;a['input_tokens']+=c['input_tokens'];a['generated_tokens']+=len(c['token_ids']);a['forwarded_tokens']+=c['actual_forwarded_tokens'];a['generation_seconds']+=c['elapsed_seconds']
 assert len(xs)==16 and len(cs)==256 and len(ds)==64
 for c,row in zip(xs,streams):
  capture(c,row,'extract');parsed=parse_record(c['text'],row['history'])
  if not c['ended_at_eos'] or not c['body_structurally_valid']:parsed={'valid':False,'record':{'status':'unknown','value':None,'turn':None,'quote':None},'error':'invalid or incomplete body'}
  assert c['parsed']==parsed
 xm={x['id']:x for x in xs};dm={x['id']:x for x in ds}
 for q,d in zip(qs,ds):
  rec=xm[q['stream_id']]['parsed']['record']
  assert d=={'id':q['id'],'arm':'extracted_fact','request_id':'extracted_fact:'+q['id'],'messages':record_messages(q['property'],rec,q['query']),'record':rec}
 expected=[]
 for i,q in enumerate(qs):
  arms=['direct','oracle_fact','extracted_fact','oracle_query'];arms=arms[i%4:]+arms[:i%4]
  expected.extend((arm,dm[q['id']] if arm=='extracted_fact' else st[arm+':'+q['id']]) for arm in arms)
 for c,(arm,row) in zip(cs,expected):capture(c,row,arm)
 reused=read(P/'reused-ids.json');old={c['id']:c for c in read(HERE.parent/'260911-reader-sft-v2/run/captures.json') if c['arm']=='adapted'}
 reproduced=[]
 for c in cs:
  if c['arm']=='direct' and c['id'] in reused:
   assert all(c[k]==old[c['id']][k] for k in ('messages','token_ids','text'));reproduced.append(c['id'])
 assert len(reproduced)==12
 gates=read(P/'gate-ids.json');checks=read(R/'cache-checks.json');expected_gate=[(a,cid) for a in ('direct','oracle_fact','oracle_query','extract','extracted_fact') for cid in gates[a]]
 assert [(c['arm'],c['id']) for c in checks]==expected_gate
 gate_account=defaultdict(Counter)
 for c in checks:
  a,cid=c['arm'],c['id'];row=sm[cid] if a=='extract' else dm[cid] if a=='extracted_fact' else st[a+':'+cid]
  assert c['messages']==row['messages'] and c['pass']==(c['initial_argmax_equal'] and c['cached_tokens']==c['fresh_tokens']) and c['pass']
  n=len(answer_prefix_ids(tok,row['messages']));ac=gate_account[a];ac['fixtures']+=1
  for path in ('cached','fresh'):
   ts=c[path+'_tokens'];assert 0<len(ts)<=16;steps=len(ts)-int(ts[-1]==tok.eos_token_id)
   ac[path+'_generated_tokens']+=len(ts);ac[path+'_forwarded_tokens']+=n+steps if path=='cached' else sum(n+i for i in range(steps+1))
 assert s['status']=='collection_complete' and s['answers']==256 and s['extractions']==16 and s['optimizer_steps']==s['training_labels']==0
 assert s['gate']==read(R/'cache-verdict.json') and s['gate']['pass'] and s['gate']['checked']==25
 assert s['body_valid_answers']==sum(c['body_structurally_valid'] for c in cs) and s['answers_within_90_words']==sum(c['within_90_words'] for c in cs)
 return {'status':'PASS','answers':256,'extractions':16,'passed_cache_checks':25,'unchanged_frozen_tensors':True,'identical_prior_direct_answers':reproduced,'protected_files':len(read(P/'protected.json')),'accounting_by_arm':dict(account),'cache_gate_accounting_by_arm':dict(gate_account)}
if __name__=='__main__':
 r=verify()
 if (HERE/'result-manifest.json').exists():assert r==read(R/'artifact-verification.json')
 else:(R/'artifact-verification.json').write_text(json.dumps(r,indent=2)+'\n')
 print(json.dumps(r,indent=2))

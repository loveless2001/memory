"""Verify captured prompts/tokens, matched training and saved continuations."""
import hashlib,json,sys,math
from pathlib import Path
from collections import Counter,defaultdict
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];P=HERE/'preflight';R=HERE/'run';sys.path.insert(0,str(ROOT))
from experiments.context_policy.preflight import digest
from experiments.context_policy.broader_protocol import answer_prefix_ids,strict_body_capture
from experiments.context_policy.reader_sft_protocol import encode_answer,learning_rate
from experiments.context_policy.reader_decision_protocol import parse_decision,render_decision
from transformers import AutoTokenizer
read=lambda p:json.loads(p.read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()

def verify():
 launch=read(R/'launch.json');m=read(R/'manifest.json');status=read(R/'status.json');cfg=read(P/'runtime-config.json')
 for n,h in read(R/'artifact-hashes.json').items():
  assert not Path(n).is_absolute() and '..' not in Path(n).parts;assert sha(R/n)==h,n
 for k in ('source_hashes','input_hashes','runner_sha256','freeze_sha256'):assert launch[k]==m[k]
 assert m['source_hashes']==read(P/'runtime-sources.json')
 assert m['training_targets_mounted'] and m['training'] and m['dedicated_output_volume']
 assert not m['evaluation_oracle_metadata_mounted'] and not m['final_answer_references_mounted'] and not m['prior_model_outputs_mounted']
 assert m['planned_answers']==1680 and m['planned_training_runs']==2 and m['planned_examples_per_adapter']==512
 assert m['hard_timeout_seconds']==3600 and m['retries']==0
 assert set(m['input_hashes'])=={'runtime-config.json','train-inputs.json','eval-inputs.json','training-order.json','gate-ids.json'}
 assert sha(P/'freeze.json')==launch['freeze_sha256']
 for files in (read(P/'freeze.json')['files'],read(P/'protected.json')):
  for n,h in files.items():assert sha(ROOT/n)==h,n
 for n,h in launch['source_hashes'].items():assert sha(R/'source-snapshot'/n)==h,n
 assert sha(R/'source-snapshot/modal-runners/modal-reader-decision.py')==launch['runner_sha256']
 for n,h in launch['input_hashes'].items():assert sha(P/n)==h,n
 tok=AutoTokenizer.from_pretrained(cfg['model_id'],revision=cfg['model_revision'],local_files_only=True)
 runtime=read(R/'runtime.json');initial={'base':cfg['prior_base_tensors'],'adapter':cfg['prior_adapter_tensors']}
 assert runtime['model_revision']==cfg['model_revision'] and runtime['template_sha256']==digest(tok.chat_template)
 assert runtime['torch'].split('+')[0]=='2.7.1' and runtime['transformers']=='4.55.2' and runtime['peft']=='0.17.0'
 assert runtime['inference_dtype']=='float32' and runtime['attention']=='math' and not runtime['tf32']
 assert runtime['initial_tensors']==initial and runtime['base_trainable_parameters']==runtime['initial_trainable_parameters']==0
 train=read(P/'train-inputs.json');tm={r['id']:r for r in train};inputs=read(P/'eval-inputs.json');im={r['id']:r for r in inputs};orders=read(P/'training-order.json')
 for row in train:
  for fmt in ('prose','decision'):
   r=row[fmt];e=encode_answer(tok,r['messages'],r['answer'],max_answer_tokens=cfg['output_cap_by_format'][fmt])
   assert all(r[k]==v for k,v in e.items())
  assert row['prose']['messages'][1]==row['decision']['messages'][1]
 caps=read(R/'captures.json') if (R/'captures.json').exists() else [];checks=read(R/'cache-checks.json');training=read(R/'training.json') if (R/'training.json').exists() else {};reload=read(R/'reload-verification.json') if (R/'reload-verification.json').exists() else {}
 expected=[]
 for i,row in enumerate(inputs):
  arms=['current_direct','current_decision'];arms=arms[i%2:]+arms[:i%2];expected.extend((a,row) for a in arms)
 for a in ('trained_direct','trained_decision'):expected.extend((a,r) for r in inputs)
 assert len(caps)<=1680
 old={c['id']:c for c in read(HERE.parent/'260911-reader-sft-v2/run/captures.json') if c['arm']=='adapted'}
 old.update({c['id']:c for c in read(HERE.parent/'260911-reader-factor/run/captures.json') if c['arm']=='direct'})
 case_map={c['id']:c for c in read(P/'eval-cases.json')};account=defaultdict(Counter);reproduced=[];renders=[]
 for c,(arm,row) in zip(caps,expected):
  fmt='decision' if arm.endswith('decision') else 'prose';inp=row[fmt];cap=cfg['output_cap_by_format'][fmt]
  assert c['id']==row['id'] and c['arm']==arm and c['format']==fmt and c['messages']==inp['messages']
  assert c['input_tokens']==inp['input_tokens']==len(answer_prefix_ids(tok,inp['messages'])) and c['output_cap']==cap
  assert 0<len(c['token_ids'])<=cap and tok.eos_token_id not in c['token_ids'][:-1]
  for k,v in strict_body_capture(tok,c['token_ids'],tok.eos_token_id).items():assert c[k]==v,(arm,c['id'],k)
  assert c['fresh_prefill'] and c['actual_forwarded_tokens']==c['input_tokens']+len(c['token_ids'])-int(c['ended_at_eos'])
  assert c['input_tokens']+cap<=8192
  adapter=cfg['prior_adapter_files']['adapter_model.safetensors'] if arm.startswith('current') else training[arm]['adapter_sha256']
  assert c['adapter_sha256']==adapter
  if arm=='current_direct' and row['split']=='regression':
   assert all(c[k]==old[c['id']][k] for k in ('messages','token_ids','text'));reproduced.append(c['id'])
  a=account[arm];a['calls']+=1;a['input_tokens']+=c['input_tokens'];a['generated_tokens']+=len(c['token_ids']);a['forwarded_tokens']+=c['actual_forwarded_tokens'];a['generation_seconds']+=c['elapsed_seconds']
  if fmt=='decision':
   case=case_map[c['id']];p=parse_decision(c['text'],case['history'],case['query'])
   if not c['ended_at_eos'] or not c['body_structurally_valid']:p={'valid':False,'record':None,'error':'invalid or incomplete model body'}
   text=render_decision(p);renders.append({'id':c['id'],'arm':arm,'parsed':p,'rendered_text':text,'within_90_words':len(text.split())<=90,'rendered_tokens':len(tok.encode(text,add_special_tokens=False)),'capture_text_sha256':digest(c['text'])})
 gates=read(P/'gate-ids.json');expected_gates=[(a,cid) for a in cfg['arms'] for cid in gates]
 assert [(c['arm'],c['id']) for c in checks]==expected_gates[:len(checks)]
 gate_account=defaultdict(Counter)
 for c in checks:
  arm=c['arm'];fmt='decision' if arm.endswith('decision') else 'prose';inp=im[c['id']][fmt]
  assert c['format']==fmt and c['messages']==inp['messages']
  assert c['pass']==(c['initial_argmax_equal'] and c['cached_tokens']==c['fresh_tokens'])
  adapter=cfg['prior_adapter_files']['adapter_model.safetensors'] if arm.startswith('current') else training[arm]['adapter_sha256'];assert c['adapter_sha256']==adapter
  a=gate_account[arm];a['fixtures']+=1;n=inp['input_tokens']
  for path in ('cached','fresh'):
   ts=c[path+'_tokens'];assert 0<len(ts)<=16;steps=len(ts)-int(ts[-1]==tok.eos_token_id)
   a[path+'_generated_tokens']+=len(ts);a[path+'_forwarded_tokens']+=n+steps if path=='cached' else sum(n+i for i in range(steps+1))
 step_counts={}
 for arm in ('trained_direct','trained_decision'):
  fmt='decision' if arm.endswith('decision') else 'prose';sf=R/(arm+'-steps.json');steps=read(sf) if sf.exists() else [];seen=[]
  for i,s in enumerate(steps):
   assert s['step']==i+1 and s['epoch']==i//32+1 and s['example_ids']==orders[i//32][i%32*16:(i%32+1)*16]
   assert s['learning_rate']==learning_rate(i+1,64,cfg['learning_rate'],cfg['warmup_steps'])
   assert s['all_gradients_finite'] and s['only_adapter_gradients']
   assert all(math.isfinite(s[k]) and s[k]>=0 for k in ('mean_answer_loss','min_answer_loss','max_answer_loss','gradient_norm_before_clip','elapsed_seconds'))
   seen+=s['example_ids']
  step_counts[arm]=len(steps)
  if arm in training:
   t=training[arm];assert len(steps)==t['optimizer_steps']==64 and seen==orders[0]+orders[1]
   assert t['examples_seen']==1024 and t['unique_examples']==512 and t['epochs']==2 and t['format']==fmt
   assert t['exposure_order_sha256']==digest(seen)
   assert t['answer_target_tokens']==2*sum(r[fmt]['supervised_tokens'] for r in train) and t['masked_prefix_tokens']==2*sum(r[fmt]['prefix_tokens'] for r in train)
   assert t['initial_tensors']==initial and t['final_tensors']['base']==initial['base'] and t['final_tensors']['adapter']!=initial['adapter']
   assert not t['base_parameter_training'] and not t['base_buffer_training'] and not t['evaluation_references_mounted'] and t['routing_labels']==0
   assert t['initial_adapter_sha256']==cfg['prior_adapter_files']['adapter_model.safetensors'] and t['checkpoint_selection']=='fixed_final_after_two_epochs'
   ap=R/'adapters'/arm;assert sha(ap/'adapter_model.safetensors')==t['adapter_sha256']
   assert len(t['trainable_names'])==144 and all('lora_' in n and ('q_proj' in n or 'v_proj' in n) for n in t['trainable_names'])
   ac=read(ap/'adapter_config.json')
   for k,v in cfg['lora'].items():assert (set(ac[k])==set(v) if isinstance(v,list) else ac[k]==v),k
   from safetensors import safe_open
   with safe_open(ap/'adapter_model.safetensors',framework='pt',device='cpu') as f:
    assert set(f.keys())=={n.replace('.default.','.') for n in t['trainable_names']}
    assert sum(f.get_tensor(n).numel() for n in f.keys())==t['trainable_parameters']
  if arm in reload:
   v=reload[arm];assert v['status']=='PASS' and v['saved_tensor_equality'] and v['trainable_parameters']==0
   assert v['tensors']==training[arm]['final_tensors'] and v['adapter_sha256']==training[arm]['adapter_sha256']
 if (R/'baseline-verification.json').exists():
  b=read(R/'baseline-verification.json');assert b['status']=='PASS' and b['captures']==840 and b['before']==b['after']==initial
 snapshot=HERE/'review-snapshot';snapshot_verified=None
 if (snapshot/'verification.json').exists():
  sv=read(snapshot/'verification.json');assert sv['status']=='PASS' and sv['both_fixed_trainings_complete']
  for n,h in sv['files'].items():assert sha(snapshot/n)==h,n
  sc=read(snapshot/'captures.json');assert len(sc)==sv['captures'] and caps[:len(sc)]==sc
  assert read(snapshot/'training.json')==training
  rm={(r['arm'],r['id']):r for r in renders}
  for r in read(snapshot/'rendered-decisions.json'):
   assert all(rm[r['arm'],r['id']][k]==v for k,v in r.items())
  snapshot_verified=len(sc)
 complete=status['status']=='collection_complete'
 if complete:
  assert len(caps)==1680 and len(checks)==80 and all(c['pass'] for c in checks)
  assert len(reproduced)==260 and len(renders)==840 and len(training)==len(reload)==2 and all(v['tensors_unchanged_after_eval'] for v in reload.values())
  assert status['training_runs']==2 and status['optimizer_steps_total']==128 and status['training_exposures_total']==2048
  assert status['gate']==read(R/'cache-verdict.json') and status['gate']['pass']
  assert status['body_valid']==sum(c['body_structurally_valid'] for c in caps)
  assert status['prose_answers_within_90_words']==sum(c['within_90_words'] for c in caps if c['format']=='prose')
  assert training['trained_direct']['exposure_order_sha256']==training['trained_decision']['exposure_order_sha256']
 result={'status':'PASS','remote_status':status['status'],'complete':complete,'unchanged_review_snapshot_captures':snapshot_verified,'captures':len(caps),'cache_checks':len(checks),'passed_cache_checks':sum(c['pass'] for c in checks),
  'optimizer_steps':step_counts,'training_runs_complete':len(training),'saved_reloads_verified':len(reload),'identical_prior_direct_answers':len(reproduced),'reproduced_ids':reproduced,
  'protected_files':len(read(P/'protected.json')),'accounting_by_arm':dict(account),'cache_gate_accounting_by_arm':dict(gate_account),
  'schema_valid_decisions':{a:sum(x['parsed']['valid'] for x in renders if x['arm']==a) for a in ('current_decision','trained_decision')},
  'rendered_answers_within_90_words':sum(r['within_90_words'] for r in renders)}
 return result,renders
if __name__=='__main__':
 result,renders=verify()
 if (HERE/'result-manifest.json').exists():assert result==read(R/'artifact-verification.json') and renders==read(HERE/'rendered-decisions.json')
 else:
  (R/'artifact-verification.json').write_text(json.dumps(result,indent=2)+'\n');(HERE/'rendered-decisions.json').write_text(json.dumps(renders,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps(result,indent=2))

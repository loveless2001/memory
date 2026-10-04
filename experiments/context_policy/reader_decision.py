"""Two matched v2 continuations and four frozen reader conditions in one bounded app."""
import gc,hashlib,time
from pathlib import Path
import torch
from torch.nn.attention import SDPBackend,sdpa_kernel
from .cache_session import AppendOnlySession,ReaderIdentity
from .broader_protocol import answer_prefix_ids,strict_body_capture
from .preflight import canonical,digest,paired_greedy
from .reader_sft import tensor_hash
from .reader_sft_protocol import encode_answer,answer_loss,learning_rate,cast_training_parameters

def run(config,payload,root,commit,deadline):
 from transformers import AutoTokenizer,AutoModelForCausalLM
 from peft import PeftModel
 from safetensors.torch import load_file
 import transformers,peft
 root=Path(root);torch.set_num_threads(4);torch.manual_seed(config['seed'])
 torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False;torch.set_float32_matmul_precision('highest')
 tok=AutoTokenizer.from_pretrained(config['model_id'],revision=config['model_revision'],local_files_only=True)
 inputs=payload['eval-inputs.json'];im={r['id']:r for r in inputs};training=payload['train-inputs.json'];tm={r['id']:r for r in training};orders=payload['training-order.json'];gates=payload['gate-ids.json']
 assert len(inputs)==420 and len(training)==512 and len(gates)==20
 assert len(orders)==2 and all(len(o)==512 and set(o)==set(tm) for o in orders)
 for row in training:
  for fmt in ('prose','decision'):
   r=row[fmt];e=encode_answer(tok,r['messages'],r['answer'],max_answer_tokens=config['output_cap_by_format'][fmt]);assert all(r[k]==v for k,v in e.items())
 for n,h in config['prior_adapter_files'].items():assert hashlib.sha256((Path('/root/prior-adapter')/n).read_bytes()).hexdigest()==h
 def load(adapter='/root/prior-adapter',trainable=False):
  base=AutoModelForCausalLM.from_pretrained(config['model_id'],revision=config['model_revision'],local_files_only=True,torch_dtype=torch.bfloat16,attn_implementation='sdpa').to('cuda')
  assert base.config._commit_hash==config['model_revision']
  return PeftModel.from_pretrained(base,adapter,is_trainable=trainable,local_files_only=True).float().eval()
 model=load();model.requires_grad_(False)
 before={'base':tensor_hash(model),'adapter':tensor_hash(model,adapter=True)}
 assert before=={'base':config['prior_base_tensors'],'adapter':config['prior_adapter_tensors']}
 runtime={'model_revision':config['model_revision'],'torch':torch.__version__,'transformers':transformers.__version__,'peft':peft.__version__,
  'template_sha256':digest(tok.chat_template),'gpu':torch.cuda.get_device_name(),'inference_dtype':'float32','attention':'math','tf32':False,'initial_tensors':before,
  'base_trainable_parameters':0,'initial_trainable_parameters':0}
 (root/'runtime.json').write_bytes(canonical(runtime));commit()
 captures=[];checks=[];training_results={};reload_results={};baseline_sha=config['prior_adapter_files']['adapter_model.safetensors']
 def fmt_for(arm):return 'decision' if arm.endswith('decision') else 'prose'
 @torch.inference_mode()
 def check(row,arm,adapter_sha):
  deadline();fmt=fmt_for(arm);messages=row[fmt]['messages'];ids=answer_prefix_ids(tok,messages);fresh_ids=list(ids)
  ident=ReaderIdentity(config['model_revision'],adapter_sha,digest(tok.chat_template),'fp32-decision-'+arm)
  sess=AppendOnlySession(model,ident,last_logit_only=True);cached=sess.append_transcript(ids,ident)[0][-1]
  def fresh():return model(input_ids=torch.tensor([fresh_ids],device='cuda'),use_cache=False,logits_to_keep=1).logits[0,-1]
  full=fresh();initial=int(cached.argmax())==int(full.argmax())
  def cs(token):ids.append(token);return sess.append_transcript(ids,ident)[0][-1]
  def fs(token):fresh_ids.append(token);return fresh()
  ct,ft=paired_greedy(cached,full,cs,fs,tok.eos_token_id,deadline,limit=16)
  c={'id':row['id'],'arm':arm,'format':fmt,'messages':messages,'initial_argmax_equal':initial,'cached_tokens':ct,'fresh_tokens':ft,'pass':initial and ct==ft,'adapter_sha256':adapter_sha}
  checks.append(c);(root/'cache-checks.json').write_bytes(canonical(checks));commit();return c['pass']
 @torch.inference_mode()
 def generate(row,arm,adapter_sha):
  deadline();fmt=fmt_for(arm);messages=row[fmt]['messages'];cap=config['output_cap_by_format'][fmt]
  start=time.monotonic();ids=answer_prefix_ids(tok,messages);n=len(ids);assert n==row[fmt]['input_tokens'] and n+cap<=8192
  ident=ReaderIdentity(config['model_revision'],adapter_sha,digest(tok.chat_template),'fp32-decision-'+arm)
  sess=AppendOnlySession(model,ident,8192,last_logit_only=True);logits=sess.append_transcript(ids,ident)[0][-1];tokens=[]
  for _ in range(cap):
   deadline();token=int(logits.argmax());tokens.append(token)
   if token==tok.eos_token_id:break
   ids.append(token);logits=sess.append_transcript(ids,ident)[0][-1]
  c=strict_body_capture(tok,tokens,tok.eos_token_id)
  c.update(id=row['id'],arm=arm,format=fmt,messages=messages,input_tokens=n,actual_forwarded_tokens=sess.fresh_tokens,fresh_prefill=True,
   adapter_sha256=adapter_sha,output_cap=cap,elapsed_seconds=time.monotonic()-start)
  captures.append(c);(root/'captures.json').write_bytes(canonical(captures));commit()
  if len(captures)%20==0:print('CAPTURE '+str(len(captures))+'/1680 '+arm+' '+row['id'],flush=True)
 with sdpa_kernel(SDPBackend.MATH):
  for arm in ('current_direct','current_decision'):
   for cid in gates:
    if not check(im[cid],arm,baseline_sha):return {'status':'initial_cache_gate_failed','captures':0,'training_runs':0}
  print('INITIAL_CACHE_GATES 40/40 PASS',flush=True)
  for i,row in enumerate(inputs):
   arms=['current_direct','current_decision'];arms=arms[i%2:]+arms[:i%2]
   for arm in arms:generate(row,arm,baseline_sha)
 assert {'base':tensor_hash(model),'adapter':tensor_hash(model,adapter=True)}==before
 (root/'baseline-verification.json').write_bytes(canonical({'status':'PASS','before':before,'after':before,'captures':840}));commit()
 model=None;gc.collect();torch.cuda.empty_cache()
 for arm in ('trained_direct','trained_decision'):
  deadline();torch.manual_seed(config['seed']);fmt=fmt_for(arm)
  model=load(trainable=True)
  initial={'base':tensor_hash(model),'adapter':tensor_hash(model,adapter=True)};assert initial==before
  trainable=[(n,p) for n,p in model.named_parameters() if p.requires_grad]
  assert trainable and all('lora_' in n and ('q_proj' in n or 'v_proj' in n) for n,p in trainable)
  cast_training_parameters(model);assert tensor_hash(model)==before['base']
  model.config.use_cache=False;model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={'use_reentrant':False});model.enable_input_require_grads();model.train()
  optimizer=torch.optim.AdamW([p for _,p in trainable],lr=config['learning_rate'],weight_decay=config['weight_decay'])
  steps=[];seen=[];target_tokens=0;prefix_tokens=0;step=0;started=time.monotonic()
  with sdpa_kernel(SDPBackend.MATH):
   for epoch,order in enumerate(orders):
    for offset in range(0,len(order),16):
     deadline();batch=order[offset:offset+16];assert len(batch)==16
     step+=1;lr=learning_rate(step,64,config['learning_rate'],config['warmup_steps'])
     for group in optimizer.param_groups:group['lr']=lr
     optimizer.zero_grad(set_to_none=True);losses=[];step_started=time.monotonic()
     for cid in batch:
      deadline();r=tm[cid][fmt]
      ids=torch.tensor([r['input_ids']],device='cuda');positions=torch.tensor(r['prediction_positions'],device='cuda');labels=torch.tensor(r['target_ids'],device='cuda')
      logits=model(input_ids=ids,use_cache=False,logits_to_keep=positions).logits[0];loss=answer_loss(logits,labels)
      assert torch.isfinite(loss);(loss/16).backward();losses.append(float(loss.detach()));seen.append(cid)
      target_tokens+=len(r['target_ids']);prefix_tokens+=r['prefix_tokens'];del ids,positions,labels,logits,loss
     assert all(p.grad is not None and torch.isfinite(p.grad).all() for _,p in trainable)
     assert any(p.grad.abs().max()>0 for _,p in trainable)
     assert all(p.grad is None for p in model.parameters() if not p.requires_grad)
     norm=torch.nn.utils.clip_grad_norm_([p for _,p in trainable],config['gradient_clip_norm']);assert torch.isfinite(norm);optimizer.step()
     entry={'step':step,'epoch':epoch+1,'example_ids':batch,'learning_rate':lr,'mean_answer_loss':sum(losses)/16,'min_answer_loss':min(losses),'max_answer_loss':max(losses),
      'gradient_norm_before_clip':float(norm),'all_gradients_finite':True,'only_adapter_gradients':True,'elapsed_seconds':time.monotonic()-step_started}
     steps.append(entry);(root/(arm+'-steps.json')).write_bytes(canonical(steps));commit()
     print('TRAIN '+arm+' '+str(step)+'/64 loss='+str(round(entry['mean_answer_loss'],6)),flush=True)
  optimizer.zero_grad(set_to_none=True);del optimizer
  assert step==64 and seen==orders[0]+orders[1]
  model.gradient_checkpointing_disable();model.disable_input_require_grads();model.config.use_cache=True;model.eval();model.float()
  final={'base':tensor_hash(model),'adapter':tensor_hash(model,adapter=True)};assert final['base']==before['base'] and final['adapter']!=before['adapter']
  adapter_dir=root/'adapters'/arm;model.save_pretrained(adapter_dir,safe_serialization=True)
  adapter_sha=hashlib.sha256((adapter_dir/'adapter_model.safetensors').read_bytes()).hexdigest()
  training_results[arm]={'status':'training_complete','format':fmt,'optimizer_steps':64,'epochs':2,'examples_seen':1024,'unique_examples':512,'exposure_order_sha256':digest(seen),
   'answer_target_tokens':target_tokens,'masked_prefix_tokens':prefix_tokens,'training_seconds':time.monotonic()-started,
   'trainable_parameters':sum(p.numel() for _,p in trainable),'trainable_names':[n for n,p in trainable],'initial_tensors':initial,'final_tensors':final,
   'adapter_sha256':adapter_sha,'initial_adapter_sha256':baseline_sha,'base_parameter_training':False,'base_buffer_training':False,'evaluation_references_mounted':False,
   'checkpoint_selection':'fixed_final_after_two_epochs','routing_labels':0}
  (root/'training.json').write_bytes(canonical(training_results));commit()
  del trainable;model=None;gc.collect();torch.cuda.empty_cache();deadline()
  model=load(str(adapter_dir));model.requires_grad_(False)
  reloaded={'base':tensor_hash(model),'adapter':tensor_hash(model,adapter=True)};assert reloaded==final
  saved=load_file(str(adapter_dir/'adapter_model.safetensors'));loaded={n.replace('.default.','.'):p.detach().cpu() for n,p in model.named_parameters() if 'lora_' in n}
  assert set(saved)==set(loaded) and all(torch.equal(saved[n].float(),loaded[n].float()) for n in saved)
  del saved,loaded
  reload_results[arm]={'status':'PASS','tensors':reloaded,'adapter_sha256':adapter_sha,'saved_tensor_equality':True,'trainable_parameters':0}
  (root/'reload-verification.json').write_bytes(canonical(reload_results));commit()
  with sdpa_kernel(SDPBackend.MATH):
   for cid in gates:
    if not check(im[cid],arm,adapter_sha):return {'status':arm+'_cache_gate_failed','captures':len(captures),'training_runs':len(training_results)}
   print('TRAINED_CACHE_GATE '+arm+' 20/20 PASS',flush=True)
   for row in inputs:generate(row,arm,adapter_sha)
  assert {'base':tensor_hash(model),'adapter':tensor_hash(model,adapter=True)}==final
  reload_results[arm]['tensors_unchanged_after_eval']=True;(root/'reload-verification.json').write_bytes(canonical(reload_results));commit()
  model=None;gc.collect();torch.cuda.empty_cache()
 gate={'pass':len(checks)==80 and all(c['pass'] for c in checks),'checked':len(checks),'decode_limit':16}
 (root/'cache-verdict.json').write_bytes(canonical(gate));commit()
 return {'status':'collection_complete','captures':len(captures),'training_runs':2,'optimizer_steps_total':128,'training_exposures_total':2048,
  'gate':gate,'body_valid':sum(c['body_structurally_valid'] for c in captures),'prose_answers_within_90_words':sum(c['within_90_words'] for c in captures if c['format']=='prose'),
  'final_structured_answer_rendering':'local deterministic parser and renderer, with every decision semantically reviewed','routing_labels':0}

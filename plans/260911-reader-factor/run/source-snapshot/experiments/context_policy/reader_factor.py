"""One frozen inference-only factorization of evidence and answer selection."""
import time,hashlib
from pathlib import Path
import torch
from torch.nn.attention import SDPBackend,sdpa_kernel
from .cache_session import AppendOnlySession,ReaderIdentity
from .broader_protocol import answer_prefix_ids,strict_body_capture
from .preflight import canonical,digest,paired_greedy
from .reader_sft import tensor_hash
from .reader_factor_protocol import parse_record,record_messages

@torch.inference_mode()
def run(cfg,payload,root,commit,deadline):
 from transformers import AutoTokenizer,AutoModelForCausalLM
 from peft import PeftModel
 import transformers,peft
 root=Path(root);torch.set_num_threads(4);torch.manual_seed(cfg['seed'])
 torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False;torch.set_float32_matmul_precision('highest')
 tok=AutoTokenizer.from_pretrained(cfg['model_id'],revision=cfg['model_revision'],local_files_only=True)
 for n,h in cfg['adapter_files'].items():assert hashlib.sha256((Path('/root/adapter')/n).read_bytes()).hexdigest()==h
 model=AutoModelForCausalLM.from_pretrained(cfg['model_id'],revision=cfg['model_revision'],local_files_only=True,torch_dtype=torch.bfloat16,attn_implementation='sdpa').to('cuda')
 assert model.config._commit_hash==cfg['model_revision']
 model=PeftModel.from_pretrained(model,'/root/adapter',is_trainable=False,local_files_only=True).float().eval();model.requires_grad_(False)
 before={'base':tensor_hash(model),'adapter':tensor_hash(model,adapter=True)}
 assert before['base']==cfg['base_tensors'] and before['adapter']==cfg['adapter_tensors']
 runtime={'model_revision':cfg['model_revision'],'torch':torch.__version__,'transformers':transformers.__version__,'peft':peft.__version__,
  'template_sha256':digest(tok.chat_template),'gpu':torch.cuda.get_device_name(),'dtype':'float32','attention':'math','tf32':False,'trainable_parameters':0,'tensor_hashes_before':before}
 (root/'runtime.json').write_bytes(canonical(runtime));commit()
 identity=ReaderIdentity(cfg['model_revision'],cfg['adapter_files']['adapter_model.safetensors'],digest(tok.chat_template),'fp32-factor')
 static={r['request_id']:r for r in payload['static-inputs.json']};streams=payload['extraction-inputs.json'];sm={s['id']:s for s in streams}
 questions=payload['questions.json'];gates=payload['gate-ids.json'];checks=[];captures=[];extracts=[]
 def check(row,arm):
  deadline();ids=answer_prefix_ids(tok,row['messages']);fresh_ids=list(ids)
  sess=AppendOnlySession(model,identity,last_logit_only=True);cached=sess.append_transcript(ids,identity)[0][-1]
  def fresh():return model(input_ids=torch.tensor([fresh_ids],device='cuda'),use_cache=False,logits_to_keep=1).logits[0,-1]
  full=fresh();initial=int(cached.argmax())==int(full.argmax())
  def cs(token):ids.append(token);return sess.append_transcript(ids,identity)[0][-1]
  def fs(token):fresh_ids.append(token);return fresh()
  ct,ft=paired_greedy(cached,full,cs,fs,tok.eos_token_id,deadline,limit=16)
  result={'id':row['id'],'arm':arm,'messages':row['messages'],'initial_argmax_equal':initial,'cached_tokens':ct,'fresh_tokens':ft,'pass':initial and ct==ft}
  checks.append(result);(root/'cache-checks.json').write_bytes(canonical(checks));commit()
  return result['pass']
 def generate(row,arm):
  deadline();start=time.monotonic();ids=answer_prefix_ids(tok,row['messages']);n=len(ids)
  assert n+192<=cfg['active_context_max_tokens']
  sess=AppendOnlySession(model,identity,cfg['active_context_max_tokens'],last_logit_only=True)
  logits=sess.append_transcript(ids,identity)[0][-1];tokens=[]
  for _ in range(192):
   deadline();token=int(logits.argmax());tokens.append(token)
   if token==tok.eos_token_id:break
   ids.append(token);logits=sess.append_transcript(ids,identity)[0][-1]
  c=strict_body_capture(tok,tokens,tok.eos_token_id)
  c.update(id=row['id'],arm=arm,messages=row['messages'],input_tokens=n,actual_forwarded_tokens=sess.fresh_tokens,fresh_prefill=True,elapsed_seconds=time.monotonic()-start)
  return c
 with sdpa_kernel(SDPBackend.MATH):
  for arm in ('direct','oracle_fact','oracle_query','extract'):
   for cid in gates[arm]:
    row=sm[cid] if arm=='extract' else static[arm+':'+cid]
    if not check(row,arm):return {'status':'static_cache_gate_failed','answers':0,'extractions':0,'training_labels':0}
  print('STATIC_CACHE_GATE 20/20 PASS',flush=True)
  for s in streams:
   c=generate(s,'extract');parsed=parse_record(c['text'],s['history'])
   if not c['ended_at_eos'] or not c['body_structurally_valid']:parsed={'valid':False,'record':{'status':'unknown','value':None,'turn':None,'quote':None},'error':'invalid or incomplete body'}
   c['parsed']=parsed;extracts.append(c);(root/'extractions.json').write_bytes(canonical(extracts));commit()
   print('EXTRACT '+str(len(extracts))+'/16 '+s['id'],flush=True)
  em={c['id']:c for c in extracts};derived={}
  for q in questions:
   r=em[q['stream_id']]['parsed']['record']
   derived[q['id']]={'id':q['id'],'arm':'extracted_fact','request_id':'extracted_fact:'+q['id'],
     'messages':record_messages(q['property'],r,q['query']),'record':r}
  (root/'derived-inputs.json').write_bytes(canonical(list(derived.values())));commit()
  for cid in gates['extracted_fact']:
   if not check(derived[cid],'extracted_fact'):return {'status':'derived_cache_gate_failed','answers':0,'extractions':len(extracts),'training_labels':0}
  gate={'pass':len(checks)==25 and all(c['pass'] for c in checks),'checked':25,'decode_limit':16}
  (root/'cache-verdict.json').write_bytes(canonical(gate));commit();print('ALL_CACHE_GATES 25/25 PASS',flush=True)
  for i,q in enumerate(questions):
   arms=['direct','oracle_fact','extracted_fact','oracle_query'];arms=arms[i%4:]+arms[:i%4]
   for arm in arms:
    row=derived[q['id']] if arm=='extracted_fact' else static[arm+':'+q['id']]
    c=generate(row,arm);captures.append(c);(root/'captures.json').write_bytes(canonical(captures));commit()
   print('ANSWERS '+str(len(captures))+'/256 '+q['id'],flush=True)
 after={'base':tensor_hash(model),'adapter':tensor_hash(model,adapter=True)};assert after==before
 (root/'tensor-verification.json').write_bytes(canonical({'status':'PASS','before':before,'after':after,'trainable_parameters':0}));commit()
 return {'status':'collection_complete','answers':len(captures),'extractions':len(extracts),'gate':gate,'training_labels':0,'optimizer_steps':0,
  'body_valid_answers':sum(c['body_structurally_valid'] for c in captures),'answers_within_90_words':sum(c['within_90_words'] for c in captures)}

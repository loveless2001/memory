"""One revised-data LoRA run against the frozen preceding adapter."""
import gc,hashlib,time
from pathlib import Path
import torch
from torch.nn.attention import SDPBackend,sdpa_kernel
from .cache_session import AppendOnlySession,ReaderIdentity
from .broader_protocol import answer_prefix_ids,strict_body_capture
from .preflight import canonical,digest,paired_greedy
from .reader_sft_protocol import encode_answer,answer_loss,learning_rate,cast_training_parameters


def tensor_hash(model,adapter=False):
    """Hash complete tensor contents; frozen parameters and buffers include RoPE."""
    rows=[]
    for kind,iterator in (('parameter',model.named_parameters()),('buffer',model.named_buffers())):
        for name,tensor in iterator:
            is_adapter='lora_' in name
            if is_adapter!=adapter:continue
            normalized=name.removeprefix('base_model.model.').replace('.base_layer.','.').replace('.default.','.')
            rows.append((kind+':'+normalized,tensor))
    h=hashlib.sha256();elements=0;names=[]
    for name,tensor in sorted(rows,key=lambda row:row[0]):
        cpu=tensor.detach().to(device='cpu',dtype=torch.float32 if tensor.is_floating_point() else tensor.dtype).contiguous()
        h.update(canonical([name,list(cpu.shape),str(cpu.dtype)]));h.update(memoryview(cpu.numpy()).cast('B'))
        elements+=cpu.numel();names.append(name);del cpu
    return {'sha256':h.hexdigest(),'tensors':len(rows),'elements':elements,'names_sha256':digest(names)}


def run(config,payload,root,commit,deadline):
    from transformers import AutoTokenizer,AutoModelForCausalLM
    from peft import LoraConfig,get_peft_model,PeftModel
    from safetensors.torch import load_file
    import transformers,peft
    root=Path(root);torch.set_num_threads(4);torch.manual_seed(config['seed'])
    tok=AutoTokenizer.from_pretrained(config['model_id'],revision=config['model_revision'],local_files_only=True)
    inputs=payload['eval-inputs.json'];input_map={r['id']:r for r in inputs}
    training=payload['train-inputs.json'];train_map={r['id']:r for r in training};orders=payload['training-order.json']
    gate_ids=payload['gate-ids.json']
    assert len(inputs)==208 and len(training)==512 and len(gate_ids)==20
    assert set(input_map).isdisjoint(train_map)
    assert len(orders)==2 and all(len(o)==512 and set(o)==set(train_map) for o in orders)
    for r in inputs:assert r['input_tokens']==len(answer_prefix_ids(tok,r['messages']))
    for row in training:
        encoded=encode_answer(tok,row['messages'],row['answer'])
        assert all(row[k]==v for k,v in encoded.items())
    torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
    torch.set_float32_matmul_precision('highest')

    def load_base():
        m=AutoModelForCausalLM.from_pretrained(config['model_id'],revision=config['model_revision'],local_files_only=True,
                torch_dtype=torch.bfloat16,attn_implementation='sdpa').to('cuda')
        assert m.config._commit_hash==config['model_revision']
        return m

    model=load_base().float().eval();model.requires_grad_(False)
    base_hash=tensor_hash(model)
    runtime={'model_revision':model.config._commit_hash,'torch':torch.__version__,'transformers':transformers.__version__,
             'peft':peft.__version__,'gpu':torch.cuda.get_device_name(),'template_sha256':digest(tok.chat_template),
             'inference_dtype':'float32','attention':'math','tf32':False,'base_tensors_initial':base_hash,
             'base_parameters':sum(p.numel() for p in model.parameters()),'base_trainable_parameters':0}
    (root/'runtime.json').write_bytes(canonical(runtime));commit()
    captures=[];checks=[]

    @torch.inference_mode()
    def check(row,arm,adapter_sha):
        deadline();ids=answer_prefix_ids(tok,row['messages']);fresh_ids=list(ids)
        ident=ReaderIdentity(config['model_revision'],adapter_sha,digest(tok.chat_template),'fp32-math-reader-sft-'+arm)
        session=AppendOnlySession(model,ident,last_logit_only=True)
        cached=session.append_transcript(ids,ident)[0][-1]
        def fresh():return model(input_ids=torch.tensor([fresh_ids],device='cuda'),use_cache=False,logits_to_keep=1).logits[0,-1]
        full=fresh();initial=int(cached.argmax())==int(full.argmax())
        def cached_step(token):ids.append(token);return session.append_transcript(ids,ident)[0][-1]
        def fresh_step(token):fresh_ids.append(token);return fresh()
        ct,ft=paired_greedy(cached,full,cached_step,fresh_step,tok.eos_token_id,deadline,limit=16)
        result={'id':row['id'],'arm':arm,'initial_argmax_equal':initial,'cached_tokens':ct,'fresh_tokens':ft,
                'pass':initial and ct==ft,'adapter_sha256':adapter_sha}
        checks.append(result);(root/'cache-checks.json').write_bytes(canonical(checks));commit()
        return result['pass']

    @torch.inference_mode()
    def generate(row,arm,adapter_sha):
        deadline();start=time.monotonic();ids=answer_prefix_ids(tok,row['messages']);n=len(ids)
        if n+192>config['active_context_max_tokens']:raise ValueError('evaluation input exceeds context cap')
        ident=ReaderIdentity(config['model_revision'],adapter_sha,digest(tok.chat_template),'fp32-math-reader-sft-'+arm)
        session=AppendOnlySession(model,ident,config['active_context_max_tokens'],last_logit_only=True)
        logits=session.append_transcript(ids,ident)[0][-1];tokens=[]
        for _ in range(config['max_message_output_tokens']):
            deadline();token=int(logits.argmax());tokens.append(token)
            if token==tok.eos_token_id:break
            ids.append(token);logits=session.append_transcript(ids,ident)[0][-1]
        result=strict_body_capture(tok,tokens,tok.eos_token_id)
        result.update(id=row['id'],arm=arm,messages=row['messages'],input_tokens=n,actual_forwarded_tokens=session.fresh_tokens,
                      fresh_prefill=True,adapter_sha256=adapter_sha,elapsed_seconds=time.monotonic()-start)
        captures.append(result);(root/'captures.json').write_bytes(canonical(captures));commit()
        print('CAPTURE '+str(len(captures))+'/416 '+arm+' '+row['id'],flush=True)

    prior_dir=Path('/root/prior-adapter')
    for name,h in config['prior_adapter_files'].items():
        assert hashlib.sha256((prior_dir/name).read_bytes()).hexdigest()==h,name
    prior_sha=config['prior_adapter_files']['adapter_model.safetensors']
    model=PeftModel.from_pretrained(model,str(prior_dir),is_trainable=False,local_files_only=True).float().eval()
    model.requires_grad_(False)
    assert tensor_hash(model)==base_hash==config['prior_base_tensors']
    assert tensor_hash(model,adapter=True)==config['prior_adapter_tensors']
    with sdpa_kernel(SDPBackend.MATH):
        for cid in gate_ids:
            if not check(input_map[cid],'prior',prior_sha):
                return {'status':'prior_cache_gate_failed','captures':0,'optimizer_steps':0}
        print('PRIOR_CACHE_GATE 20/20 PASS',flush=True)
        for row in inputs:generate(row,'prior',prior_sha)
    model=None;gc.collect();torch.cuda.empty_cache();deadline()
    model=load_base().float().eval();model.requires_grad_(False)
    assert tensor_hash(model)==base_hash


    # The optimizer never receives evaluation inputs, answers or reference scores.
    torch.manual_seed(config['seed'])
    model=get_peft_model(model,LoraConfig(**config['lora'],task_type='CAUSAL_LM'))
    trainable=[(n,p) for n,p in model.named_parameters() if p.requires_grad]
    assert trainable and all('lora_' in n and ('q_proj' in n or 'v_proj' in n) for n,p in trainable)
    assert tensor_hash(model)==base_hash
    initial_adapter_hash=tensor_hash(model,adapter=True)
    cast_training_parameters(model)
    assert all(p.dtype==torch.float32 for _,p in trainable)
    assert tensor_hash(model)==base_hash
    model.config.use_cache=False
    model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={'use_reentrant':False})
    model.enable_input_require_grads();model.train()
    optimizer=torch.optim.AdamW([p for _,p in trainable],lr=config['learning_rate'],weight_decay=config['weight_decay'])
    steps=[];seen=[];supervised_tokens=0;prefix_tokens=0;step=0;training_started=time.monotonic()
    with sdpa_kernel(SDPBackend.MATH):
        for epoch,order in enumerate(orders):
            for offset in range(0,len(order),config['gradient_accumulation']):
                deadline();batch_ids=order[offset:offset+config['gradient_accumulation']]
                assert len(batch_ids)==16
                step+=1;lr=learning_rate(step,config['optimizer_steps'],config['learning_rate'],config['warmup_steps'])
                for group in optimizer.param_groups:group['lr']=lr
                optimizer.zero_grad(set_to_none=True);loss_values=[];step_started=time.monotonic()
                for cid in batch_ids:
                    deadline();row=train_map[cid]
                    ids=torch.tensor([row['input_ids']],device='cuda')
                    positions=torch.tensor(row['prediction_positions'],device='cuda')
                    labels=torch.tensor(row['target_ids'],device='cuda')
                    logits=model(input_ids=ids,use_cache=False,logits_to_keep=positions).logits[0]
                    loss=answer_loss(logits,labels)
                    if not torch.isfinite(loss):raise ValueError('nonfinite training loss')
                    (loss/len(batch_ids)).backward();loss_values.append(float(loss.detach()))
                    seen.append(cid);supervised_tokens+=len(row['target_ids']);prefix_tokens+=row['prefix_tokens']
                    del ids,positions,labels,logits,loss
                assert all(p.grad is not None and torch.isfinite(p.grad).all() for _,p in trainable)
                assert any(p.grad.abs().max()>0 for _,p in trainable)
                assert all(p.grad is None for p in model.parameters() if not p.requires_grad)
                grad_norm=torch.nn.utils.clip_grad_norm_([p for _,p in trainable],config['gradient_clip_norm'])
                assert torch.isfinite(grad_norm)
                optimizer.step()
                entry={'step':step,'epoch':epoch+1,'example_ids':batch_ids,'learning_rate':lr,
                       'mean_answer_loss':sum(loss_values)/len(loss_values),'min_answer_loss':min(loss_values),
                       'max_answer_loss':max(loss_values),'gradient_norm_before_clip':float(grad_norm),
                       'all_gradients_finite':True,'only_adapter_gradients':True,'elapsed_seconds':time.monotonic()-step_started}
                steps.append(entry);(root/'training-steps.json').write_bytes(canonical(steps));commit()
                print('TRAIN_STEP '+str(step)+'/64 loss='+str(round(entry['mean_answer_loss'],6)),flush=True)
    optimizer.zero_grad(set_to_none=True);del optimizer
    assert step==64 and seen==orders[0]+orders[1]
    model.gradient_checkpointing_disable();model.disable_input_require_grads();model.config.use_cache=True
    model.eval();model.float()
    after_hash=tensor_hash(model);assert after_hash==base_hash
    final_adapter_hash=tensor_hash(model,adapter=True);assert final_adapter_hash!=initial_adapter_hash
    adapter_dir=root/'adapter';model.save_pretrained(adapter_dir,safe_serialization=True)
    adapter_sha=hashlib.sha256((adapter_dir/'adapter_model.safetensors').read_bytes()).hexdigest()
    training_result={'status':'training_complete','optimizer_steps':step,'epochs':2,'examples_seen':len(seen),
        'unique_examples':len(set(seen)),'exposure_order_sha256':digest(seen),'answer_target_tokens':supervised_tokens,
        'masked_prefix_tokens':prefix_tokens,'action_tokens_supervised':0,'training_seconds':time.monotonic()-training_started,
        'trainable_parameters':sum(p.numel() for _,p in trainable),'trainable_names':[n for n,p in trainable],
        'base_tensors_before':base_hash,'base_tensors_after':after_hash,'initial_adapter_tensors':initial_adapter_hash,
        'trained_adapter_tensors':final_adapter_hash,'adapter_sha256':adapter_sha,
        'training_examples_mounted':512,'evaluation_references_mounted':False,'checkpoint_selection':'fixed_final_after_two_epochs',
        'base_parameter_training':False,'base_buffer_training':False}
    (root/'training.json').write_bytes(canonical(training_result));commit()
    del trainable;model=None;gc.collect();torch.cuda.empty_cache()
    deadline()
    model=PeftModel.from_pretrained(load_base(),str(adapter_dir),is_trainable=False,local_files_only=True).float().eval()
    model.requires_grad_(False)
    reloaded_base=tensor_hash(model);reloaded_adapter=tensor_hash(model,adapter=True)
    assert reloaded_base==base_hash and reloaded_adapter==final_adapter_hash
    saved=load_file(str(adapter_dir/'adapter_model.safetensors'))
    loaded={n.replace('.default.','.'):p.detach().cpu() for n,p in model.named_parameters() if 'lora_' in n}
    assert set(saved)==set(loaded) and all(torch.equal(saved[n].float(),loaded[n].float()) for n in saved)
    assert all('lora_' in n and ('q_proj' in n or 'v_proj' in n) for n in saved)
    del saved,loaded
    (root/'reload-verification.json').write_bytes(canonical({'status':'PASS','base_tensors':reloaded_base,
        'adapter_tensors':reloaded_adapter,'adapter_sha256':adapter_sha,'saved_tensor_equality':True,
        'trainable_parameters':sum(p.numel() for p in model.parameters() if p.requires_grad)}));commit()
    print('ADAPTER_RELOAD PASS',flush=True)
    with sdpa_kernel(SDPBackend.MATH):
        for cid in gate_ids:
            if not check(input_map[cid],'adapted',adapter_sha):
                return {'status':'adapted_cache_gate_failed','captures':len(captures),'optimizer_steps':step,'adapter_sha256':adapter_sha}
        gate={'pass':len(checks)==40 and all(c['pass'] for c in checks),'checked':len(checks),
              'decode_limit':16,'scope':'same twenty actual prompts per prior and reloaded revised adapter'}
        (root/'cache-verdict.json').write_bytes(canonical(gate));commit()
        print('ALL_CACHE_GATES 40/40 PASS',flush=True)
        for row in inputs:generate(row,'adapted',adapter_sha)
    return {'status':'collection_complete','captures':len(captures),'optimizer_steps':step,'training_examples':512,
        'training_exposures':len(seen),'adapter_sha256':adapter_sha,'gate':gate,
        'body_valid':sum(c['body_structurally_valid'] for c in captures),
        'within_90_words':sum(c['within_90_words'] for c in captures),'routing_labels':0,'answer_supervision_examples':512}

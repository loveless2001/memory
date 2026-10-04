"""Frozen-source presentation diagnostic; no notes, retrieval selection or training."""
import time
from pathlib import Path
import torch
from torch.nn.attention import SDPBackend, sdpa_kernel
from .cache_session import AppendOnlySession, ReaderIdentity
from .broader_protocol import answer_prefix_ids, strict_body_capture, SYSTEM
from .preflight import canonical, digest, paired_greedy


@torch.inference_mode()
def run(config, inputs, gate_indices, root, commit, deadline):
    from transformers import AutoTokenizer, AutoModelForCausalLM
    import transformers
    root=Path(root);torch.set_num_threads(4);torch.manual_seed(config['seed'])
    tok=AutoTokenizer.from_pretrained(config['model_id'],revision=config['model_revision'],local_files_only=True)
    for row in inputs:
        if row['input_tokens']!=len(answer_prefix_ids(tok,row['messages'])):raise ValueError('input token binding mismatch')
        if row['messages'][0]!={'role':'system','content':SYSTEM}:raise ValueError('system changed')
    model=AutoModelForCausalLM.from_pretrained(config['model_id'],revision=config['model_revision'],local_files_only=True,
        torch_dtype=torch.bfloat16,attn_implementation='sdpa').to('cuda').eval()
    model.requires_grad_(False);model.float()
    if model.config._commit_hash!=config['model_revision']:raise ValueError('model revision changed')
    torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
    torch.set_float32_matmul_precision('highest')
    identity=ReaderIdentity(config['model_revision'],'base-no-adapter',digest(tok.chat_template),
                            'fp32-math-tf32off-reader-diagnostic-'+digest(SYSTEM))
    (root/'runtime.json').write_bytes(canonical({'model_revision':model.config._commit_hash,
        'template_sha256':digest(tok.chat_template),'torch':torch.__version__,'transformers':transformers.__version__,
        'gpu':torch.cuda.get_device_name(),'dtype':'float32','attention':'math','tf32':False,
        'trainable_parameters':sum(p.numel() for p in model.parameters() if p.requires_grad)}));commit()
    checks=[];captures=[]
    with sdpa_kernel(SDPBackend.MATH):
        for index in gate_indices:
            deadline();row=inputs[index];ids=answer_prefix_ids(tok,row['messages']);fresh_ids=list(ids)
            session=AppendOnlySession(model,identity,last_logit_only=True)
            cached=session.append_transcript(ids,identity)[0][-1]
            def fresh():return model(input_ids=torch.tensor([fresh_ids],device='cuda'),use_cache=False,logits_to_keep=1).logits[0,-1]
            full=fresh()
            initial=int(cached.argmax())==int(full.argmax())
            def cached_step(token):
                ids.append(token);return session.append_transcript(ids,identity)[0][-1]
            def fresh_step(token):
                fresh_ids.append(token);return fresh()
            ct,ft=paired_greedy(cached,full,cached_step,fresh_step,tok.eos_token_id,deadline,limit=16)
            checks.append({'input_index':index,'id':row['id'],'arm':row['arm'],'initial_argmax_equal':initial,
                           'cached_tokens':ct,'fresh_tokens':ft,'pass':initial and ct==ft})
            (root/'cache-checks.json').write_bytes(canonical(checks));commit()
            if not checks[-1]['pass']:break
        gate={'pass':len(checks)==40 and all(c['pass'] for c in checks),'checked':len(checks),
              'decode_limit':16,'scope':'40 actual diagnostic prompts, ten per arm; frozen base FP32 math'}
        (root/'cache-verdict.json').write_bytes(canonical(gate));commit()
        print('CACHE_GATE '+str(gate),flush=True)
        if not gate['pass']:return {'status':'cache_gate_failed','captures':0,'gate':gate}
        for index,row in enumerate(inputs):
            deadline();began=time.monotonic();ids=answer_prefix_ids(tok,row['messages']);n=len(ids)
            if n+config['max_message_output_tokens']>config['active_context_max_tokens']:raise ValueError('context budget exceeded')
            session=AppendOnlySession(model,identity,config['active_context_max_tokens'],last_logit_only=True)
            logits=session.append_transcript(ids,identity)[0][-1];tokens=[]
            for _ in range(config['max_message_output_tokens']):
                deadline();token=int(logits.argmax());tokens.append(token)
                if token==tok.eos_token_id:break
                ids.append(token);logits=session.append_transcript(ids,identity)[0][-1]
            result=strict_body_capture(tok,tokens,tok.eos_token_id)
            result.update(id=row['id'],arm=row['arm'],input_index=index,messages=row['messages'],input_tokens=n,
                actual_forwarded_tokens=session.fresh_tokens,fresh_prefill=True,elapsed_seconds=time.monotonic()-began)
            captures.append(result);(root/'captures.json').write_bytes(canonical(captures));commit()
            print('CAPTURE '+str(len(captures))+'/'+str(len(inputs))+' '+row['id']+' '+row['arm'],flush=True)
    return {'status':'collection_complete','captures':len(captures),'gate':gate,'training_labels':0,
            'body_valid':sum(c['body_structurally_valid'] for c in captures),
            'within_90_words':sum(c['within_90_words'] for c in captures)}

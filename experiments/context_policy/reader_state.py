"""Frozen three-arm state diagnostic; extraction is separate from answer generation."""
import time
from pathlib import Path
import torch
from torch.nn.attention import SDPBackend, sdpa_kernel
from .cache_session import AppendOnlySession, ReaderIdentity
from .broader_protocol import answer_prefix_ids, strict_body_capture
from .preflight import canonical, digest, paired_greedy
from .reader_state_protocol import parse_events, resolve, record_for_question, state_messages


@torch.inference_mode()
def run(config, payload, root, commit, deadline):
    from transformers import AutoTokenizer, AutoModelForCausalLM
    import transformers
    root = Path(root); torch.set_num_threads(4); torch.manual_seed(config['seed'])
    tok = AutoTokenizer.from_pretrained(config['model_id'], revision=config['model_revision'], local_files_only=True)
    static = {r['request_id']: r for r in payload['static-inputs.json']}
    streams = payload['streams.json']; questions = payload['questions.json']; gates = payload['gate-requests.json']
    for row in static.values():
        assert row['input_tokens'] == len(answer_prefix_ids(tok, row['messages']))
    model = AutoModelForCausalLM.from_pretrained(config['model_id'], revision=config['model_revision'],
        local_files_only=True, torch_dtype=torch.bfloat16, attn_implementation='sdpa').to('cuda').eval()
    model.requires_grad_(False); model.float()
    assert model.config._commit_hash == config['model_revision']
    torch.backends.cuda.matmul.allow_tf32 = False; torch.backends.cudnn.allow_tf32 = False
    torch.set_float32_matmul_precision('highest')
    (root/'runtime.json').write_bytes(canonical({'model_revision':model.config._commit_hash,
        'template_sha256':digest(tok.chat_template),'torch':torch.__version__,'transformers':transformers.__version__,
        'gpu':torch.cuda.get_device_name(),'dtype':'float32','attention':'math','tf32':False,
        'trainable_parameters':sum(p.numel() for p in model.parameters() if p.requires_grad)}))
    captures = []; extractions = []; checks = []

    def identity(messages):
        return ReaderIdentity(config['model_revision'],'base-no-adapter',digest(tok.chat_template),
                              'fp32-math-tf32off-reader-state-'+digest(messages[0]['content']))

    def check(row):
        deadline(); ids = answer_prefix_ids(tok,row['messages']); full_ids = list(ids); ident = identity(row['messages'])
        session = AppendOnlySession(model,ident,last_logit_only=True)
        cached = session.append_transcript(ids,ident)[0][-1]
        def fresh():
            return model(input_ids=torch.tensor([full_ids],device='cuda'),use_cache=False,logits_to_keep=1).logits[0,-1]
        full = fresh(); initial = int(cached.argmax()) == int(full.argmax())
        def cached_step(token):
            ids.append(token); return session.append_transcript(ids,ident)[0][-1]
        def fresh_step(token):
            full_ids.append(token); return fresh()
        ct, ft = paired_greedy(cached,full,cached_step,fresh_step,tok.eos_token_id,deadline,limit=16)
        result = {'request_id':row['request_id'],'arm':row['arm'],'messages':row['messages'],
                  'initial_argmax_equal':initial,'cached_tokens':ct,'fresh_tokens':ft,'pass':initial and ct==ft}
        checks.append(result); (root/'cache-checks.json').write_bytes(canonical(checks)); commit()
        return result['pass']

    def generate(row, limit):
        deadline(); started = time.monotonic(); ids = answer_prefix_ids(tok,row['messages']); n = len(ids)
        if n + limit > config['active_context_max_tokens']: raise ValueError('context budget exceeded')
        ident = identity(row['messages'])
        session = AppendOnlySession(model,ident,config['active_context_max_tokens'],last_logit_only=True)
        logits = session.append_transcript(ids,ident)[0][-1]; tokens = []
        for _ in range(limit):
            deadline(); token = int(logits.argmax()); tokens.append(token)
            if token == tok.eos_token_id: break
            ids.append(token); logits = session.append_transcript(ids,ident)[0][-1]
        body = strict_body_capture(tok,tokens,tok.eos_token_id)
        body.update(request_id=row['request_id'],id=row['id'],arm=row['arm'],messages=row['messages'],
                    input_tokens=n,output_limit=limit,actual_forwarded_tokens=session.fresh_tokens,
                    fresh_prefill=True,elapsed_seconds=time.monotonic()-started)
        return body

    with sdpa_kernel(SDPBackend.MATH):
        for key in gates['static']:
            if not check(static[key]):
                return {'status':'static_cache_gate_failed','captures':0,'extractions':0,'training_labels':0}
        print('STATIC_CACHE_GATE 30/30 PASS',flush=True)
        extracted = {}
        for stream in streams:
            row = static['extract:'+stream['id']]
            capture = generate(row,config['extraction_output_tokens'])
            parsed = parse_events(capture['text'],stream['history'])
            if not capture['ended_at_eos'] or not capture['body_structurally_valid']:
                parsed = {'valid':False,'events':[],'error':'incomplete or invalid extraction body'}
            state = resolve(parsed['events'],stream['property'])
            capture.update(parsed=parsed,resolved_state=state)
            extractions.append(capture); extracted[stream['id']] = capture
            (root/'extractions.json').write_bytes(canonical(extractions)); commit()
            print('EXTRACT '+str(len(extractions))+'/'+str(len(streams))+' '+stream['id'],flush=True)
        stream_map = {s['id']:s for s in streams}; dynamic = {}
        for q in questions:
            stream = stream_map[q['stream_id']]
            record = record_for_question(extracted[stream['id']]['resolved_state'],stream['history'],q)
            dynamic[q['id']] = {'request_id':'extracted:'+q['id'],'id':q['id'],'arm':'extracted',
                                'messages':state_messages(record,q['query']),'record':record}
        (root/'derived-inputs.json').write_bytes(canonical(list(dynamic.values())))
        for cid in gates['extracted']:
            if not check(dynamic[cid]):
                return {'status':'derived_cache_gate_failed','captures':0,'extractions':len(extractions),'training_labels':0}
        gate = {'pass':len(checks)==40 and all(c['pass'] for c in checks),'checked':len(checks),
                'decode_limit':16,'scope':'10 actual prompts per baseline/oracle/extractor/extracted workload'}
        (root/'cache-verdict.json').write_bytes(canonical(gate)); commit()
        print('ALL_CACHE_GATES 40/40 PASS',flush=True)
        for i,q in enumerate(questions):
            arms = ['baseline','oracle','extracted']; arms = arms[i%3:] + arms[:i%3]
            for arm in arms:
                row = dynamic[q['id']] if arm == 'extracted' else static[arm+':'+q['id']]
                capture = generate(row,config['max_message_output_tokens'])
                captures.append(capture); (root/'captures.json').write_bytes(canonical(captures)); commit()
                print('ANSWER '+str(len(captures))+'/'+str(len(questions)*3)+' '+row['request_id'],flush=True)
    return {'status':'collection_complete','captures':len(captures),'extractions':len(extractions),
            'gate':gate,'training_labels':0,'valid_extraction_parses':sum(c['parsed']['valid'] for c in extractions),
            'body_valid':sum(c['body_structurally_valid'] for c in captures),
            'within_90_words':sum(c['within_90_words'] for c in captures)}

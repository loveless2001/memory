"""Bounded prospective probe for extractive notes and anchored retrieval.

No training, private reference access, automatic retry, or prior-score rewriting.
"""

import json
import time
from pathlib import Path

import torch
from torch.nn.attention import SDPBackend, sdpa_kernel

from .cache_session import AppendOnlySession, ReaderIdentity
from .grounded_notes import (source_candidates, note_batches, selector_messages,
                             accept_selection, render_notes)
from .preflight import canonical, digest, fixtures, paired_greedy
from .repair_pilot import chunks_for, retrieve_rounds, render_history, validate_bundle
from .repair_protocol import (reader_messages, append_retrieval, answer_prefix_ids,
                              body_capture, READER_SYSTEM)


def transcript_gate(model, tokenizer, identity, root, commit, deadline):
    checks = []
    for row in fixtures():
        deadline()
        history = reader_messages('A separate meeting concerned accessibility. ' * row['padding_repetitions'], '', row['question'])
        session = AppendOnlySession(model, identity, last_logit_only=True)
        stages = []
        for n in range(3):
            ids = tokenizer.apply_chat_template(history, tokenize=True, add_generation_prompt=True)
            cached = session.append_transcript(ids, identity)[0][-1]
            full = model(input_ids=torch.tensor([ids], device='cuda'), use_cache=False, logits_to_keep=1).logits[0, -1]
            stages.append(int(cached.argmax()) == int(full.argmax()))
            if n < 2:
                history = append_retrieval(history, row['evidence'] if n == 0 else 'No additional evidence.', row['question'])
        # Supply the same action prefix as counterfactual collection. Check its
        # append separately; then compare full generated body trajectories.
        ids = answer_prefix_ids(tokenizer, history)
        cached = session.append_transcript(ids, identity)[0][-1]
        fresh_ids = list(ids)
        def fresh():
            return model(input_ids=torch.tensor([fresh_ids], device='cuda'), use_cache=False, logits_to_keep=1).logits[0, -1]
        full = fresh()
        stages.append(int(cached.argmax()) == int(full.argmax()))
        def cached_step(token):
            ids.append(token)
            return session.append_transcript(ids, identity)[0][-1]
        def fresh_step(token):
            fresh_ids.append(token)
            return fresh()
        ct, ft = paired_greedy(cached, full, cached_step, fresh_step, tokenizer.eos_token_id, deadline, limit=16)
        checks.append({'id': row['id'], 'append_argmax_equal': stages, 'cached_tokens': ct,
                       'fresh_tokens': ft, 'equal': all(stages) and ct == ft})
        (root/'transcript-checks.json').write_bytes(canonical(checks)); commit()
        print(json.dumps({'stage': 'revised_transcript_gate', 'completed': len(checks),
                          'failed': sum(not x['equal'] for x in checks)}), flush=True)
    return {'pass': all(x['equal'] for x in checks), 'checked': len(checks),
            'scope': 'frozen base FP32; not a trained-adapter certification',
            'decode_limit': 16, 'question_evidence': 'synthetic cache fixtures, not accuracy data'}


@torch.inference_mode()
def run(config, bundle, root, commit, deadline):
    from transformers import AutoModelForCausalLM, AutoTokenizer
    validate_bundle(bundle)
    root = Path(root)
    torch.set_num_threads(4); torch.manual_seed(0)
    tokenizer = AutoTokenizer.from_pretrained(config['model_id'], revision=config['model_revision'], local_files_only=True)
    model = AutoModelForCausalLM.from_pretrained(config['model_id'], revision=config['model_revision'],
        local_files_only=True, torch_dtype=torch.bfloat16, attn_implementation='sdpa').to('cuda').eval()
    assert model.config._commit_hash == config['model_revision']
    model.requires_grad_(False)
    model.float()
    torch.backends.cuda.matmul.allow_tf32 = False; torch.backends.cudnn.allow_tf32 = False
    torch.set_float32_matmul_precision('highest')
    identity = ReaderIdentity(config['model_revision'], 'base-no-adapter', digest(tokenizer.chat_template),
                              'fp32_math-tf32-off-repair-v2-' + digest(READER_SYSTEM))
    with sdpa_kernel(SDPBackend.MATH):
        gate = transcript_gate(model, tokenizer, identity, root, commit, deadline)
    (root/'transcript-verdict.json').write_bytes(canonical(gate)); commit()
    if not gate['pass']:
        return {'status': 'revised_transcript_gate_failed', 'corpus_trained': False, 'gate': gate}
    model.bfloat16()
    notes, events = {}, []
    for pid, history in bundle['histories'].items():
        candidates, constraints = source_candidates(tokenizer, history)
        batches = note_batches(tokenizer, candidates)
        previous = []
        rendered = render_notes([], [])
        for batch_index, batch in enumerate(batches):
            deadline()
            through = len(history)-1 if batch_index == len(batches)-1 else batch[-1]['turn']
            ledger = [x for x in constraints if x['turn'] <= through]
            messages = selector_messages(tokenizer, previous, batch, ledger, config['notes_max_tokens'])
            ids = tokenizer.apply_chat_template(messages, tokenize=True, add_generation_prompt=True, return_tensors='pt').to('cuda')
            if ids.shape[1] > 6144:
                raise ValueError('note update input exceeds 6144 tokens')
            started = time.monotonic()
            result = model.generate(ids, attention_mask=torch.ones_like(ids), do_sample=False, max_new_tokens=192,
                                    pad_token_id=tokenizer.eos_token_id, use_cache=True, max_time=60)
            tokens = result[0, ids.shape[1]:].tolist()
            raw = tokenizer.decode(tokens, skip_special_tokens=True)
            event = {'persona_id': pid, 'batch': batch_index, 'through_turn': through, 'input_tokens': ids.shape[1],
                     'output_tokens': len(tokens), 'raw': raw, 'elapsed_seconds': time.monotonic()-started,
                     'ended_at_eos': bool(tokens and tokens[-1] == tokenizer.eos_token_id)}
            try:
                previous, rendered = accept_selection(tokenizer, raw, event['ended_at_eos'], previous, batch,
                    ledger, history, config['notes_max_tokens'], through_turn=through)
                event['accepted'] = True
            except (ValueError, KeyError, TypeError) as exc:
                event.update(accepted=False, error=str(exc))
                events.append(event)
                (root/'note-events.json').write_bytes(canonical(events)); commit()
                return {'status': 'note_selection_gate_failed', 'failed_persona': pid, 'failed_batch': batch_index,
                        'error': str(exc), 'notes_completed': len(notes), 'corpus_trained': False, 'gate': gate}
            events.append(event)
            (root/'note-events.json').write_bytes(canonical(events)); commit()
            print(json.dumps({'stage': 'extractive_notes', 'persona': pid, 'batch': batch_index+1,
                              'batches': len(batches), 'accepted': True}), flush=True)
        notes[pid] = {'text': rendered, 'selected': previous, 'withdrawals': constraints,
                      'tokens': len(tokenizer.encode(rendered, add_special_tokens=False)),
                      'semantic_review': 'pending', 'history_sha256': digest(history)}
        (root/'notes.json').write_bytes(canonical(notes)); commit()
    model.float()
    captures = []
    with sdpa_kernel(SDPBackend.MATH):
        for question in bundle['questions']:
            deadline()
            pid = question['persona_id']; query = question['query']['content']; history = bundle['histories'][pid]
            ranked_start = time.monotonic()
            chunks = chunks_for(tokenizer, history, config['chunk_max_tokens'], config['chunk_overlap_tokens'])
            retrievals = retrieve_rounds(tokenizer, chunks, query, config['evidence_tokens_per_round'])
            retrieval_seconds = time.monotonic()-ranked_start
            recent = tokenizer.decode(tokenizer.encode(render_history(history), add_special_tokens=False)[-config['recent_max_tokens']:])
            messages = reader_messages(notes[pid]['text'], recent, query)
            for n in range(3):
                started = time.monotonic()
                ids = answer_prefix_ids(tokenizer, messages)
                input_tokens = len(ids)
                session = AppendOnlySession(model, identity, config['active_context_max_tokens'], last_logit_only=True)
                logits = session.append_transcript(ids, identity)[0][-1]
                tokens = []
                for _ in range(config['max_message_output_tokens']):
                    deadline(); token = int(logits.argmax()); tokens.append(token)
                    if token == tokenizer.eos_token_id:
                        break
                    ids.append(token); logits = session.append_transcript(ids, identity)[0][-1]
                result = body_capture(tokenizer, tokens, tokenizer.eos_token_id)
                result.update(id=question['id'], persona_id=pid, retrieval_rounds=n, messages=messages,
                              retrieval=retrievals[:n], input_tokens=input_tokens,
                              elapsed_seconds=time.monotonic()-started, retrieval_seconds=retrieval_seconds,
                              actual_forwarded_tokens=session.fresh_tokens)
                captures.append(result)
                (root/'captures.json').write_bytes(canonical(captures)); commit()
                print(json.dumps({'stage': 'body_capture', 'completed': len(captures), 'valid_body': result['body_structurally_valid']}), flush=True)
                if n < 2:
                    messages = append_retrieval(messages, retrievals[n]['text'], query)
    return {'status': 'awaiting_source_and_content_review', 'captures': len(captures), 'notes': len(notes),
            'body_structurally_valid': sum(x['body_structurally_valid'] for x in captures),
            'generated_action_protocol_valid': None, 'corpus_trained': False, 'trainable_parameters': 0, 'gate': gate}

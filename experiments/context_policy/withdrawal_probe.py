"""Frozen-note reader collection for a separately versioned development set."""

import json
import time
from pathlib import Path

import torch
from torch.nn.attention import SDPBackend, sdpa_kernel

from .cache_session import AppendOnlySession, ReaderIdentity
from .preflight import canonical, digest
from .repair_pilot import validate_bundle
from .reader_regression import FORCED_SYSTEM, answer_prefix_ids, append_evidence, strict_body_capture, reader_messages, paired_views, validate_topics
from .memory_probe import validate_reused_notes
from .preflight import fixtures, paired_greedy


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
                history = append_evidence(history, row['evidence'] if n == 0 else 'No additional evidence.', row['question'])
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
        print(json.dumps({'stage': 'withdrawal_transcript_gate', 'completed': len(checks),
                          'failed': sum(not x['equal'] for x in checks)}), flush=True)
        if not checks[-1]['equal']:
            break
    return {'pass': len(checks) == 40 and all(x['equal'] for x in checks), 'checked': len(checks),
            'scope': 'frozen base FP32; not a trained-adapter certification',
            'decode_limit': 16, 'question_evidence': 'synthetic cache fixtures, not accuracy data'}


@torch.inference_mode()
def run(config, bundle, notes, topics, schedule, root, commit, deadline):
    from transformers import AutoModelForCausalLM, AutoTokenizer
    validate_bundle(bundle)
    root = Path(root)
    torch.set_num_threads(4); torch.manual_seed(0)
    tokenizer = AutoTokenizer.from_pretrained(config['model_id'], revision=config['model_revision'], local_files_only=True)
    if [q['id'] for q in bundle['questions']] != [q['id'] for q in schedule]:
        raise ValueError('schedule question mismatch')
    if set(topics) != set(bundle['histories']):
        raise ValueError('topic history mismatch')
    for pid, history in bundle['histories'].items():
        validate_topics(history, topics[pid])
    note_check = validate_reused_notes(tokenizer, bundle, notes, config['notes_max_tokens'])
    (root / 'reused-note-checks.json').write_bytes(canonical(note_check)); commit()
    model = AutoModelForCausalLM.from_pretrained(config['model_id'], revision=config['model_revision'],
        local_files_only=True, torch_dtype=torch.bfloat16, attn_implementation='sdpa').to('cuda').eval()
    assert model.config._commit_hash == config['model_revision']
    model.requires_grad_(False); model.float()
    torch.backends.cuda.matmul.allow_tf32 = False; torch.backends.cudnn.allow_tf32 = False
    torch.set_float32_matmul_precision('highest')
    identity = ReaderIdentity(config['model_revision'], 'base-no-adapter', digest(tokenizer.chat_template),
                              'fp32_math-tf32-off-withdrawal-v1-' + digest(FORCED_SYSTEM))
    with sdpa_kernel(SDPBackend.MATH):
        gate = transcript_gate(model, tokenizer, identity, root, commit, deadline)
    (root / 'transcript-verdict.json').write_bytes(canonical(gate)); commit()
    if not gate['pass']:
        return {'status': 'transcript_gate_failed', 'corpus_trained': False, 'gate': gate}
    captures = []
    with sdpa_kernel(SDPBackend.MATH):
        for question, row in zip(bundle['questions'], schedule):
            deadline()
            pid = question['persona_id']; query = question['query']['content']; history = bundle['histories'][pid]
            started = time.monotonic()
            views = paired_views(tokenizer, history, notes[pid], topics[pid], query, config)
            retrieval_seconds = time.monotonic() - started
            n = row['retrieval_rounds']
            if n not in (0, 1) or sorted(row['arm_order']) != ['neutral', 'raw']:
                raise ValueError('invalid paired schedule')
            for arm in row['arm_order']:
                view = views[arm]
                messages = reader_messages(view['notes'], view['recent'], query)
                retrievals = [view['retrieval']] if n else []
                if n:
                    messages = append_evidence(messages, view['retrieval']['text'], query)
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
                result = strict_body_capture(tokenizer, tokens, tokenizer.eos_token_id)
                result.update(id=question['id'], arm=arm, kind=row['kind'], persona_id=pid, retrieval_rounds=n, messages=messages,
                              retrieval=retrievals[:n], input_tokens=input_tokens,
                              elapsed_seconds=time.monotonic()-started, retrieval_seconds=retrieval_seconds,
                              actual_forwarded_tokens=session.fresh_tokens)
                captures.append(result)
                (root / 'captures.json').write_bytes(canonical(captures)); commit()
                print(json.dumps({'stage': 'withdrawal_body_capture', 'completed': len(captures),
                                  'id': question['id'], 'round': n, 'arm': arm, 'valid_body': result['body_structurally_valid']}), flush=True)
    return {'status': 'awaiting_source_content_length_review', 'captures': len(captures), 'notes_reused': len(notes),
            'body_structurally_valid': sum(x['body_structurally_valid'] for x in captures),
            'generated_action_protocol_valid': None, 'corpus_trained': False, 'trainable_parameters': 0,
            'note_check': note_check, 'gate': gate}

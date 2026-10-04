"""Frozen-note reader collection for a separately versioned development set."""

import json
import time
from pathlib import Path

import torch
from torch.nn.attention import SDPBackend, sdpa_kernel

from .cache_session import AppendOnlySession, ReaderIdentity
from .grounded_notes import render_notes, withdrawal
from .preflight import canonical, digest
from .repair_pilot import chunks_for, render_history, retrieve_rounds, validate_bundle
from .repair_protocol import READER_SYSTEM, answer_prefix_ids, append_retrieval, body_capture, reader_messages
from .repair_v2 import transcript_gate


def validate_reused_notes(tokenizer, bundle, notes, note_cap=768):
    validate_bundle(bundle)
    if set(notes) != set(bundle['histories']):
        raise ValueError('reused notes must cover exactly these histories')
    for pid, history in bundle['histories'].items():
        note = notes[pid]
        if note['history_sha256'] != digest(history):
            raise ValueError('reused note history binding changed')
        ledger = [{'turn': i, 'content': m['content']} for i, m in enumerate(history) if withdrawal(m)]
        if note['withdrawals'] != ledger:
            raise ValueError('reused note withdrawal ledger changed')
        seen = set()
        for quote in note['selected']:
            turn, start, end = quote['turn'], quote['start'], quote['end']
            if type(turn) is not int or not 0 <= turn < len(history):
                raise ValueError('reused quote turn is invalid')
            message = history[turn]
            if (type(start) is not int or type(end) is not int or not 0 <= start < end <= len(message['content'])
                    or message['role'] != 'user' or quote['source_sha256'] != digest(message)
                    or quote['id'] != f'T{turn}:{start}-{end}' or quote['id'] in seen
                    or quote['quote'] != message['content'][start:end]):
                raise ValueError('reused note quotation binding changed')
            seen.add(quote['id'])
        if not seen or note['text'] != render_notes(note['selected'], ledger):
            raise ValueError('reused note rendering changed or empty selection')
        tokens = len(tokenizer.encode(note['text'], add_special_tokens=False))
        if tokens != note['tokens'] or tokens > note_cap:
            raise ValueError('reused note token count changed or exceeds cap')
    return {'histories': len(notes), 'quotations': sum(len(n['selected']) for n in notes.values()),
            'withdrawals': sum(len(n['withdrawals']) for n in notes.values()),
            'all_source_bindings_valid': True, 'regenerated': False}


@torch.inference_mode()
def run(config, bundle, notes, root, commit, deadline):
    from transformers import AutoModelForCausalLM, AutoTokenizer
    validate_bundle(bundle)
    root = Path(root)
    torch.set_num_threads(4); torch.manual_seed(0)
    tokenizer = AutoTokenizer.from_pretrained(config['model_id'], revision=config['model_revision'], local_files_only=True)
    note_check = validate_reused_notes(tokenizer, bundle, notes, config['notes_max_tokens'])
    (root / 'reused-note-checks.json').write_bytes(canonical(note_check)); commit()
    model = AutoModelForCausalLM.from_pretrained(config['model_id'], revision=config['model_revision'],
        local_files_only=True, torch_dtype=torch.bfloat16, attn_implementation='sdpa').to('cuda').eval()
    assert model.config._commit_hash == config['model_revision']
    model.requires_grad_(False); model.float()
    torch.backends.cuda.matmul.allow_tf32 = False; torch.backends.cudnn.allow_tf32 = False
    torch.set_float32_matmul_precision('highest')
    identity = ReaderIdentity(config['model_revision'], 'base-no-adapter', digest(tokenizer.chat_template),
                              'fp32_math-tf32-off-repair-v2-' + digest(READER_SYSTEM))
    with sdpa_kernel(SDPBackend.MATH):
        gate = transcript_gate(model, tokenizer, identity, root, commit, deadline)
    (root / 'transcript-verdict.json').write_bytes(canonical(gate)); commit()
    if not gate['pass']:
        return {'status': 'transcript_gate_failed', 'corpus_trained': False, 'gate': gate}
    captures = []
    with sdpa_kernel(SDPBackend.MATH):
        for question in bundle['questions']:
            deadline()
            pid = question['persona_id']; query = question['query']['content']; history = bundle['histories'][pid]
            started = time.monotonic()
            chunks = chunks_for(tokenizer, history, config['chunk_max_tokens'], config['chunk_overlap_tokens'])
            retrievals = retrieve_rounds(tokenizer, chunks, query, config['evidence_tokens_per_round'])
            retrieval_seconds = time.monotonic() - started
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
                (root / 'captures.json').write_bytes(canonical(captures)); commit()
                print(json.dumps({'stage': 'memory_body_capture', 'completed': len(captures),
                                  'id': question['id'], 'round': n, 'valid_body': result['body_structurally_valid']}), flush=True)
                if n < 2:
                    messages = append_retrieval(messages, retrievals[n]['text'], query)
    return {'status': 'awaiting_source_content_length_review', 'captures': len(captures), 'notes_reused': len(notes),
            'body_structurally_valid': sum(x['body_structurally_valid'] for x in captures),
            'generated_action_protocol_valid': None, 'corpus_trained': False, 'trainable_parameters': 0,
            'note_check': note_check, 'gate': gate}

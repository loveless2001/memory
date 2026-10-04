"""Bounded broader reader collection. References and judgments are not inputs."""

import json
import time
from pathlib import Path

import torch
from torch.nn.attention import SDPBackend, sdpa_kernel

from .broader_protocol import SYSTEM, reader_messages, append_evidence, answer_prefix_ids, strict_body_capture
from .cache_session import AppendOnlySession, ReaderIdentity
from .grounded_notes import note_batches, render_notes
from .broader_notes import source_candidates, pack_ranked_selection, validate_notes
from .preflight import canonical, digest, fixtures, paired_greedy
from .repair_pilot import validate_bundle
from .source_choice import choice_messages, SourceChoiceGrammar


def transcript_gate(model, tokenizer, identity, root, commit, deadline):
    checks = []
    for row in fixtures():
        deadline()
        messages = reader_messages('A separate meeting concerned accessibility. ' * row['padding_repetitions'], '', row['question'])
        session = AppendOnlySession(model, identity, last_logit_only=True)
        equal = []
        for stage in range(3):
            ids = tokenizer.apply_chat_template(messages, tokenize=True, add_generation_prompt=True)
            cached = session.append_transcript(ids, identity)[0][-1]
            full = model(input_ids=torch.tensor([ids], device='cuda'), use_cache=False, logits_to_keep=1).logits[0, -1]
            equal.append(int(cached.argmax()) == int(full.argmax()))
            if stage < 2:
                messages = append_evidence(messages, row['evidence'] if stage == 0 else 'No additional evidence.', row['question'])
        ids = answer_prefix_ids(tokenizer, messages)
        cached = session.append_transcript(ids, identity)[0][-1]
        fresh_ids = list(ids)
        def fresh():
            return model(input_ids=torch.tensor([fresh_ids], device='cuda'), use_cache=False, logits_to_keep=1).logits[0, -1]
        full = fresh()
        equal.append(int(cached.argmax()) == int(full.argmax()))
        def cached_step(token):
            ids.append(token)
            return session.append_transcript(ids, identity)[0][-1]
        def fresh_step(token):
            fresh_ids.append(token)
            return fresh()
        ct, ft = paired_greedy(cached, full, cached_step, fresh_step, tokenizer.eos_token_id, deadline, limit=16)
        checks.append({'id': row['id'], 'append_argmax_equal': equal, 'cached_tokens': ct,
                       'fresh_tokens': ft, 'equal': all(equal) and ct == ft})
        (root / 'transcript-checks.json').write_bytes(canonical(checks)); commit()
        if not checks[-1]['equal']:
            break
    return {'pass': len(checks) == 40 and all(x['equal'] for x in checks), 'checked': len(checks),
            'decode_limit': 16, 'scope': 'new raw-source transcript, frozen base FP32; no adapter certification'}


def generate_notes(model, tokenizer, histories, worklist, config, root, commit, deadline):
    """No queries, references, answer modes or target spans enter this function."""
    notes, events = {}, []
    if len(worklist) != len(histories) or {w['history_id'] for w in worklist} != set(histories):
        raise ValueError('note worklist coverage mismatch')
    for work in worklist:
        hid = work['history_id']; history = histories[hid]
        if work['history_sha256'] != digest(history):
            raise ValueError('note worklist source mismatch')
        candidates, constraints = source_candidates(tokenizer, history)
        parent = work['parent_history_id']
        if parent is None:
            previous = []
            batches = note_batches(tokenizer, candidates)
        else:
            prefix = histories[parent]
            if history[:len(prefix)] != prefix or len(history) != len(prefix) + 2:
                raise ValueError('variant does not extend its exact parent')
            previous = list(notes[parent]['selected'])
            batches = note_batches(tokenizer, [x for x in candidates if x['turn'] >= len(prefix)])
        if len(batches) != work['updates']:
            raise ValueError('note workload changed')
        rendered = render_notes(previous, constraints)
        for batch_index, batch in enumerate(batches):
            deadline()
            through = len(history)-1 if batch_index == len(batches)-1 else batch[-1]['turn']
            ledger = [x for x in constraints if x['turn'] <= through]
            messages = choice_messages(tokenizer, previous, batch, ledger, config['notes_max_tokens'])
            ids = tokenizer.apply_chat_template(messages, tokenize=True, add_generation_prompt=True, return_tensors='pt').to('cuda')
            if ids.shape[1] > 6144:
                raise ValueError('note selector input exceeds budget')
            grammar = SourceChoiceGrammar(tokenizer, list(dict.fromkeys(x['id'] for x in previous + batch)))
            if grammar.max_required_tokens > 192:
                raise ValueError('note grammar exceeds output budget')
            prompt_length = ids.shape[1]
            def allowed(_batch_id, sequence):
                deadline()
                return grammar.allowed_tokens(sequence[prompt_length:].tolist())
            began = time.monotonic()
            event = {'history_id': hid, 'parent_history_id': parent, 'batch': batch_index,
                     'through_turn': through, 'messages': messages, 'input_tokens': ids.shape[1], 'accepted': None}
            events.append(event)
            (root / 'note-events.json').write_bytes(canonical(events)); commit()
            result = model.generate(ids, attention_mask=torch.ones_like(ids), do_sample=False, max_new_tokens=192,
                                    pad_token_id=tokenizer.eos_token_id, use_cache=True, max_time=60,
                                    prefix_allowed_tokens_fn=allowed)
            tokens = result[0, ids.shape[1]:].tolist()
            event.update(token_ids=tokens, elapsed_seconds=time.monotonic()-began)
            try:
                ranking = grammar.selected_ids(tokens)
                previous, rendered, admission = pack_ranked_selection(tokenizer, json.dumps(ranking),
                    bool(tokens and tokens[-1] == tokenizer.eos_token_id), previous, batch, ledger, history,
                    config['notes_max_tokens'], through_turn=through)
                event.update(accepted=True, admission=admission)
            except (ValueError, KeyError, TypeError) as exc:
                event.update(accepted=False, error=str(exc))
                (root / 'note-events.json').write_bytes(canonical(events)); commit()
                raise
            (root / 'note-events.json').write_bytes(canonical(events)); commit()
        notes[hid] = {'text': rendered, 'selected': previous, 'withdrawals': constraints,
                      'tokens': len(tokenizer.encode(rendered, add_special_tokens=False)),
                      'semantic_review': 'pending', 'history_sha256': digest(history)}
        (root / 'notes.json').write_bytes(canonical(notes)); commit()
    return notes


@torch.inference_mode()
def run(config, bundle, worklist, prepared_views, schedule, root, commit, deadline):
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from .broader_protocol import validate_span, render_spans
    validate_bundle(bundle)
    root = Path(root)
    torch.set_num_threads(4); torch.manual_seed(0)
    tokenizer = AutoTokenizer.from_pretrained(config['model_id'], revision=config['model_revision'], local_files_only=True)
    if [q['id'] for q in bundle['questions']] != [r['id'] for r in schedule]:
        raise ValueError('question schedule mismatch')
    if set(prepared_views) != {q['id'] for q in bundle['questions']}:
        raise ValueError('view coverage mismatch')
    for q in bundle['questions']:
        view = prepared_views[q['id']]
        if view['history_sha256'] != digest(bundle['histories'][q['persona_id']]) or view['query_sha256'] != digest(q['query']):
            raise ValueError('view binding mismatch')
        for part in [view['recent']] + view['retrievals']:
            for span in part['spans']:
                validate_span(bundle['histories'][q['persona_id']], span)
            expected = render_spans(part['spans']) or ('No additional matching dialogue was found.' if part in view['retrievals'] else '')
            if part['text'] != expected or part['tokens'] != len(tokenizer.encode(expected, add_special_tokens=False)):
                raise ValueError('prepared rendering changed')
    model = AutoModelForCausalLM.from_pretrained(config['model_id'], revision=config['model_revision'],
        local_files_only=True, torch_dtype=torch.bfloat16, attn_implementation='sdpa').to('cuda').eval()
    if model.config._commit_hash != config['model_revision']:
        raise ValueError('model revision mismatch')
    model.requires_grad_(False); model.float()
    torch.backends.cuda.matmul.allow_tf32 = False; torch.backends.cudnn.allow_tf32 = False
    torch.set_float32_matmul_precision('highest')
    identity = ReaderIdentity(config['model_revision'], 'base-no-adapter', digest(tokenizer.chat_template),
                              'fp32_math-tf32-off-broader-raw-v1-' + digest(SYSTEM))
    import transformers
    (root / 'runtime.json').write_bytes(canonical({'torch':torch.__version__, 'transformers':transformers.__version__,
        'model_revision':model.config._commit_hash, 'tokenizer_template_sha256':digest(tokenizer.chat_template),
        'gpu':torch.cuda.get_device_name(), 'reader_dtype':'float32', 'reader_attention_backend':'math',
        'reader_tf32':False, 'note_selector_dtype':'bfloat16', 'trainable_parameters':sum(p.numel() for p in model.parameters() if p.requires_grad)}))
    commit()
    with sdpa_kernel(SDPBackend.MATH):
        gate = transcript_gate(model, tokenizer, identity, root, commit, deadline)
    (root / 'transcript-verdict.json').write_bytes(canonical(gate)); commit()
    if not gate['pass']:
        return {'status': 'transcript_gate_failed', 'gate': gate, 'corpus_trained': False}
    model.bfloat16()
    notes = generate_notes(model, tokenizer, bundle['histories'], worklist, config, root, commit, deadline)
    note_check = validate_notes(tokenizer, bundle['histories'], notes, config['notes_max_tokens'])
    (root / 'note-validation.json').write_bytes(canonical(note_check)); commit()
    model.float()
    captures = []
    with sdpa_kernel(SDPBackend.MATH):
        for question, row in zip(bundle['questions'], schedule):
            query = question['query']['content']; hid = question['persona_id']; view = prepared_views[question['id']]
            if sorted(row['round_order']) != [0, 1, 2]:
                raise ValueError('invalid round schedule')
            transcripts = [reader_messages(notes[hid]['text'], view['recent']['text'], query)]
            for retrieval in view['retrievals']:
                transcripts.append(append_evidence(transcripts[-1], retrieval['text'], query))
            for n in row['round_order']:
                deadline(); messages = transcripts[n]; started = time.monotonic()
                ids = answer_prefix_ids(tokenizer, messages); input_tokens = len(ids)
                if input_tokens + config['max_message_output_tokens'] > config['active_context_max_tokens']:
                    raise ValueError('reader context exceeds cap including output reserve')
                session = AppendOnlySession(model, identity, config['active_context_max_tokens'], last_logit_only=True)
                logits = session.append_transcript(ids, identity)[0][-1]; tokens = []
                for _ in range(config['max_message_output_tokens']):
                    deadline(); token = int(logits.argmax()); tokens.append(token)
                    if token == tokenizer.eos_token_id:
                        break
                    ids.append(token); logits = session.append_transcript(ids, identity)[0][-1]
                result = strict_body_capture(tokenizer, tokens, tokenizer.eos_token_id)
                result.update(id=question['id'], persona_id=hid, retrieval_rounds=n, messages=messages,
                    retrieval=view['retrievals'][:n], input_tokens=input_tokens,
                    actual_forwarded_tokens=session.fresh_tokens, elapsed_seconds=time.monotonic()-started,
                    arm='raw_source', fresh_prefill=True)
                captures.append(result)
                (root / 'captures.json').write_bytes(canonical(captures)); commit()
                print(json.dumps({'stage': 'broader_capture', 'completed': len(captures), 'id': question['id'], 'round': n}), flush=True)
    return {'status': 'awaiting_independent_answer_review', 'captures': len(captures), 'notes': len(notes),
            'gate': gate, 'body_structurally_valid': sum(x['body_structurally_valid'] for x in captures),
            'within_90_words': sum(x['within_90_words'] for x in captures), 'note_check': note_check,
            'generated_action_protocol_valid': None, 'corpus_trained': False, 'trainable_parameters': 0}

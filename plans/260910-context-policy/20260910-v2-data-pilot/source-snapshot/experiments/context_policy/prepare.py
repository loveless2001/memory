"""Bounded development-only dialogue pilot; no training or test scoring."""

import json
import time
from pathlib import Path

import torch

from .corpus import audit_blueprints, build_blueprints, parse_realization, realization_messages
from .preflight import canonical, digest


def pilot_blueprints(rows):
    selected, groups = [], set()
    for split, count in (("train", 7), ("validation", 3)):
        choices = sorted((r for r in rows if r['split'] == split), key=lambda r: digest(r['family_id']))
        for row in choices:
            if row['realization_family'] in groups:
                continue
            selected.append(row); groups.add(row['realization_family'])
            if sum(r['split'] == split for r in selected) == count:
                break
    assert len(selected) == 10 and all(r['split'] != 'internal_test' for r in selected)
    return selected


def run_data_pilot(config, output, numerics_run, commit, deadline):
    from transformers import AutoModelForCausalLM, AutoTokenizer, StoppingCriteria, StoppingCriteriaList
    output, numerics_run = Path(output), Path(numerics_run)
    gate = json.loads((numerics_run / "numerics-verdict.json").read_text())
    if not gate['pass'] or gate['selected_runtime'] != config['reader_runtime']:
        raise ValueError("data preparation requires the matching passed reader gate")
    rows = build_blueprints()
    audit = audit_blueprints(rows)
    pilot = pilot_blueprints(rows)
    (output / "blueprints.private.json").write_bytes(canonical(rows))
    (output / "blueprint-audit.json").write_bytes(canonical(audit))
    (output / "pilot-blueprints.private.json").write_bytes(canonical(pilot))
    commit()
    torch.set_num_threads(4)
    torch.manual_seed(0)
    tokenizer = AutoTokenizer.from_pretrained(config['model_id'], revision=config['model_revision'], local_files_only=True)
    tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = 'left'
    # This is a shared, query-blind fictional dialogue generator, not a reader arm.
    model = AutoModelForCausalLM.from_pretrained(config['model_id'], revision=config['model_revision'],
        local_files_only=True, torch_dtype=torch.bfloat16, attn_implementation='sdpa').to('cuda').eval()
    model.requires_grad_(False)
    class TimeGuard(StoppingCriteria):
        def __call__(self, input_ids, scores, **kwargs):
            deadline()
            return False
    tasks = [(row, session) for row in pilot for session in row['sessions']]
    captures, generation_seconds, generated_tokens = [], 0.0, 0
    for start in range(0, len(tasks), 64):
        deadline()
        group = tasks[start:start+64]
        prompts = [tokenizer.apply_chat_template(realization_messages(row, session), tokenize=False,
                   add_generation_prompt=True) for row, session in group]
        batch = tokenizer(prompts, return_tensors='pt', padding=True, add_special_tokens=False).to('cuda')
        torch.cuda.synchronize(); began = time.monotonic()
        with torch.inference_mode():
            tokens = model.generate(**batch, do_sample=False, min_new_tokens=2048, max_new_tokens=3072,
                                    use_cache=True, logits_to_keep=1, pad_token_id=tokenizer.pad_token_id,
                                    stopping_criteria=StoppingCriteriaList([TimeGuard()]))
        torch.cuda.synchronize(); elapsed = time.monotonic()-began
        generation_seconds += elapsed
        width = batch['input_ids'].shape[1]
        for (row, session), generated in zip(group, tokens[:, width:].tolist()):
            if tokenizer.eos_token_id in generated:
                generated = generated[:generated.index(tokenizer.eos_token_id)]
                ended = True
            else:
                ended = False
            text = tokenizer.decode(generated, skip_special_tokens=True)
            record = {'family_id': row['family_id'], 'session_id': session['session_id'],
                      'generated_tokens': len(generated), 'ended_with_eos': ended, 'text': text}
            generated_tokens += len(generated)
            try:
                record['parsed'] = parse_realization(text, session, tokenizer)
                if not ended:
                    raise ValueError('dialogue reached output-token cap before EOS')
                record['valid'] = True
            except ValueError as exc:
                record['valid'] = False
                record['error'] = str(exc)
            captures.append(record)
        (output / 'dialogue-captures.json').write_bytes(canonical(captures))
        commit()
        print(json.dumps({'phase':'dialogue_pilot','sessions':len(captures),'valid':sum(r['valid'] for r in captures),
                          'generation_seconds':generation_seconds,'generated_tokens':generated_tokens}),flush=True)
        del tokens, batch
    histories = []
    for row in pilot:
        sessions = [r for r in captures if r['family_id'] == row['family_id']]
        total = sum(r['generated_tokens'] for r in sessions)
        histories.append({'family_id':row['family_id'],'tokens':total,
                          'valid':all(r['valid'] for r in sessions) and 16000 <= total <= 48000})
    generation_projection = generation_seconds * len(rows) / len(pilot)
    verdict = {'automated_dialogue_gate_passed':all(r['valid'] for r in histories),
               'human_audit_pending':True,'histories':histories,'sessions':len(captures),
               'valid_sessions':sum(r['valid'] for r in captures),
               'generation_seconds':generation_seconds,'generated_tokens':generated_tokens,
               'generation_tokens_per_second':generated_tokens/max(generation_seconds,1e-9),
               'projected_full_generation_seconds':generation_projection,
               'preparation_total_ceiling_seconds':7200,
               'generation_alone_fits_preparation_ceiling':generation_projection < 7200,
               'note':'Projection excludes notes, embedding, labels, and review; passing it alone does not admit full preparation.',
               'corpus_trained':False}
    (output / 'data-pilot-verdict.json').write_bytes(canonical(verdict))
    commit()
    return verdict

"""Fixed-adapter diagnosis of prefill/decode numerical differences.

Three prespecified execution modes; exact greedy gate remains unchanged.
No policy fitting, external data, or accuracy-based selection occurs here.
"""

from contextlib import nullcontext
import hashlib
import json
import time
from pathlib import Path

import torch
from torch.nn.attention import SDPBackend, sdpa_kernel

from .cache_session import AppendOnlySession, ReaderIdentity
from .preflight import canonical, digest, fixtures, messages


MODES = ("bf16_auto", "bf16_math", "fp32_math")


def top_logits(logits, tokenizer):
    values, ids = logits.float().topk(5)
    return [{"id": int(i), "text": tokenizer.decode([int(i)]), "logit": float(v)}
            for i, v in zip(ids, values)]


def run_numerics(config, output, previous, commit, deadline):
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer
    output, previous = Path(output), Path(previous)
    started = time.monotonic()
    torch.set_num_threads(4)
    torch.manual_seed(0)
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    torch.set_float32_matmul_precision("highest")
    previous_reader = json.loads((previous / "reader.json").read_text())
    adapter = previous / "disposable-preflight-adapter"
    adapter_sha = hashlib.sha256((adapter / "adapter_model.safetensors").read_bytes()).hexdigest()
    assert adapter_sha == previous_reader["adapter_sha256"]
    tokenizer = AutoTokenizer.from_pretrained(config["model_id"], revision=config["model_revision"], local_files_only=True)
    template_sha = hashlib.sha256(tokenizer.chat_template.encode()).hexdigest()
    assert template_sha == previous_reader["template_sha256"]
    base = AutoModelForCausalLM.from_pretrained(config["model_id"], revision=config["model_revision"],
        local_files_only=True, torch_dtype=torch.bfloat16, attn_implementation="sdpa").to("cuda")
    assert base.config._commit_hash == config["model_revision"]
    model = PeftModel.from_pretrained(base, str(adapter), is_trainable=False).eval()
    model.requires_grad_(False)
    rows = fixtures()
    assert digest(rows) == previous_reader["fixture_sha256"]
    (output / "fixtures.json").write_bytes(canonical(rows))
    metadata = {"previous_run": previous.name, "adapter_sha256": adapter_sha,
                "template_sha256": template_sha, "fixture_sha256": digest(rows),
                "model_revision": config["model_revision"], "modes": list(MODES),
                "gpu": torch.cuda.get_device_name(), "tf32": False,
                "trainable_parameters": sum(p.numel() for p in model.parameters() if p.requires_grad),
                "selection": "first exact-gate passing mode in bf16_auto, bf16_math, fp32_math order; all arms must use it",
                "note": "FP32 upcasts the same stored BF16 base weights; adapter remains its saved precision."}
    (output / "reader.json").write_bytes(canonical(metadata))
    commit()

    @torch.inference_mode()
    def fresh(ids):
        return model(input_ids=torch.tensor([ids], device="cuda"), use_cache=False,
                     logits_to_keep=1).logits[0, -1].float()

    results = {}
    original_checks = json.loads((previous / "cache-checks.json").read_text())
    original_failure = next(r for r in original_checks if r['cached_tokens'] != r['fresh_tokens'])
    divergence = next(i for i, (a, b) in enumerate(zip(original_failure['cached_tokens'], original_failure['fresh_tokens'])) if a != b)
    failing_fixture = next(r for r in rows if r['id'] == original_failure['id'])
    for mode in MODES:
        deadline()
        if mode == "fp32_math":
            model.float()
        identity = ReaderIdentity(config["model_revision"], adapter_sha, template_sha, mode + "-tf32-off")
        context = nullcontext() if mode == "bf16_auto" else sdpa_kernel(SDPBackend.MATH)
        checks = []
        mode_start = time.monotonic()
        with context:
            # Exactly the same original divergent prefix in all three modes,
            # independent of any precision-dependent change to free generation.
            history = messages(failing_fixture)
            ids = tokenizer.apply_chat_template(history, tokenize=True, add_generation_prompt=True)
            probe_session = AppendOnlySession(model, identity, last_logit_only=True)
            for retrieval in range(3):
                probe_logits = probe_session.append_transcript(ids, identity)[0][-1].float()
                if retrieval < 2:
                    history += [{"role": "assistant", "content": "RETRIEVE"},
                                {"role": "tool", "content": failing_fixture['evidence'] if retrieval == 0 else "No additional evidence found."}]
                    ids = tokenizer.apply_chat_template(history, tokenize=True, add_generation_prompt=True)
            for token in original_failure['cached_tokens'][:divergence]:
                ids.append(token)
                probe_logits = probe_session.append_transcript(ids, identity)[0][-1].float()
            full_probe = fresh(ids)
            fixed_probe = {"id": failing_fixture['id'], "step": divergence, "prefix_sha256": digest(ids),
                           "cached_top5": top_logits(probe_logits, tokenizer), "fresh_top5": top_logits(full_probe, tokenizer),
                           "max_abs_logit_delta": float((probe_logits-full_probe).abs().max()),
                           "argmax_equal": int(probe_logits.argmax()) == int(full_probe.argmax())}
            (output / f"{mode}-fixed-prefix.json").write_bytes(canonical(fixed_probe))
            for row in rows:
                deadline()
                history = messages(row)
                ids = tokenizer.apply_chat_template(history, tokenize=True, add_generation_prompt=True)
                session = AppendOnlySession(model, identity, last_logit_only=True)
                stages = []
                for retrieval in range(3):
                    cached = session.append_transcript(ids, identity)[0][-1].float()
                    full = fresh(ids)
                    stages.append({"tokens": len(ids), "argmax_equal": int(cached.argmax()) == int(full.argmax()),
                                   "max_abs_logit_delta": float((cached-full).abs().max())})
                    if retrieval < 2:
                        history += [{"role": "assistant", "content": "RETRIEVE"},
                                    {"role": "tool", "content": row["evidence"] if retrieval == 0 else "No additional evidence found."}]
                        more = tokenizer.apply_chat_template(history, tokenize=True, add_generation_prompt=True)
                        assert more[:len(ids)] == ids
                        ids = more
                cached_ids, full_ids = list(ids), list(ids)
                cached_generated, full_generated = [], []
                cached_done = full_done = False
                first_difference = None
                shared_prefix_deltas = []
                for step in range(16):
                    deadline()
                    if cached_ids == full_ids and not cached_done and not full_done:
                        shared_prefix_deltas.append(float((cached-full).abs().max()))
                        if int(cached.argmax()) != int(full.argmax()) and first_difference is None:
                            first_difference = {"step": step, "shared_prefix_sha256": digest(cached_ids),
                                                "shared_prefix_tokens": cached_ids,
                                                "cached_top5": top_logits(cached, tokenizer),
                                                "fresh_top5": top_logits(full, tokenizer),
                                                "max_abs_logit_delta": shared_prefix_deltas[-1]}
                    if not cached_done:
                        token = int(cached.argmax())
                        cached_generated.append(token)
                        cached_done = token == tokenizer.eos_token_id
                        if not cached_done:
                            cached_ids.append(token)
                            cached = session.append_transcript(cached_ids, identity)[0][-1].float()
                    if not full_done:
                        token = int(full.argmax())
                        full_generated.append(token)
                        full_done = token == tokenizer.eos_token_id
                        if not full_done:
                            full_ids.append(token)
                            full = fresh(full_ids)
                    if cached_done and full_done:
                        break
                checks.append({"id": row["id"], "stages": stages,
                               "equal": cached_generated == full_generated and all(x['argmax_equal'] for x in stages),
                               "cached_tokens": cached_generated, "fresh_tokens": full_generated,
                               "cached_text": tokenizer.decode(cached_generated), "fresh_text": tokenizer.decode(full_generated),
                               "max_shared_prefix_logit_delta": max(shared_prefix_deltas),
                               "first_difference": first_difference})
                if len(checks) % 4 == 0:
                    (output / f"{mode}-checks.json").write_bytes(canonical(checks))
                    commit()
                    print(json.dumps({"mode": mode, "completed": len(checks), "failures": sum(not x['equal'] for x in checks)}), flush=True)
        results[mode] = {"pass": all(x['equal'] for x in checks), "checked": len(checks),
                         "failed_ids": [x['id'] for x in checks if not x['equal']],
                         "max_shared_prefix_logit_delta": max(x['max_shared_prefix_logit_delta'] for x in checks),
                         "elapsed_seconds": time.monotonic()-mode_start}
        (output / "mode-summary.json").write_bytes(canonical(results))
        commit()
    selected = next((m for m in MODES if results[m]['pass']), None)
    verdict = {"pass": selected is not None, "selected_runtime": selected, "modes": results,
               "elapsed_seconds": time.monotonic()-started, "previous_failure_preserved": True,
               "corpus_trained": False, "runtime_change_requires_new_identity": selected not in (None, "bf16_auto")}
    (output / "numerics-verdict.json").write_bytes(canonical(verdict))
    commit()
    return verdict

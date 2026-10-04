"""Actual pinned 4B/LoRA cache gate. No corpus training or test-set access."""

import hashlib
import json
import time
from pathlib import Path

import torch

from .cache_session import AppendOnlySession, ReaderIdentity


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def source_manifest(root, remote=False):
    paths = ["CONTEXT-POLICY.md", "pyproject.toml"]
    paths += [str(p.relative_to(root)) for p in sorted((root / "experiments/context_policy").glob("*.py"))]
    paths += ["experiments/context_policy/design.json"]
    out = {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in paths}
    runner = root / ("modal-context-policy.py" if remote else "modal-runners/modal-context-policy.py")
    out["modal-runners/modal-context-policy.py"] = hashlib.sha256(runner.read_bytes()).hexdigest()
    return out


def fixtures():
    """Forty deterministic development probes; distinct from future training data."""
    mechanisms = [
        ("A proposal to move the review to Tuesday was rejected. The accepted meeting remains Thursday.",
         "Which day is the accepted review?", "Thursday"),
        ("The deadline moved from May 8 to May 12. The requirement for two reviewers remains in force.",
         "How many reviewers are still required?", "two"),
        ("Atlas East stores exports for 14 days. Atlas West stores exports for 30 days.",
         "How long does Atlas East retain exports?", "14 days"),
        ("Session 1: Mira owns the audit. Session 2: the audit owner must approve releases.",
         "Who must approve releases?", "Mira"),
        ("Use metric units for all reports. A later discussion changed the cover color to blue.",
         "Which units should a report use?", "metric"),
        ("We discussed the lunch menu. No supplier contract or price was mentioned.",
         "What is the supplier contract price?", "not established"),
        ("The staging service uses port 8123. Production uses port 8443. Only staging was restarted.",
         "What port does production use?", "8443"),
        ("On June 2 the draft was approved. On June 4 that approval was withdrawn pending a review.",
         "Is the draft currently approved?", "No"),
    ]
    out = []
    for repeat in range(5):
        for kind, (evidence, question, answer) in enumerate(mechanisms):
            out.append({"id": f"cache-probe-{repeat}-{kind}", "kind": kind,
                        "padding_repetitions": [0, 8, 32, 80, 160][repeat],
                        "evidence": evidence, "question": question, "answer": answer})
    return out


def messages(row):
    # Padding tests realistic context lengths; it is explicitly not training data.
    unrelated = "A separate meeting covered the document layout and accessibility review. "
    return [
        {"role": "system", "content": "Answer using the supplied history. Emit exactly RETRIEVE to request evidence, or ANSWER on its own line followed by your answer. Abstain if the history does not establish an answer."},
        {"role": "user", "content": f"Notes: {unrelated * row['padding_repetitions']}\nQuestion: {row['question']}"},
    ]


def paired_greedy(cached_logits, full_logits, cached_step, full_step, eos_id, deadline, limit=16):
    """Stop each trajectory at its own EOS; do not compare post-message garbage."""
    cached_tokens, full_tokens = [], []
    cached_done = full_done = False
    for _ in range(limit):
        deadline()
        if not cached_done:
            next_id = int(cached_logits.argmax())
            cached_tokens.append(next_id)
            cached_done = next_id == eos_id
            if not cached_done:
                cached_logits = cached_step(next_id)
        if not full_done:
            next_id = int(full_logits.argmax())
            full_tokens.append(next_id)
            full_done = next_id == eos_id
            if not full_done:
                full_logits = full_step(next_id)
        if cached_done and full_done:
            break
    return cached_tokens, full_tokens


def run_preflight(config, output, commit, deadline):
    from peft import LoraConfig, get_peft_model
    from transformers import AutoModelForCausalLM, AutoTokenizer

    output = Path(output)
    started = time.monotonic()
    torch.set_num_threads(4)
    torch.manual_seed(0)
    tokenizer = AutoTokenizer.from_pretrained(config["model_id"], revision=config["model_revision"], local_files_only=True)
    model = AutoModelForCausalLM.from_pretrained(
        config["model_id"], revision=config["model_revision"], local_files_only=True,
        torch_dtype=torch.bfloat16, attn_implementation="sdpa").to("cuda")
    assert model.config._commit_hash == config["model_revision"]
    adapter_cfg = LoraConfig(**config["lora"], task_type="CAUSAL_LM")
    model = get_peft_model(model, adapter_cfg)
    trainable = [(n, p) for n, p in model.named_parameters() if p.requires_grad]
    assert trainable and all("lora_" in n and ("q_proj" in n or "v_proj" in n) for n, p in trainable)
    metadata = {"gpu": torch.cuda.get_device_name(), "torch": torch.__version__,
                "trainable_parameters": sum(p.numel() for _, p in trainable),
                "trainable_names": [n for n, _ in trainable],
                "frozen_parameters": sum(p.numel() for p in model.parameters() if not p.requires_grad),
                "template_sha256": hashlib.sha256(tokenizer.chat_template.encode()).hexdigest()}
    # Two optimization steps are a disposable gradient check, not corpus training.
    optimizer = torch.optim.AdamW([p for _, p in trainable], lr=1e-4)
    batch = tokenizer("History: The accepted review is Thursday.\nANSWER\nThursday", return_tensors="pt").to("cuda")
    model.train()
    losses = []
    for step in range(2):
        deadline()
        optimizer.zero_grad(set_to_none=True)
        loss = model(**batch, labels=batch["input_ids"], use_cache=False).loss
        assert torch.isfinite(loss)
        loss.backward()
        assert all(p.grad is not None and torch.isfinite(p.grad).all() for _, p in trainable)
        assert any(p.grad.abs().max() > 0 for _, p in trainable)
        assert all(p.grad is None for p in model.parameters() if not p.requires_grad)
        optimizer.step()
        losses.append(float(loss.detach()))
    del optimizer
    model.eval()
    model.save_pretrained(output / "disposable-preflight-adapter", safe_serialization=True)
    adapter_sha = hashlib.sha256((output / "disposable-preflight-adapter/adapter_model.safetensors").read_bytes()).hexdigest()
    identity = ReaderIdentity(config["model_revision"], adapter_sha, metadata["template_sha256"], "bf16-sdpa-torch2.7.1-transformers4.55.2-peft0.17.0")
    rows = fixtures()
    (output / "fixtures.json").write_bytes(canonical(rows))
    metadata.update(gradient_check_losses=losses, adapter_sha256=adapter_sha, fixture_sha256=digest(rows))
    (output / "reader.json").write_bytes(canonical(metadata))
    commit()
    results = []

    @torch.inference_mode()
    def fresh(ids):
        return model(input_ids=torch.tensor([ids], device="cuda"), use_cache=False,
                     logits_to_keep=1).logits[0, -1].float()

    for row in rows:
        deadline()
        history = messages(row)
        ids = tokenizer.apply_chat_template(history, tokenize=True, add_generation_prompt=True)
        session = AppendOnlySession(model, identity, last_logit_only=True)
        errors = []
        numerical = []
        stages = []
        for round_id in range(3):
            deadline()
            reused, _ = session.append_transcript(ids, identity)
            current = fresh(ids)
            numerical.append(float((reused[-1].float() - current).abs().max()))
            stages.append({"tokens": len(ids), "argmax_equal": int(reused[-1].argmax()) == int(current.argmax())})
            if not stages[-1]["argmax_equal"]:
                errors.append(f"append_{round_id}_argmax")
            if round_id < 2:
                history += [{"role": "assistant", "content": "RETRIEVE"},
                            {"role": "tool", "content": row["evidence"] if round_id == 0 else "No additional evidence found."}]
                updated = tokenizer.apply_chat_template(history, tokenize=True, add_generation_prompt=True)
                if updated[:len(ids)] != ids:
                    raise ValueError("actual Qwen chat template changed the cached prefix")
                ids = updated
        prefix = list(ids)
        full_ids = list(prefix)
        def cached_step(token):
            prefix.append(token)
            return session.append_transcript(prefix, identity)[0][-1].float()
        def full_step(token):
            full_ids.append(token)
            return fresh(full_ids)
        cached_generated, full_generated = paired_greedy(
            reused[-1].float(), current, cached_step, full_step, tokenizer.eos_token_id, deadline)
        if cached_generated != full_generated:
            errors.append("greedy_sequence")
        # Deliberately switch the adapter without changing the supplied identity.
        # The cache owner must reject this, then a fresh session may use it.
        model.disable_adapter_layers()
        try:
            session.append_transcript(list(session.token_ids) + [1], identity)
        except ValueError as exc:
            assert "adapter selection changed" in str(exc)
        else:
            raise AssertionError("silently disabled adapter accepted by live cache")
        finally:
            model.enable_adapter_layers()
        results.append({"id": row["id"], "stages": stages, "max_abs_logit_delta": max(numerical),
                        "cached_tokens": cached_generated, "fresh_tokens": full_generated,
                        "cached_text": tokenizer.decode(cached_generated),
                        "fresh_text": tokenizer.decode(full_generated), "errors": errors})
        (output / "cache-checks.json").write_bytes(canonical(results))
        if len(results) % 4 == 0:
            commit()
            print(json.dumps({"phase": "cache_preflight", "completed": len(results), "failures": sum(bool(x['errors']) for x in results)}), flush=True)
    verdict = {"pass": all(not r["errors"] for r in results), "checked_prompts": len(results),
               "failed_prompts": [r["id"] for r in results if r["errors"]],
               "max_abs_logit_delta": max(r["max_abs_logit_delta"] for r in results),
               "elapsed_seconds": time.monotonic()-started,
               "gradient_check_passed": True, "actual_chat_prefix_passed": True,
               "silent_adapter_disable_rejected": True,
               "trained_on_corpus": False}
    (output / "preflight-verdict.json").write_bytes(canonical(verdict))
    commit()
    return verdict

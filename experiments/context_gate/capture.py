"""Frozen-reader capture and sequential deployed-branch replay."""

from __future__ import annotations

import json
import random
import time
from pathlib import Path

import numpy as np
import torch

from .data import LETTERS, canonical, digest, render_messages, surface_features


class FrozenReader:
    def __init__(self, config):
        from transformers import AutoModelForCausalLM, AutoTokenizer
        from memsub.fingerprint import compute_fingerprint

        self.config = config
        torch.set_num_threads(4)
        self.tokenizer = AutoTokenizer.from_pretrained(config["model_id"], revision=config["model_revision"], local_files_only=True)
        self.tokenizer.padding_side = "left"
        self.tokenizer.pad_token = self.tokenizer.eos_token
        self.model = AutoModelForCausalLM.from_pretrained(
            config["model_id"], revision=config["model_revision"], local_files_only=True,
            torch_dtype=torch.bfloat16, attn_implementation="sdpa").to("cuda").eval()
        self.model.requires_grad_(False)
        assert self.model.config._commit_hash == config["model_revision"], "model revision drift"
        assert not any(p.requires_grad for p in self.model.parameters())
        self.letters = {}
        for label in (*LETTERS, "R", "S"):
            ids = self.tokenizer.encode(label, add_special_tokens=False)
            assert len(ids) == 1, f"{label} is not one token"
            self.letters[label] = ids[0]
        self.fingerprint = compute_fingerprint(
            self.model.config, self.tokenizer,
            model_id=config["model_id"] + "@" + config["model_revision"],
            attention_impl="sdpa", quantization="bfloat16", device="cuda").to_dict()
        self.metadata = {"fingerprint": self.fingerprint, "model_revision": config["model_revision"],
                         "parameters": sum(p.numel() for p in self.model.parameters()), "trainable_backbone_parameters": 0,
                         "gpu": torch.cuda.get_device_name(), "torch": torch.__version__,
                         "action_token_ids": self.letters, "hidden_layer": config["hidden_layer"]}

    def text(self, row, arm):
        return self.tokenizer.apply_chat_template(render_messages(row, arm), tokenize=False,
                                                  add_generation_prompt=True, enable_thinking=False)

    def evidence_tokens(self, row, oracle=False):
        indices = row["oracle_indices" if oracle else "retrieved_indices"]
        text = "\n".join(f"Turn {row['archive'][i]['turn']}: {row['archive'][i]['text']}" for i in indices)
        return len(self.tokenizer.encode(text, add_special_tokens=False))

    @torch.inference_mode()
    def infer(self, rows, arm="notes", hidden=False):
        texts = [self.text(row, arm) for row in rows]
        batch = self.tokenizer(texts, return_tensors="pt", padding=True, add_special_tokens=False)
        lengths = batch["attention_mask"].sum(1).numpy()
        if max(lengths) > self.config["max_prompt_tokens"]:
            raise ValueError(f"prompt overflow: {max(lengths)}")
        for row in rows:
            if self.evidence_tokens(row) > self.config["max_retrieved_tokens"]:
                raise ValueError("retrieved evidence exceeds budget")
        batch = {k: v.to("cuda") for k, v in batch.items()}
        position_ids = batch["attention_mask"].long().cumsum(-1) - 1
        position_ids.masked_fill_(batch["attention_mask"] == 0, 0)
        torch.cuda.synchronize()
        started = time.monotonic()
        # Avoid materializing vocabulary logits for every prompt position.
        out = self.model.model(**batch, position_ids=position_ids, use_cache=False, output_hidden_states=hidden)
        logits = self.model.lm_head(out.last_hidden_state[:, -1]).float()
        labels = ("R", "S") if arm == "decision" else tuple(LETTERS)
        chosen_ids = [self.letters[x] for x in labels]
        probs = logits[:, chosen_ids].softmax(-1).cpu().numpy()
        first_token_valid = torch.isin(logits.argmax(-1), torch.tensor(chosen_ids, device=logits.device)).cpu().numpy()
        features = out.hidden_states[self.config["hidden_layer"]][:, -1].float().cpu().numpy() if hidden else None
        torch.cuda.synchronize()
        elapsed = time.monotonic()-started
        if not np.isfinite(probs).all() or (features is not None and not np.isfinite(features).all()):
            raise ValueError("nonfinite frozen-model capture")
        del out, logits
        return {"probs": probs, "tokens": lengths, "seconds": np.full(len(rows), elapsed / len(rows)),
                "format_valid": first_token_valid, "hidden": features}


def capture_batch(reader, rows):
    result = {"item_ids": np.asarray([r["item_id"] for r in rows]),
              "retrieved_tokens": np.asarray([reader.evidence_tokens(r) for r in rows]),
              "oracle_tokens": np.asarray([reader.evidence_tokens(r, True) for r in rows])}
    answers = np.asarray([LETTERS.index(r["answer"]) for r in rows])
    for arm in ("notes", "retrieved", "oracle", "decision"):
        info = reader.infer(rows, arm, hidden=arm == "notes")
        for name in ("tokens", "seconds", "format_valid"):
            result[f"{name}_{arm}"] = info[name]
        if arm == "decision":
            result["self_probability"] = info["probs"][:, 0]
        else:
            result[f"probs_{arm}"] = info["probs"]
            result[f"correct_{arm}"] = (info["probs"].argmax(1) == answers).astype(np.int64)
        if arm == "notes":
            result["hidden"] = info["hidden"].astype(np.float16)
            result["surface"] = np.stack([surface_features(row, int(n), p)
                                           for row, n, p in zip(rows, info["tokens"], info["probs"])])
    return result


def capture_rows(reader, rows, directory, commit, check_time):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    dataset_sha = digest(rows)
    state_path = directory / "state.json"
    state = {"dataset_sha256": dataset_sha, "completed": 0, "chunks": []}
    # This campaign never silently resumes across changed code/config or overwrites a chunk.
    if state_path.exists():
        raise FileExistsError(f"capture namespace already used: {directory}")
    chunks = []
    for start in range(0, len(rows), reader.config["batch_size"]):
        check_time()
        group = rows[start:start+reader.config["batch_size"]]
        cap = capture_batch(reader, group)
        filename = f"rows-{start:05d}-{start+len(group):05d}.npz"
        path = directory / filename
        np.savez_compressed(path, **cap)
        sha = __import__("hashlib").sha256(path.read_bytes()).hexdigest()
        chunks.append(cap)
        state["completed"] = start+len(group)
        state["chunks"].append({"file": filename, "sha256": sha, "rows": len(group)})
        state_path.write_bytes(canonical(state))
        commit()
        if start == 0 or state["completed"] % 80 == 0 or state["completed"] == len(rows):
            print(f"capture {directory.name}: {state['completed']}/{len(rows)}", flush=True)
    return {key: np.concatenate([c[key] for c in chunks], axis=0) for key in chunks[0]}


def smoke_verdict(rows, cap, elapsed, config, spent):
    repairs = int(((cap["correct_notes"] == 0) & (cap["correct_retrieved"] == 1)).sum())
    oracle_accuracy = float(cap["correct_oracle"].mean())
    # Allow conservative CPU training/replay headroom on top of full capture projection.
    projected = elapsed / len(rows) * sum(config["episodes"].values()) * 3 + 600
    checks = {"oracle_accuracy_at_least_0_60": oracle_accuracy >= .60,
              "at_least_three_repairs": repairs >= 3,
              "runtime_fits": projected < config["gpu_seconds_limit"]-spent,
              "three_families": len({r["family"] for r in rows}) == 3,
              "finite_hidden": bool(np.isfinite(cap["hidden"]).all()),
              "retrieval_budget": bool((cap["retrieved_tokens"] <= config["max_retrieved_tokens"]).all())}
    return {"pass": all(checks.values()), "checks": checks, "repairs": repairs,
            "notes_accuracy": float(cap["correct_notes"].mean()),
            "retrieved_accuracy": float(cap["correct_retrieved"].mean()),
            "oracle_accuracy": oracle_accuracy, "projected_remaining_seconds": projected,
            "measured_smoke_seconds": elapsed,
            "format_valid_rates": {arm: float(cap[f"format_valid_{arm}"].mean()) for arm in ("notes", "retrieved", "oracle", "decision")}}


def sequential_replay(reader, rows, cap, config, output_dir, commit, check_time):
    from .learning import load_ensemble

    out = Path(output_dir)
    policy = json.loads((out / "frozen-policy.json").read_text())
    models = {name: load_ensemble(out / name) for name in ("surface_mlp", "hidden_mlp")}
    test_episodes = list(dict.fromkeys(r["episode_id"] for r in rows if r["split"] == "test"))[:config["replay_episodes"]]
    selected = [(i, r) for i, r in enumerate(rows) if r["episode_id"] in test_episodes]
    arms = ["notes_only", "always_retrieve", "self_raw", "confidence", "surface_mlp", "hidden_mlp"]
    reader.infer([selected[0][1]], "notes", hidden=True)
    records = []
    saved_scores = np.load(out / "controller-scores.npz")
    for ix, row in selected:
        check_time()
        order = arms[:]
        random.Random(row["item_id"]).shuffle(order)
        for arm in order:
            torch.cuda.synchronize()
            started = time.monotonic()
            tokens = 0
            if arm == "always_retrieve":
                decision = True
            elif arm == "self_raw":
                first = reader.infer([row], "decision")
                tokens += int(first["tokens"][0])
                decision = bool(first["probs"][0, 0] >= .5)
            else:
                first = reader.infer([row], "notes", hidden=arm == "hidden_mlp")
                tokens += int(first["tokens"][0])
                if arm == "notes_only":
                    decision = False
                elif arm == "confidence":
                    score = float(1-first["probs"][0].max())
                    decision = score >= policy["thresholds"][arm]["threshold"]
                else:
                    s = surface_features(row, int(first["tokens"][0]), first["probs"][0])
                    # Quantization matches persisted training captures.
                    x = s
                    if arm == "hidden_mlp":
                        h = first["hidden"][0].astype(np.float16).astype(np.float32)
                        x = np.concatenate((h, s))
                    p = models[arm](x[None])[0]
                    decision = bool(p[2]-p[0] >= policy["thresholds"][arm]["threshold"])
            if decision:
                final = reader.infer([row], "retrieved")
                tokens += int(final["tokens"][0])
            elif arm == "self_raw":
                final = reader.infer([row], "notes")
                tokens += int(final["tokens"][0])
            else:
                final = first
            predicted = LETTERS[int(final["probs"][0].argmax())]
            torch.cuda.synchronize()
            elapsed = time.monotonic()-started
            original_decision = bool(saved_scores[f"decision_{arm}"][ix])
            original_prediction = LETTERS[int(cap["probs_retrieved" if decision else "probs_notes"][ix].argmax())]
            records.append({"item_id": row["item_id"], "arm": arm, "retrieve": bool(decision),
                            "prediction": predicted, "correct": predicted == row["answer"], "input_tokens": tokens,
                            "wall_seconds": elapsed, "matches_capture_decision": bool(decision) == original_decision,
                            "matches_capture_answer": predicted == original_prediction})
        (out / "replay-rows.json").write_bytes(canonical(records))
        commit()
    summary = {"rows_per_arm": len(selected), "arms": {}}
    for arm in arms:
        group = [r for r in records if r["arm"] == arm]
        summary["arms"][arm] = {"accuracy": float(np.mean([r["correct"] for r in group])),
                                  "retrieval_rate": float(np.mean([r["retrieve"] for r in group])),
                                  "mean_input_tokens": float(np.mean([r["input_tokens"] for r in group])),
                                  "mean_wall_seconds": float(np.mean([r["wall_seconds"] for r in group])),
                                  "median_wall_seconds": float(np.median([r["wall_seconds"] for r in group])),
                                  "p95_wall_seconds": float(np.quantile([r["wall_seconds"] for r in group], .95)),
                                  "decision_drift_count": sum(not r["matches_capture_decision"] for r in group),
                                  "answer_drift_count": sum(not r["matches_capture_answer"] for r in group)}
    (out / "replay-summary.json").write_bytes(canonical(summary))
    commit()
    return summary

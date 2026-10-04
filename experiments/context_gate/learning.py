"""Utility-controller training and locked evaluation for ContextGate v1."""

from __future__ import annotations

import copy
import json
import time
from pathlib import Path

import numpy as np
import torch
from torch import nn


def utility_labels(notes_correct, retrieved_correct):
    """Classes 0,1,2 encode harm, neutral, and repair, respectively."""
    return np.asarray(retrieved_correct, dtype=np.int64) - np.asarray(notes_correct, dtype=np.int64) + 1


def make_model(dim, hidden):
    return (nn.Sequential(nn.Linear(dim, hidden), nn.GELU(), nn.Linear(hidden, 3))
            if hidden else nn.Sequential(nn.Linear(dim, 3)))


def fit_ensemble(x, y, splits, config, directory, hidden):
    """No test features/labels participate in scaling, fitting, or stopping."""
    started = time.monotonic()
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    tr, va = np.flatnonzero(splits == "train"), np.flatnonzero(splits == "validation")
    mean = x[tr].mean(axis=0)
    scale = np.maximum(x[tr].std(axis=0), .01)
    z = torch.from_numpy(((x - mean) / scale).astype(np.float32))
    labels = torch.from_numpy(y).long()
    histories, checkpoints, probabilities = [], [], []
    for seed in config["training_seeds"]:
        torch.manual_seed(seed)
        model = make_model(x.shape[1], hidden)
        initial = {k: v.detach().clone() for k, v in model.state_dict().items()}
        optim = torch.optim.AdamW(model.parameters(), lr=config["learning_rate"], weight_decay=config["weight_decay"])
        loss_fn = nn.CrossEntropyLoss()
        best, best_epoch, stale, trace = float("inf"), -1, 0, []
        with torch.no_grad():
            initial_loss = float(loss_fn(model(z[tr]), labels[tr]))
        state = None
        for epoch in range(config["epochs"]):
            model.train()
            order = tr[torch.randperm(len(tr)).numpy()]
            grad_norms = []
            for start in range(0, len(order), 128):
                ix = order[start:start+128]
                optim.zero_grad(set_to_none=True)
                loss = loss_fn(model(z[ix]), labels[ix])
                if not torch.isfinite(loss):
                    raise ValueError("nonfinite controller loss")
                loss.backward()
                grad = nn.utils.clip_grad_norm_(model.parameters(), 5.)
                if not torch.isfinite(grad):
                    raise ValueError("nonfinite controller gradient")
                grad_norms.append(float(grad))
                optim.step()
            model.eval()
            with torch.no_grad():
                train_loss = float(loss_fn(model(z[tr]), labels[tr]))
                val_loss = float(loss_fn(model(z[va]), labels[va]))
            trace.append({"epoch": epoch, "train_loss": train_loss, "validation_loss": val_loss,
                          "max_gradient_norm": max(grad_norms)})
            if val_loss < best - 1e-6:
                best, best_epoch, stale = val_loss, epoch, 0
                state = copy.deepcopy(model.state_dict())
            else:
                stale += 1
            if stale >= config["patience"]:
                break
        assert state is not None
        model.load_state_dict(state)
        model.eval()
        with torch.no_grad():
            p = model(z).softmax(-1).numpy()
            final_loss = float(loss_fn(model(z[tr]), labels[tr]))
        change = sum(float((state[k]-initial[k]).square().sum()) for k in state) ** .5
        if not change > 0:
            raise ValueError("controller did not change")
        checkpoint = {"state_dict": state, "mean": torch.from_numpy(mean), "scale": torch.from_numpy(scale),
                      "input_dim": x.shape[1], "hidden_width": hidden, "seed": seed,
                      "best_epoch": best_epoch, "class_order": ["harm", "neutral", "repair"]}
        path = directory / f"seed-{seed}.pt"
        torch.save(checkpoint, path)
        # Verify the artifact we will actually use, rather than the in-memory model alone.
        restored = load_checkpoint(path)
        np.testing.assert_allclose(p, restored(x), atol=1e-6, rtol=1e-5)
        probabilities.append(p)
        checkpoints.append(str(path))
        histories.append({"seed": seed, "best_epoch": best_epoch, "initial_train_loss": initial_loss,
                          "selected_train_loss": final_loss, "selected_validation_loss": best,
                          "weight_change_l2": change, "history": trace})
        print(f"controller={directory.name} seed={seed} best_epoch={best_epoch} "
              f"train_loss={initial_loss:.4f}->{final_loss:.4f} validation={best:.4f}", flush=True)
    metadata = {"seeds": histories, "checkpoints": checkpoints, "elapsed_seconds": time.monotonic()-started,
                "reload_equivalence": True}
    (directory / "training.json").write_text(json.dumps(metadata, indent=2) + "\n")
    return np.mean(probabilities, axis=0), metadata


def load_checkpoint(path):
    ck = torch.load(path, map_location="cpu", weights_only=True)
    model = make_model(ck["input_dim"], ck["hidden_width"])
    model.load_state_dict(ck["state_dict"])
    model.eval()
    def predict(x):
        with torch.no_grad():
            z = (torch.as_tensor(x, dtype=torch.float32) - ck["mean"]) / ck["scale"]
            return model(z).softmax(-1).numpy()
    return predict


def load_ensemble(directory):
    models = [load_checkpoint(p) for p in sorted(Path(directory).glob("seed-*.pt"))]
    if len(models) != 3:
        raise ValueError("expected all three fixed seeds")
    def predict(x):
        return np.mean([model(x) for model in models], axis=0)
    return predict


def choose_threshold(score, c0, c1, penalty):
    """Calibration-only maximization with deterministic low-retrieval ties."""
    candidates = np.unique(np.concatenate(([-2.], score, [2.])))
    best = None
    for tau in candidates:
        decision = score >= tau
        acc = np.where(decision, c1, c0).mean()
        rate = decision.mean()
        objective = float(acc - penalty * rate)
        key = (round(objective, 12), -float(rate), float(tau))
        if best is None or key > best[0]:
            best = (key, {"threshold": float(tau), "accuracy": float(acc),
                          "retrieval_rate": float(rate), "utility": objective})
    return best[1]


def paired_interval(values, groups, bootstrap=2000, seed=20260910):
    """Episode cluster bootstrap. Each sampled cluster retains all note views."""
    unique = np.unique(groups)
    sums = np.asarray([values[groups == g].sum() for g in unique])
    counts = np.asarray([(groups == g).sum() for g in unique])
    rng = np.random.default_rng(seed)
    draws = rng.integers(len(unique), size=(bootstrap, len(unique)))
    means = sums[draws].sum(1) / counts[draws].sum(1)
    return {"estimate": float(np.mean(values)), "ci95": np.quantile(means, [.025, .975]).tolist(),
            "clusters": len(unique)}


def arm_vectors(name, decision, cap):
    """Per-item correctness and conservative total prefill accounting.

    Gating pays for its initial prompt even when the second prompt is used.
    All second prompts are rebuilt without cache reuse.
    """
    c0, c1 = cap["correct_notes"], cap["correct_retrieved"]
    if name == "oracle_evidence":
        return cap["correct_oracle"], cap["tokens_oracle"], cap["seconds_oracle"]
    if name == "always_retrieve":
        return c1, cap["tokens_retrieved"], cap["seconds_retrieved"]
    correct = np.where(decision, c1, c0)
    if name in ("self_raw", "self_calibrated"):
        tokens = cap["tokens_decision"] + np.where(decision, cap["tokens_retrieved"], cap["tokens_notes"])
        seconds = cap["seconds_decision"] + np.where(decision, cap["seconds_retrieved"], cap["seconds_notes"])
    else:
        tokens = cap["tokens_notes"] + decision * cap["tokens_retrieved"]
        seconds = cap["seconds_notes"] + decision * cap["seconds_retrieved"]
    return correct, tokens, seconds


def metrics_for_arm(name, decision, cap, mask, rows):
    correct, tokens, seconds = arm_vectors(name, decision, cap)
    benefit = (cap["correct_retrieved"] > cap["correct_notes"])
    harm = (cap["correct_retrieved"] < cap["correct_notes"])
    prior = cap["correct_oracle"].astype(bool)
    # Oracle evidence is always an evidence arm; its decision mask is all true.
    out = {"n": int(mask.sum()), "accuracy": float(correct[mask].mean()),
           "retrieval_rate": float(decision[mask].mean()),
           "all_error_rate": float((1-correct[mask]).mean()),
           "error_without_retrieval": float(((1-correct) * ~decision)[mask].mean()),
           "missed_repair_count": int((benefit & ~decision & mask).sum()),
           "harmful_retrieval_count": int((harm & decision & mask).sum()),
           "unnecessary_retrieval_count": int((~benefit & decision & mask).sum()),
           "mean_input_tokens": float(tokens[mask].mean()),
           "mean_capture_seconds_estimate": float(seconds[mask].mean()),
           "mean_retrieved_tokens": float((decision * cap["retrieved_tokens"])[mask].mean()),
           "oracle_conditioned_loss": float((1-correct)[mask & prior].mean()) if (mask & prior).any() else None}
    if name == "oracle_evidence":
        out["mean_retrieved_tokens"] = float(cap["oracle_tokens"][mask].mean())
        for key in ("missed_repair_count", "harmful_retrieval_count", "unnecessary_retrieval_count"):
            out[key] = None
    out["slices"] = {}
    for field in ("family", "note_policy"):
        for value in sorted({r[field] for r in rows}):
            m = mask & np.asarray([r[field] == value for r in rows])
            if m.any():
                out["slices"][f"{field}:{value}"] = {"n": int(m.sum()), "accuracy": float(correct[m].mean()),
                                                     "retrieval_rate": float(decision[m].mean())}
    return out


def train_and_evaluate(rows, cap, config, output_dir):
    from sklearn.metrics import roc_auc_score

    torch.set_num_threads(4)
    out = Path(output_dir)
    split = np.asarray([r["split"] for r in rows])
    groups = np.asarray([r["episode_id"] for r in rows])
    y = utility_labels(cap["correct_notes"], cap["correct_retrieved"])
    class_counts = {part: np.bincount(y[split == part], minlength=3).tolist() for part in np.unique(split)}
    # Only training/calibration class counts can affect whether fitting proceeds.
    if class_counts["train"][2] < 20 or sum(class_counts["train"][:2]) < 20:
        return {"status": "label_starvation", "class_counts": class_counts}
    if class_counts["calibration"][2] < 5 or sum(class_counts["calibration"][:2]) < 5:
        return {"status": "calibration_starvation", "class_counts": class_counts}
    x_surface = cap["surface"].astype(np.float32)
    x_hidden = np.concatenate((cap["hidden"].astype(np.float32), x_surface), axis=1)
    scores = {"confidence": 1-cap["probs_notes"].max(axis=1), "self_calibrated": cap["self_probability"]}
    probability, training = {}, {}
    for name, x, width in (("surface_mlp", x_surface, config["hidden_width"]),
                           ("hidden_linear", x_hidden, 0),
                           ("hidden_mlp", x_hidden, config["hidden_width"])):
        probability[name], training[name] = fit_ensemble(x, y, split, config, out / name, width)
        scores[name] = probability[name][:, 2] - probability[name][:, 0]
    cal = split == "calibration"
    c0, c1 = cap["correct_notes"], cap["correct_retrieved"]
    thresholds = {name: choose_threshold(s[cal], c0[cal], c1[cal], config["retrieval_penalty"])
                  for name, s in scores.items()}
    decisions = {name: scores[name] >= op["threshold"] for name, op in thresholds.items()}
    decisions.update({"notes_only": np.zeros(len(rows), dtype=bool),
                      "always_retrieve": np.ones(len(rows), dtype=bool),
                      "self_raw": cap["self_probability"] >= .5,
                      "oracle_evidence": np.ones(len(rows), dtype=bool),
                      "oracle_action": y == 2})
    candidates = ("notes_only", "always_retrieve", "self_raw", "self_calibrated", "confidence", "surface_mlp")
    cal_comparators = {}
    for name in candidates:
        correct, tokens, _ = arm_vectors(name, decisions[name], cap)
        cal_comparators[name] = {"accuracy": float(correct[cal].mean()),
                                "utility": float((correct - config["retrieval_penalty"]*decisions[name])[cal].mean()),
                                "mean_input_tokens": float(tokens[cal].mean())}
    comparator = max(candidates, key=lambda n: (cal_comparators[n]["utility"], -cal_comparators[n]["mean_input_tokens"]))
    frozen = {"thresholds": thresholds, "comparator": comparator, "calibration_comparators": cal_comparators,
              "primary": "hidden_mlp", "training_seeds": config["training_seeds"]}
    # Persist the frozen policy selection before producing any held-out metrics.
    (out / "frozen-policy.json").write_text(json.dumps(frozen, indent=2) + "\n")
    result = {"status": "trained", "class_counts": class_counts, "frozen_policy": frozen, "training": training, "evaluation": {}}
    for part in ("test", "ood"):
        m = split == part
        arms = {name: metrics_for_arm(name, d, cap, m, rows) for name, d in decisions.items()}
        primary, tokens, _ = arm_vectors("hidden_mlp", decisions["hidden_mlp"], cap)
        other, other_tokens, _ = arm_vectors(comparator, decisions[comparator], cap)
        accuracy = paired_interval((primary-other)[m], groups[m], config["bootstrap_samples"])
        utility = paired_interval((primary-other-config["retrieval_penalty"]*(decisions["hidden_mlp"].astype(float)-decisions[comparator]))[m],
                                  groups[m], config["bootstrap_samples"])
        diagnostics = {}
        for name, score in scores.items():
            benefit = (y[m] == 2).astype(int)
            diagnostics[name] = {"benefit_auc": float(roc_auc_score(benefit, score[m])) if len(np.unique(benefit)) == 2 else None}
            if name in probability:
                diagnostics[name]["benefit_brier"] = float(np.mean((probability[name][m, 2]-benefit)**2))
        result["evaluation"][part] = {"arms": arms, "paired_accuracy_vs_comparator": accuracy,
                                        "paired_utility_vs_comparator": utility, "diagnostics": diagnostics,
                                        "paired_input_tokens_vs_comparator": paired_interval((tokens-other_tokens)[m], groups[m], config["bootstrap_samples"]),
                                        "input_token_ratio": float(tokens[m].mean()/other_tokens[m].mean()),
                                        "input_token_difference": float((tokens-other_tokens)[m].mean())}
    test = result["evaluation"]["test"]
    accuracy_route = (test["paired_accuracy_vs_comparator"]["ci95"][0] > 0
               and test["paired_utility_vs_comparator"]["ci95"][0] > 0
               and test["input_token_difference"] <= 0)
    efficiency_route = (test["paired_accuracy_vs_comparator"]["ci95"][0] >= -.02
                        and test["input_token_ratio"] <= .9
                        and test["paired_input_tokens_vs_comparator"]["ci95"][1] < 0)
    result["advance_routes"] = {"accuracy": accuracy_route, "efficiency": efficiency_route}
    result["verdict"] = "advance" if accuracy_route or efficiency_route else "does_not_advance"
    np.savez_compressed(out / "controller-scores.npz", item_ids=np.asarray([r["item_id"] for r in rows]),
                        **scores, **{f"decision_{n}": d for n, d in decisions.items()})
    (out / "results.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    return result

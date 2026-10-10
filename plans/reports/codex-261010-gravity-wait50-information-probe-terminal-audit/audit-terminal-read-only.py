"""Terminal provenance/data/metric audit; no model construction, forward, ridge fit, bootstrap or launch."""
import datetime
import hashlib
import importlib.util
import json
import math
import pathlib
import shutil
import subprocess

import numpy as np
import torch
from safetensors import safe_open

OUT = pathlib.Path(__file__).resolve().parent
ROOT = OUT.parents[2]
D = ROOT / "plans/261010-0107-m4-sgm-qwen-value-token-previous-key-information-probe"
SNAPSHOT = ROOT / "plans/reports/codex-261010-gravity-22425-information-probe-v06-audit/sources-935f91d"

def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

R = load(SNAPSHOT / "scripts/sgm-p2p5-previous-key-probe-stage-receipts-and-admission-validation.py", "rx50_terminal")
M = R.M
from memsub.sgm.synthetic_binding_task import BindingTaskSpec, KEY_RANGES, VALUE_BASE, N_VALUES, sample_batch
from memsub.sgm.pinned_pretrained_qwen3_backbone import snapshot_dir, verify_files

assert (D / "chain-status.txt").read_text().strip() == "COMPLETE"
v = R.validate_full(D / "probe-run-v1", D / "s1-smoke", D / "s2-smoke")
stage_receipts = {mode: R.validate_receipt(D / stem, mode) for mode, stem in
                  (("s1", "s1-smoke"), ("s2", "s2-smoke"), ("full", "probe-run-v1"))}
result = R.strict_json(D / "probe-run-v1/result.json")
assert result["reading"]["read"] is True
assert result["run"]["git_head"] == "935f91dba30f439c60e1424a40ba05b382985883"
assert result["run"]["wall_s"] == 5075

index = json.loads((SNAPSHOT.parent / "reviewed-source-index.json").read_text())
drift = [r["path"] for r in index["files"] if hashlib.sha256((ROOT / r["path"]).read_bytes()).hexdigest() != r["sha256"]]
assert not drift, drift

key_counts = {}
with np.load(D / "probe-run-v1/features.npz", allow_pickle=False) as z:
    saved = {k: z[k].copy() for k in ("fit_key_ids", "fit_value_ids", "ev_key_ids", "ev_value_ids")}
    headers = {k: {"shape": list(z[k].shape), "dtype": str(z[k].dtype)} for k in z.files}

spec = BindingTaskSpec(n_bindings=32, n_queries=4, filler_len=40)
data_checks = {}
for pre, mode_key in (("fit", "fit"), ("ev", "ev")):
    split, n, seed = R.MODES["full"][mode_key]
    gen = torch.Generator().manual_seed(seed)
    keys, vals = [], []
    for done in range(0, n, 4):
        batch = sample_batch(spec, split, min(4, n - done), gen)
        keys.append(batch.source[:, 4:68:2].numpy())
        vals.append(batch.source[:, 5:68:2].numpy())
    keys, vals = np.concatenate(keys), np.concatenate(vals)
    assert np.array_equal(keys, saved[f"{pre}_key_ids"])
    assert np.array_equal(vals, saved[f"{pre}_value_ids"])
    lo, hi = KEY_RANGES[split]
    assert np.all((keys >= lo) & (keys < hi))
    assert all(len(set(row.tolist())) == 32 for row in keys)
    assert np.all((vals >= VALUE_BASE) & (vals < VALUE_BASE + N_VALUES))
    data_checks[pre] = {"split": split, "episodes": n, "seed": seed, "generator_ids_match": True,
                        "unique_key_ids": len(np.unique(keys)), "key_range": [int(keys.min()), int(keys.max())]}
assert not (set(saved["fit_key_ids"].reshape(-1)) & set(saved["ev_key_ids"].reshape(-1)))

# Read only the key-embedding rows from the pinned weight file. This does not instantiate Qwen.
cache = snapshot_dir()
verified_weights = verify_files(cache)
with safe_open(cache / "model.safetensors", framework="pt", device="cpu") as f:
    key_embedding_block = f.get_slice("model.embed_tokens.weight")[10000:11000, :].to(torch.float32).numpy()
embed = key_embedding_block[saved["fit_key_ids"] - 10000]
target = embed / np.linalg.norm(embed, axis=-1, keepdims=True)
y = target.reshape(-1, target.shape[-1])
perm = M.null_permutations(96, 32, R.MODES["full"]["seeds"]["perm_fit"])
yshuf = np.take_along_axis(target, perm[..., None], 1).reshape(y.shape)
true_target_sha = hashlib.sha256(np.ascontiguousarray(y).tobytes()).hexdigest()[:16]
shuf_target_sha = hashlib.sha256(np.ascontiguousarray(yshuf).tobytes()).hexdigest()[:16]
assert true_target_sha != shuf_target_sha

stats, rows = {}, []
denominator = 64 * 32
for layer in R.LAYERS:
    stats[layer] = {}
    for feature in R.SETS:
        metric = result["metrics"][f"L{layer}/{feature}"]
        trip = metric["top1_point_lo_hi"]
        assert 0 <= trip[1] <= trip[2] <= 1
        assert math.isclose(trip[0] * denominator, round(trip[0] * denominator), abs_tol=1e-7)
        assert 0 <= metric["mean_rank"] <= 31
        assert math.isclose(metric["mean_rank"] * denominator, round(metric["mean_rank"] * denominator), abs_tol=1e-7)
        assert metric["fit_target_sha256"] == (shuf_target_sha if feature == "V-shuf" else true_target_sha)
        level = 1 - (M.NULL_ALPHA if feature in ("E_v", "V-shuf") else M.LAYER_ALPHA)
        assert metric["two_sided_level"] == level
        cv = {float(k): score for k, score in metric["cv_top1"].items()}
        assert set(cv) == set(M.LAMBDAS) and all(0 <= score <= 1 for score in cv.values())
        assert metric["lambda"] == max(M.LAMBDAS, key=lambda lam: (cv[lam], lam))
        stats[layer][feature] = tuple(trip)
    delta = result["metrics"][f"L{layer}/dVK"]["point_lo_hi"]
    desc = result["metrics"][f"L{layer}/dVK_vs_K (descriptive)"]["point_lo_hi"]
    assert delta[0] == stats[layer]["V+K"][0] - stats[layer]["V"][0]
    assert desc[0] == stats[layer]["V+K"][0] - stats[layer]["K"][0]
    assert result["metrics"][f"L{layer}/dVK"]["two_sided_level"] == 1 - M.LAYER_ALPHA
    stats[layer]["dVK"] = tuple(delta)
    rows.append({"layer": layer, "V": stats[layer]["V"], "K": stats[layer]["K"],
                 "V+K": stats[layer]["V+K"], "E_v": stats[layer]["E_v"],
                 "V-shuf": stats[layer]["V-shuf"], "delta_VK_minus_V": delta,
                 "delta_VK_minus_K_descriptive": desc})
reading = M.reading(stats, 1 / 32)
assert reading["label"] == result["reading"]["label"] == "CARRIED"
assert reading["calibrated_layers"] == result["reading"]["calibrated_layers"]
assert reading["invalid_cells"] == result["reading"]["invalid_cells"] == []
assert {str(k): value for k, value in reading["q2"].items()} == result["reading"]["q2"]

copies = OUT / "terminal-copies"
copies.mkdir()
for stem in ("s1-smoke", "s2-smoke", "probe-run-v1"):
    dest = copies / stem
    dest.mkdir()
    for name in ("run.json", "status.json", "result.json", "progress.log"):
        shutil.copyfile(D / stem / name, dest / name)
    if stem == "s1-smoke":
        shutil.copyfile(D / stem / "admission.json", dest / "admission.json")
    shutil.copyfile(D / (stem + ".exit"), copies / (stem + ".exit"))
shutil.copyfile(D / "probe-run-v1/features.npz", copies / "probe-run-v1/features.npz")
assert hashlib.sha256((copies / "probe-run-v1/features.npz").read_bytes()).hexdigest() == result["run"]["features_sha256"]
for name in ("chain.log", "chain-status.txt"):
    shutil.copyfile(D / name, copies / name)
scope_lines = subprocess.check_output(["systemctl", "--user", "list-units", "--type=scope", "--state=active", "--no-legend", "--plain", "pkprobe-*"], text=True).splitlines()
assert not scope_lines, scope_lines
assert all(not (pathlib.Path("/proc") / str(pid)).exists() for pid in (216781, 220812, 220813))

audit = {"utc": datetime.datetime.now(datetime.timezone.utc).isoformat(), "stage_receipts": stage_receipts,
         "full_validation": v, "head": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
         "source_files_checked": len(index["files"]), "source_drift": drift, "weight_files_verified": verified_weights,
         "initial_adapter_hash_all_stages": v["initial_adapter_params_sha256"], "data_checks": data_checks,
         "fit_eval_keys_disjoint": True, "feature_headers": headers,
         "fit_targets_verified": {"true": true_target_sha, "uniform_shuffle": shuf_target_sha},
         "reading_recomputed": reading, "metrics_rows": rows, "timing_s": result["timing_s"],
         "peak_rss_mb": result["peak_rss_mb"], "no_active_scopes_or_controller_worker_pids": True,
         "auditor_model_constructions_or_forwards": 0, "auditor_probe_refits_or_bootstrap_reruns": 0}
(OUT / "audit-checks.json").write_text(json.dumps(audit, indent=2, allow_nan=False) + "\n")
print(json.dumps({"full_receipt": v, "data_checks": data_checks, "targets_verified": audit["fit_targets_verified"],
                  "rows": rows, "active_scopes": scope_lines, "refits": 0}, indent=1))

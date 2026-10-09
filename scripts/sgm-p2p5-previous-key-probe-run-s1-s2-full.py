"""Run the previous-key information probe (proposal v0.3): --mode s1 | s2 | full.

s1  capture/fixed-lambda smoke (2 fit + 2 eval episodes), profiles the full-run cost and writes
    admission.json (full-run wall = 2 x estimate, refuse above 4 h).
s2  full-path smoke (4 fit + 2 eval episodes, 4-fold episode CV); its numbers are NOT read.
full one run (96 train + 64 heldout episodes); requires an admitting S1 admission.json.
The launcher wraps every invocation in a cgroup scope + `timeout --signal=KILL <wall>`; --wall-s must
equal the frozen/admitted wall. No retry anywhere; the output dir must not exist.
"""

from __future__ import annotations

import argparse
import gc
import hashlib
import importlib.util
import json
import math
import resource
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]

def require(ok: bool, msg: str) -> None:
    """Explicit refusal (survives python -O, unlike assert)."""
    if not ok:
        raise RuntimeError(msg)

MATH_PATH = ROOT / "scripts/sgm-p2p5-previous-key-probe-ridge-retrieval-readings.py"
CAPTURE_PATH = ROOT / "scripts/sgm-p2p5-previous-key-probe-capture-qwen-adapter-inputs.py"
MODES = {   # split, episodes, seed; smokes use their own seeds (codex 22390 §5)
    "s1": {"fit": ("train", 2, 9_799_011), "ev": ("heldout", 2, 9_799_021), "cv": False, "wall": 1800,
           "seeds": {"perm_fit": 9_799_031, "perm_ev": 9_799_032, "folds": 9_799_041, "boot": 9_799_051}},
    "s2": {"fit": ("train", 4, 9_799_012), "ev": ("heldout", 2, 9_799_022), "cv": True, "wall": 2400,
           "seeds": {"perm_fit": 9_799_031, "perm_ev": 9_799_032, "folds": 9_799_041, "boot": 9_799_051}},
    "full": {"fit": ("train", 96, 9_700_011), "ev": ("heldout", 64, 9_700_021), "cv": True, "wall": None,
             "seeds": {"perm_fit": 9_700_031, "perm_ev": 9_700_032, "folds": 9_700_041, "boot": 9_700_051}},
}
N_BOOT, THREADS, FIXED_LAMBDA = 4000, 8, 1.0
SETS = ("V", "V+K", "K", "E_v", "V-shuf")


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    return mod


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def check_wall(args) -> None:
    m = MODES[args.mode]
    if args.mode != "full":
        require(args.wall_s == m["wall"], f"--wall-s must equal the frozen {m['wall']} s")
        return
    adm = json.loads(Path(args.admission).read_text())
    require(adm["admit"], "S1 admission refused the full run")
    require(args.wall_s == math.ceil(adm["wall_s"]), f"--wall-s must equal ceil(admitted wall) {math.ceil(adm['wall_s'])}")
def features(cap: dict, layer: int, keys_emb: np.ndarray, vals_emb: np.ndarray) -> dict:
    zv, zk = cap[f"zv_L{layer}"], cap[f"zk_L{layer}"]
    flat = lambda a: a.reshape(-1, a.shape[-1])   # noqa: E731
    return {"V": flat(zv), "V+K": flat(np.concatenate([zv, zk], -1)), "K": flat(zk),
            "E_v": flat(vals_emb), "V-shuf": flat(zv)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=MODES, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--wall-s", type=int, required=True)
    ap.add_argument("--admission", default=None)
    args = ap.parse_args()
    check_wall(args)                                            # before any model load
    args.out.mkdir(parents=True, exist_ok=False)
    M, C = load(MATH_PATH, "pkmath"), load(CAPTURE_PATH, "pkcap")
    import torch
    torch.set_num_threads(THREADS)
    m, seeds, t = MODES[args.mode], MODES[args.mode]["seeds"], {"start": time.time()}
    run = {"mode": args.mode, "wall_s": args.wall_s, "threads": THREADS, "n_boot": N_BOOT, "seeds": seeds,
           "fit": m["fit"], "ev": m["ev"], "git_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
           "sha256": {p.name: sha(p) for p in (Path(__file__), MATH_PATH, CAPTURE_PATH, C.MANIFEST)}}
    (args.out / "run.json").write_text(json.dumps(run, indent=1) + "\n")
    pcfg, runtime, backend = C.load_model(); t["loaded"] = time.time()
    cap_fit = C.capture(runtime, backend, pcfg, *m["fit"]); cap_ev = C.capture(runtime, backend, pcfg, *m["ev"])
    t["captured"] = time.time()
    emb = {k: (C.embeddings(runtime, c["key_ids"]), C.embeddings(runtime, c["value_ids"])) for k, c in (("fit", cap_fit), ("ev", cap_ev))}
    del runtime, backend; gc.collect()                          # release the model before solves
    t["released"] = time.time()
    np.savez(args.out / "features.npz", **{f"fit_{k}": v for k, v in cap_fit.items() if k != "layers"},
             **{f"ev_{k}": v for k, v in cap_ev.items() if k != "layers"})
    run["features_sha256"] = sha(args.out / "features.npz")
    nf, ne, nb = m["fit"][1], m["ev"][1], cap_fit["key_ids"].shape[1]
    tgt = {k: v[0] / np.linalg.norm(v[0], axis=-1, keepdims=True) for k, v in emb.items()}   # [E, 32, d]
    ep_f, ep_e = np.repeat(np.arange(nf), nb), np.repeat(np.arange(ne), nb)
    ti_f, ti_e = np.tile(np.arange(nb), nf), np.tile(np.arange(nb), ne)
    pf, pe = M.null_permutations(nf, nb, seeds["perm_fit"]), M.null_permutations(ne, nb, seeds["perm_ev"])
    y_true_f = tgt["fit"].reshape(-1, tgt["fit"].shape[-1])
    y_shuf_f = np.take_along_axis(tgt["fit"], pf[..., None], 1).reshape(y_true_f.shape)
    folds = M.episode_folds(nf, min(4, nf), seeds["folds"]) if m["cv"] else None
    idx = M.bootstrap_index(ne, N_BOOT, seeds["boot"])
    metrics, stats, per_ep = {}, {}, {}
    for layer in cap_fit["layers"]:
        Ff, Fe = features(cap_fit, layer, *emb["fit"]), features(cap_ev, layer, *emb["ev"])
        stats[layer] = {}
        for s in SETS:
            y = y_shuf_f if s == "V-shuf" else y_true_f
            ti_fit = pf.reshape(-1) if s == "V-shuf" else ti_f     # shuffled: true = permuted binding's key
            ti_eval = pe.reshape(-1) if s == "V-shuf" else ti_e
            if m["cv"]:
                lam, table = M.cv_select_lambda(Ff[s], y, ep_f, folds, tgt["fit"], ti_fit)
            else:
                lam, table = FIXED_LAMBDA, None
            model = M.ridge_path(Ff[s], y, (lam,))
            ranks = M.retrieval_ranks(M.predict(model, lam, Fe[s]), tgt["ev"], ep_e, ti_eval)
            per_ep[(layer, s)] = M.episode_top1(ranks, ep_e, ne)
            alpha = M.NULL_ALPHA if s in ("E_v", "V-shuf") else M.LAYER_ALPHA
            stats[layer][s] = M.interval(per_ep[(layer, s)], idx, alpha)
            metrics[f"L{layer}/{s}"] = {"lambda": lam, "cv_top1": table, "top1_point_lo_hi": stats[layer][s],
                                        "fit_target_sha256": hashlib.sha256(np.ascontiguousarray(y).tobytes()).hexdigest()[:16],
                                        "two_sided_level": 1 - alpha, "mean_rank": float(ranks.mean())}
        stats[layer]["dVK"] = M.interval(per_ep[(layer, "V+K")] - per_ep[(layer, "V")], idx, M.LAYER_ALPHA)
        metrics[f"L{layer}/dVK"] = {"point_lo_hi": stats[layer]["dVK"], "two_sided_level": 1 - M.LAYER_ALPHA}
        metrics[f"L{layer}/dVK_vs_K (descriptive)"] = {"point_lo_hi": M.interval(per_ep[(layer, "V+K")] - per_ep[(layer, "K")], idx, M.LAYER_ALPHA)}
    t["fitted"] = time.time()
    rd = M.reading(stats, 1 / nb)
    rd["read"] = args.mode == "full"
    rd["note"] = "per-statistic Bonferroni over 4 layers (null family over 8); no joint coverage claimed over mixed verdicts"
    out = {"run": run, "metrics": metrics, "reading": rd,
           "timing_s": {k: v - t["start"] for k, v in t.items()},
           "peak_rss_mb": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024}
    if args.mode == "s1":
        out["admission"] = profile_and_admit(M, t, nf + ne, out_bytes=(args.out / "features.npz").stat().st_size)
        (args.out / "admission.json").write_text(json.dumps(out["admission"], indent=1) + "\n")
    (args.out / "result.json").write_text(json.dumps(out, indent=1, default=float) + "\n")
    print(json.dumps({"mode": args.mode, "label": rd["label"], "read": rd["read"], "timing_s": out["timing_s"]}, indent=1))


def profile_and_admit(M, t: dict, n_cap: int, out_bytes: int) -> dict:
    """Full-shape fit/predict/bootstrap timing on synthetic data (model already released), so the
    dimension-dependent SVD cost (rank up to 1024/2048) enters the bound, not an episode multiplier."""
    rng = np.random.default_rng(0)
    def timed(fn):   # noqa: E306
        a = time.time(); fn(); return time.time() - a
    y_cv, y_fin = rng.normal(size=(2304, 1024)), rng.normal(size=(3072, 1024))
    cand = rng.normal(size=(64, 32, 1024))
    tm = {}
    for d in (1024, 2048):
        x_cv, x_fin = rng.normal(size=(2304, d)), rng.normal(size=(3072, d))
        tm[f"cv_fit_{d}"] = timed(lambda: M.ridge_path(x_cv, y_cv))
        mod = M.ridge_path(x_cv, y_cv)
        xv = rng.normal(size=(768, d))
        tm[f"cv_pred_{d}"] = timed(lambda: [M.retrieval_ranks(M.predict(mod, l, xv), cand[:24], np.repeat(np.arange(24), 32), np.tile(np.arange(32), 24)) for l in M.LAMBDAS])
        tm[f"final_fit_{d}"] = timed(lambda: M.ridge_path(x_fin, y_fin, (1.0,)))
    per_ep = rng.random(64); idx = M.bootstrap_index(64, N_BOOT, 1)
    tm["boot_one"] = timed(lambda: M.interval(per_ep, idx, M.LAYER_ALPHA))
    per_set = lambda d: 4 * (tm[f"cv_fit_{d}"] + tm[f"cv_pred_{d}"]) + tm[f"final_fit_{d}"] + tm[f"cv_pred_{d}"] / 2   # noqa: E731
    fit_s = 4 * (4 * per_set(1024) + per_set(2048))
    boot_s = tm["boot_one"] * 4 * 8
    full_bytes = out_bytes * 160 / n_cap
    output_s = 30.0 + full_bytes / 50e6                          # >= 50 MB/s write + JSON/cleanup allowance
    cap_per_ep = (t["captured"] - t["loaded"]) / n_cap
    adm = M.admission(cap_per_ep, 160, t["loaded"] - t["start"], fit_s, boot_s, output_s)
    return {**adm, "components": {"capture_s_per_episode": cap_per_ep, "model_load_s": t["loaded"] - t["start"],
                                  "fit_s": fit_s, "boot_s": boot_s, "output_s": output_s, "timings": tm}}


if __name__ == "__main__":
    main()

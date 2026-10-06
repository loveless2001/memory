"""P2.5 option A step 2: parity of the SGM-path speed-up vs the PROFILED reference memsub.

    python scripts/sgm-p2p5-sgm-path-speedup-parity-check.py --out <dir> --ref-tree <dir with memsub/> \
        [--suite tiny-cpu|qwen-gpu]

The reference is memsub exactly as committed at the profiled commit (2fda0d4, source
048df640...), imported under the package name `memsub_ref`; the candidate is the
working-tree `memsub`. Both run the real `train()` for the same PilotConfig (dev seed
99, never a registered/artifact/reserved population), with torch.Tensor.backward and
AdamW.step wrapped to capture every update's loss and every parameter gradient. Then
one dev evaluation batch (seed 4242) through each package's `evaluate`.
Checked scope (codex 21492/21493): initial weights (bitwise), per-update loss,
per-update gradients (bound to parameter names), final weights, dev predictions and dev
accuracy. Reported as max abs / max relative (to the reference tensor's max |x|)
differences; PASS needs zero structural problems, every relative diff <= --rtol and
identical dev predictions/accuracy. "bitwise" means bitwise over THAT scope only.
NOT verified: training telemetry rows and dev numeric fields other than accuracy (the
differing float fields are listed in `dev_float_fields_differing` for information).

Isolation (codex 21484): `memsub_ref` is a separate package name with relative imports;
after the suite every loaded `memsub_ref.*` module must live under the reference copy,
every `memsub.*` module under the working tree, and no function/class reachable from a
`memsub_ref.*` module namespace may come from `memsub.*` (recorded in `isolation`).
Self-test: the first case is re-run with the candidate's delta update perturbed by a
relative 1e-3; parity MUST fail for it (`self_test_perturbation_detected`), else FAIL.
"""

import argparse
import functools
import gc
import importlib
import json
import shutil
import sys
import tempfile
import time
import types
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from memsub.sgm.synthetic_pilot_run import source_tree_sha256  # noqa: E402

TINY = dict(backbone="tiny", device="cpu", n_bindings=16, filler_len=8, batch=4, steps=3, seed=99, eval_every=10 ** 9)
SUITES = {
    "tiny-cpu": [dict(TINY, arm=a, readout=r) for a in ("learned", "single_cell", "random_fixed", "oracle")
                 for r in ("taskhead", "residual_head")]
                + [dict(TINY, arm="learned", readout="taskhead", filler_writes=False),
                   dict(TINY, arm="learned", readout="taskhead", aux_address_lambda=0.1),
                   dict(TINY, arm="memory_off", readout="residual_head")],
    "qwen-gpu": [dict(backbone="qwen3-0.6b-base", device="cuda", readout="residual_head", arm=a, n_bindings=32,
                      batch=b, steps=2, seed=99, eval_every=10 ** 9, filler_len=40, filler_len_schedule=((0, f),))
                 for a, b, f in (("learned", 16, 0), ("learned", 16, 40), ("oracle", 4, 40),
                                 ("single_cell", 4, 40), ("random_fixed", 4, 40), ("memory_off", 4, 40))],
}
CAPTURE: dict = {}


def install_capture():
    orig_backward, orig_step = torch.Tensor.backward, torch.optim.AdamW.step

    @functools.wraps(orig_backward)
    def backward(self, *a, **k):
        CAPTURE["loss"].append(self.detach().double().cpu())
        return orig_backward(self, *a, **k)

    @functools.wraps(orig_step)
    def step(self, *a, **k):
        CAPTURE["grads"].append([None if p.grad is None else p.grad.detach().cpu().clone()
                                 for g in self.param_groups for p in g["params"]])
        return orig_step(self, *a, **k)
    torch.Tensor.backward, torch.optim.AdamW.step = backward, step


def load_ref(tree: Path, name: str = "memsub_ref"):
    tmp = Path(tempfile.mkdtemp(prefix="memsub-ref-"))
    shutil.copytree(tree / "memsub", tmp / name, ignore=shutil.ignore_patterns("__pycache__"))
    sys.path.insert(0, str(tmp))
    return importlib.import_module(name), source_tree_sha256(tree / "memsub"), tmp / name


def isolation_evidence(ref_root: Path) -> dict:
    """Which files each package actually loaded, and any cross-package leak."""
    ref_files = {n: getattr(m, "__file__", None) for n, m in sys.modules.items() if n.split(".")[0] == "memsub_ref"}
    cand_files = {n: getattr(m, "__file__", None) for n, m in sys.modules.items() if n.split(".")[0] == "memsub"}
    def origin(v) -> str:                     # defining package of a function/class, or a module's name
        return v.__name__ if isinstance(v, types.ModuleType) else str(getattr(v, "__module__", "") or "")
    leaks = sorted(f"{n}.{a}" for n in ref_files for a, v in vars(sys.modules[n]).items()
                   if origin(v).split(".")[0] == "memsub")
    ok = (bool(ref_files) and bool(cand_files) and not leaks
          and all(f is None or Path(f).resolve().is_relative_to(ref_root.resolve()) for f in ref_files.values())
          and all(f is None or Path(f).resolve().is_relative_to((ROOT / "memsub").resolve())
                  for f in cand_files.values()))
    return {"ok": ok, "leaks": leaks, "ref_modules": ref_files, "cand_modules": cand_files}


def perturbed_candidate():
    """Context: candidate delta update x (1 + 1e-3) — parity must detect it."""
    import contextlib
    from memsub.runtime import sgm_model_runtime as rt
    orig = rt.delta_update

    @contextlib.contextmanager
    def ctx():
        rt.delta_update = lambda *a, **k: orig(*a, **k) * (1 + 1e-3)
        try:
            yield
        finally:
            rt.delta_update = orig
    return ctx()


def run(pkg: str, kw: dict) -> dict:
    pilot = importlib.import_module(f"{pkg}.sgm.synthetic_pilot")
    ev = importlib.import_module(f"{pkg}.sgm.synthetic_pilot_evaluation")
    pcfg = pilot.PilotConfig(**kw)
    init, orig_build = {}, pilot.build

    def build(c):                                  # train()'s own build, weights captured untouched
        out = orig_build(c)
        init.update({f"adapters.{k}": v.detach().cpu().clone() for k, v in out[0].adapters.state_dict().items()})
        init.update({f"head.{k}": v.detach().cpu().clone() for k, v in out[2].state_dict().items()})
        return out
    CAPTURE.update(loss=[], grads=[])
    pilot.build = build
    try:
        t0 = time.monotonic()
        res = pilot.train(pcfg, log=lambda _r: None)
        train_s = time.monotonic() - t0
    finally:
        pilot.build = orig_build
    weights = {**{f"adapters.{k}": v for k, v in res["runtime"].adapters.state_dict().items()},
               **{f"head.{k}": v for k, v in res["head"].state_dict().items()}}
    per_example: list = []
    dev = ev.evaluate(res["backend"], res["head"], pcfg.task_spec(), pcfg.arm, pcfg.readout, split="heldout",
                      batches=1, batch_size=pcfg.batch, seed=4242, per_example=per_example,
                      filler_writes=pcfg.filler_writes)
    rt, head = res["runtime"], res["head"]            # train()'s optimizer order: adapters then head
    names = ([f"adapters.{n}" for n, q in rt.adapters.named_parameters() if q.requires_grad]
             + [f"head.{n}" for n, q in head.named_parameters() if q.requires_grad])
    return {"init": init, "loss": list(CAPTURE["loss"]), "grads": list(CAPTURE["grads"]), "train_s": train_s,
            "param_names": names,
            "weights": {k: v.detach().cpu() for k, v in weights.items()}, "dev": dev,
            "preds": [r["pred"] for r in per_example], "telemetry": res["telemetry"]}


def diff(a: torch.Tensor, b: torch.Tensor) -> tuple[float, float, bool, str | None]:
    """(max abs, max rel to max|ref|, bitwise equal, problem). Fail-closed (codex 21488):
    shape/dtype mismatch or ANY non-finite value on either side is a problem."""
    if a.shape != b.shape or a.dtype != b.dtype:
        return float("inf"), float("inf"), False, f"shape/dtype {tuple(a.shape)}/{a.dtype} vs {tuple(b.shape)}/{b.dtype}"
    a, b = a.double(), b.double()
    if not (torch.isfinite(a).all() and torch.isfinite(b).all()):
        return float("inf"), float("inf"), False, "non-finite value"
    d = float((a - b).abs().max()) if a.numel() else 0.0
    scale = float(a.abs().max()) if a.numel() else 0.0
    return d, (d / scale if scale > 0 else (0.0 if d == 0 else float("inf"))), torch.equal(a, b), None


def compare(ref: dict, cand: dict, rtol: float) -> dict:
    """Strict structure (codex 21488): identical init (bitwise), key sets, update counts,
    per-update gradient name lists and presence; then tolerance on values."""
    problems, rows = [], []
    if ref["init"].keys() != cand["init"].keys():
        problems.append("init key sets differ")
    for k in ref["init"].keys() & cand["init"].keys():
        d = diff(ref["init"][k], cand["init"][k])
        if not d[2]:
            problems.append(f"init/{k} not bitwise equal")
    if len(ref["loss"]) != len(cand["loss"]) or len(ref["loss"]) == 0:
        problems.append(f"loss counts {len(ref['loss'])} vs {len(cand['loss'])}")
    if len(ref["grads"]) != len(cand["grads"]) or len(ref["grads"]) != len(ref["loss"]):
        problems.append(f"grad update counts {len(ref['grads'])} vs {len(cand['grads'])}")
    if ref["param_names"] != cand["param_names"]:
        problems.append("optimizer parameter names/order differ")
    rows += [(f"loss/u{u}", *diff(la, lb)) for u, (la, lb) in enumerate(zip(ref["loss"], cand["loss"]))]
    for u, (ga, gb) in enumerate(zip(ref["grads"], cand["grads"])):
        if not (len(ga) == len(gb) == len(ref["param_names"])):
            problems.append(f"u{u}: gradient list lengths {len(ga)}/{len(gb)} vs {len(ref['param_names'])} params")
            continue
        for name, a, b in zip(ref["param_names"], ga, gb):
            if (a is None) != (b is None):
                problems.append(f"u{u}: grad presence differs for {name}")
            elif a is not None:
                rows.append((f"grad/u{u}/{name}", *diff(a, b)))
    if ref["weights"].keys() != cand["weights"].keys():
        problems.append("final weight key sets differ")
    rows += [("final/" + k, *diff(ref["weights"][k], cand["weights"][k]))
             for k in ref["weights"].keys() & cand["weights"].keys()]
    problems += [f"{r[0]}: {r[4]}" for r in rows if r[4]]
    worst = max(rows, key=lambda r: r[2]) if rows else ("none", float("inf"), float("inf"), False, "no rows")
    dev_same = ref["preds"] == cand["preds"] and ref["dev"]["accuracy"] == cand["dev"]["accuracy"]
    dev_keys = {k: (ref["dev"][k], cand["dev"].get(k)) for k in ref["dev"]
                if isinstance(ref["dev"][k], float) and ref["dev"][k] != cand["dev"].get(k)}
    return {"pass": not problems and worst[2] <= rtol and dev_same,
            "bitwise": not problems and all(r[3] for r in rows) and not dev_keys,
            "problems": problems[:20], "n_problems": len(problems),
            "max_rel": worst[2], "worst": worst[0], "max_abs": max((r[1] for r in rows), default=float("inf")),
            "n_compared": len(rows), "dev_predictions_identical": dev_same,
            "dev_float_fields_differing": dev_keys,
            "ref_train_s": ref["train_s"], "cand_train_s": cand["train_s"]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--ref-tree", type=Path, required=True)
    ap.add_argument("--suite", choices=sorted(SUITES), default="tiny-cpu")
    ap.add_argument("--rtol", type=float, default=1e-5)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    _, ref_sha, ref_root = load_ref(args.ref_tree)
    install_capture()
    report = {"suite": args.suite, "rtol": args.rtol, "ref_memsub_sha256": ref_sha,
              "cand_memsub_sha256": source_tree_sha256(ROOT / "memsub"), "cases": []}
    first_ref = None
    for kw in SUITES[args.suite]:
        case = {"config": {k: v for k, v in kw.items()}}
        try:
            ref = run("memsub_ref", kw)
            first_ref = first_ref or (kw, ref)
            case.update(compare(ref, run("memsub", kw), args.rtol))
        except Exception as e:                       # recorded; the suite fails
            case.update({"pass": False, "problem": f"{type(e).__name__}: {str(e)[:300]}"})
        report["cases"].append(case)
        print(json.dumps({k: case.get(k) for k in ("pass", "bitwise", "max_rel", "worst", "ref_train_s",
                                                   "cand_train_s", "problem", "n_problems")} | {"arm": kw["arm"]}),
              flush=True)
        (args.out / "parity.json").write_text(json.dumps(report, indent=2, default=str))
        if kw["device"] == "cuda":
            gc.collect()
            torch.cuda.empty_cache()
    try:                                            # self-test: a perturbed candidate must FAIL parity
        with perturbed_candidate():
            st = compare(first_ref[1], run("memsub", first_ref[0]), args.rtol)
        report["self_test"] = {k: st.get(k) for k in ("pass", "max_rel", "worst", "problem", "n_problems")}
        report["self_test_perturbation_detected"] = st.get("pass") is False
    except Exception as e:
        report["self_test"], report["self_test_perturbation_detected"] = f"{type(e).__name__}: {e}"[:300], False
    report["isolation"] = isolation_evidence(ref_root)
    report["pass"] = (all(c["pass"] for c in report["cases"]) and report["self_test_perturbation_detected"]
                      and report["isolation"]["ok"])
    (args.out / "parity.json").write_text(json.dumps(report, indent=2, default=str))
    print("PASS" if report["pass"] else "FAIL", flush=True)
    sys.exit(0 if report["pass"] else 1)


if __name__ == "__main__":
    main()

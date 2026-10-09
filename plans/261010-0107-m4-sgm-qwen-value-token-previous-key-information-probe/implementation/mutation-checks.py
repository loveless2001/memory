"""Apply one mutant at a time to a probe source file, run the C0 + fake-capture tests, restore.
A mutant is CAUGHT iff the test run fails. Restores the original bytes in finally."""
import json, os, subprocess, sys, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[4] if False else Path.cwd()
MATH = "scripts/sgm-p2p5-previous-key-probe-ridge-retrieval-readings.py"
RUN = "scripts/sgm-p2p5-previous-key-probe-run-s1-s2-full.py"
MUTANTS = [
    ("M1 ties to smaller lambda", MATH, "key=lambda lam: (means[lam], lam)", "key=lambda lam: (means[lam], -lam)"),
    ("M2 ties count for the true key", MATH, "(scores >= true[:, None]).sum(1) - 1", "(scores > true[:, None]).sum(1)"),
    ("M3 derangement null", MATH, "np.stack([rng.permutation(n_bind) for _ in range(n_episodes)])",
     "np.stack([np.roll(np.arange(n_bind), 1 + int(rng.integers(0, n_bind - 1))) for _ in range(n_episodes)])"),
    ("M4 CV fits on all rows", MATH, "model = ridge_path(x[tr], y[tr], lambdas)", "model = ridge_path(x, y, lambdas)"),
    ("M5 CARRIED before INVALID", MATH, '    if invalid:\n        label = "INVALID"\n    elif not calibrated:',
     '    if calibrated and any(p >= 0.50 and lo > 0.10 for p, lo, _ in v.values()):\n        label = "CARRIED"\n    elif invalid:\n        label = "INVALID"\n    elif not calibrated:'),
    ("M6 null family not adjusted", MATH, "NULL_ALPHA = 0.05 / (2 * N_LAYERS)", "NULL_ALPHA = 0.05 / N_LAYERS"),
    ("M7 admission factor 1", MATH, "wall = 2.0 * est", "wall = 1.0 * est"),
    ("M8 zero-norm prediction ranks best", MATH, "np.where(pn == 0, c - 1, ge)", "np.where(pn == 0, 0, ge)"),
    ("M9 V-shuf fit on true targets", RUN, 'y = y_shuf_f if s == "V-shuf" else y_true_f', "y = y_true_f"),
    ("M10 wall check bypassed", RUN, '    check_wall(args)                                            # before any model load', "    pass"),
    ("M11 full admission 'admit' ignored", RUN, '    require(adm["admit"], "S1 admission refused the full run")', "    pass"),
    ("M12 full wall != ceil(admitted) accepted", RUN,
     '    require(args.wall_s == math.ceil(adm["wall_s"]), f"--wall-s must equal ceil(admitted wall) {math.ceil(adm[\'wall_s\'])}")',
     "    pass"),
    ("M13 model-load test guard removed", "scripts/sgm-p2p5-previous-key-probe-capture-qwen-adapter-inputs.py",
     '    require(os.environ.get("PKPROBE_FORBID_MODEL") != "1", "MODEL LOAD ATTEMPTED under PKPROBE_FORBID_MODEL=1")',
     "    pass"),
]
TESTS = ["tests/test_sgm_p2p5_previous_key_probe_math_c0.py", "tests/test_sgm_p2p5_previous_key_probe_orchestration_fake_capture.py"]
res = []
for name, path, old, new in MUTANTS:
    p = Path(path); orig = p.read_bytes(); src = orig.decode()
    if src.count(old) != 1:
        res.append({"mutant": name, "status": "PATTERN_NOT_FOUND"}); continue
    try:
        p.write_text(src.replace(old, new))
        env = {**os.environ, "PKPROBE_FORBID_MODEL": "1"}          # no mutant may load Qwen (codex 22400)
        r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider",
                            "--basetemp", str(Path(tempfile.mkdtemp(prefix="pkprobe-mut-"))), *TESTS],
                           capture_output=True, text=True, timeout=600, env=env)
        model_attempt = "MODEL LOAD ATTEMPTED" in (r.stdout + r.stderr)
        res.append({"mutant": name, "status": "CAUGHT" if r.returncode != 0 else "SURVIVED",
                    "model_load_attempt_blocked": model_attempt, "tail": r.stdout.strip().splitlines()[-1:]})
    finally:
        p.write_bytes(orig)
print(json.dumps(res, indent=1))
json.dump(res, open(Path(__file__).with_name("mutation-checks.json"), "w"), indent=1)
sys.exit(0 if all(x["status"] == "CAUGHT" for x in res) else 1)

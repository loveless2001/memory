"""Independent local review of frozen a17cd40; only reviewer-owned files are written."""
import datetime
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path.cwd()
sys.path.insert(0, str(ROOT))
OUT = Path(__file__).resolve().parent
PLAN = Path("plans/261006-1345-m4-sgm-p2p5-qwen3-0p6b-screen")
GROUP = ROOT / PLAN / "p2p5-qwen3-0p6b-screen-v1"
PKG = ROOT / PLAN / "pk-campaign-posthoc-amendment"
BASE = json.loads((OUT / "baseline.json").read_text())
TERMINAL = json.loads((OUT.parent / "codex-261007-p2p5-pk-21704-terminal-training-audit/terminal-verification.json").read_text())


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def load(rel, name):
    s = importlib.util.spec_from_file_location(name, ROOT / rel)
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m


rd = load("scripts/sgm-p2p5-pk-campaign-readings.py", "codex_rd")
runner = load("modal-runners/modal-m4-sgm-p2p5-pk-campaign-readings-runner.py", "codex_runner")
spec = rd.AMD.load_spec()
checks = {}


def check(name, ok, detail=None):
    checks[name] = {"ok": bool(ok), "detail": detail}
    assert ok, (name, detail)


index = PKG / "SHA256SUMS-posthoc-amendment-package.txt"
entries = [line.split(None, 1) for line in index.read_text().splitlines() if line.strip()]
bad = [rel for want, rel in entries if sha(ROOT / rel) != want]
check("package_index", len(entries) == 17 and not bad,
      {"sha256": sha(index), "files": len(entries), "mismatches": bad})

manifest = json.loads(rd.MANIFEST.read_text())
check("fresh_manifest_exact", rd.MAN.freeze() == manifest)
check("analysis_and_launch_manifest", rd.MAN.manifest_problem(ROOT, manifest, rd.current_identity()["memsub"],
      sections=("analysis", "launch"), closure=rd.analysis_closure()) is None)
old = json.loads(subprocess.check_output(["git", "show", "537ace8:configs/m4_sgm_p2p5_campaign_analysis_manifest.json"], text=True))
delta = {section: sorted(k for k in set(old[section]) | set(manifest[section])
                        if old[section].get(k) != manifest[section].get(k)) for section in ("analysis", "launch")}
check("exact_manifest_delta", delta == {
    "analysis": ["configs/m4_sgm_p2p5_pk_posthoc_validation_amendment.json",
                 "scripts/sgm-p2p5-pk-campaign-analysis-dependency-manifest.py",
                 "scripts/sgm-p2p5-pk-campaign-readings.py",
                 "scripts/sgm-p2p5-pk-posthoc-validation-amendment.py"],
    "launch": ["modal-runners/modal-m4-sgm-p2p5-pk-campaign-readings-runner.py",
               str(PLAN / "pk-campaign-posthoc-amendment/learned-n32-s1-revalidation-record.json"),
               str(PLAN / "prereg-amendment-posthoc-validation-learned-n32-s1.md")]}, delta)
protected = {rel: sha(ROOT / rel) == want for rel, want in BASE["protected_sha256"].items()
             if rel != str(rd.MANIFEST.relative_to(ROOT))}
check("protected_scientific_inputs", all(protected.values()), protected)
check("numerical_source_unchanged", rd.current_identity()["memsub"] == BASE["original_memsub_sha256"],
      rd.current_identity())

ev = BASE["exception_evidence"]
expected_nulls = sorted([r["step"], k] for r in ev["null_gradient_rows"] for k in r["keys"])
bindings = {"cell": spec["cell"] == BASE["exception_cell"], "slot": spec["slot"] == "learned-n32",
            "epoch": spec["epoch"] == 1,
            "attempt": spec["attempt"] == "cells/learned-n32-s1/epoch-1/attempt-1",
            "state_sha256": spec["state_sha256"] == ev["state_sha256"],
            "done_sha256": spec["done_sha256"] == ev["done_sha256"],
            "outputs": spec["outputs"] == ev["output_hashes"],
            "terminal_checkpoint": spec["terminal_checkpoint"] == ev["terminal_generation"],
            "original_reason": spec["original_reason"] == ev["reason"],
            "original_validation": spec["original_validation"] == ev["reason"].removeprefix("output validation: "),
            "nullable_leaves": sorted(spec["nullable_leaves"]) == expected_nulls,
            "label": spec["label"] == "post-hoc amended"}
check("full_spec_vs_independent_baseline", all(bindings.values()), bindings)

with tempfile.TemporaryDirectory(prefix="codex-a17cd40-bind-") as d:
    root, admitted = Path(d), {}
    for slot in runner.SLOTS:
        (root / slot).symlink_to(GROUP / slot / "volume-evidence/collect-1" / slot)
        admitted[slot] = sorted(int(k.split("-")[1]) for k in json.loads((GROUP / slot / "admission.json").read_text())
                                if k.startswith("start-"))
    grid, registry, schema = (json.loads(p.read_text()) for p in (rd.GRID, rd.REGISTRY, rd.SCHEMA))
    bound0, problem0 = rd.bind_cells(root, admitted, rd.current_identity()["memsub"], grid, registry, schema)
    bound1, problem1 = rd.bind_cells(root, admitted, rd.current_identity()["memsub"], grid, registry, schema, spec)
    check("real_original_gate", len(bound0) == 17 and problem0 == "learned-n32-s1: state FAILED",
          {"bound": len(bound0), "problem": problem0})
    check("real_amended_gate", len(bound1) == 18 and problem1 is None,
          {"bound": sorted(bound1), "problem": problem1})
    unchanged = {}
    for slot, evidence in TERMINAL["slots"].items():
        for cid, prior in evidence["cells"].items():
            cell_dir = root / slot / "cells" / cid
            state = cell_dir / f"epoch-{prior['epoch']}" / "state.json"
            tail = prior["terminal_checkpoint"]
            checkpoint = cell_dir / f"epoch-{tail['epoch']}" / tail["file"]
            unchanged[cid] = sha(state) == prior["state_sha256"] and sha(checkpoint) == tail["sha256"]
    check("all18_states_and_terminal_payloads_unchanged", len(unchanged) == 18 and all(unchanged.values()), unchanged)

check("real_runner_preconditions", runner.amendment_gate(ROOT) == (spec, None)
      and runner.slots_ready(GROUP, spec) is None and runner.slots_ready(GROUP) is not None)
record_path = OUT / "record-reproduced.json"
cmd = [sys.executable, "scripts/sgm-p2p5-pk-posthoc-validation-amendment.py", "--slot-root",
       str(GROUP / "learned-n32/volume-evidence/collect-1/learned-n32"), "--out", str(record_path)]
made = subprocess.run(cmd, text=True, capture_output=True)
original_record = PKG / "learned-n32-s1-revalidation-record.json"
check("revalidation_cli_byte_identical", made.returncode == 0 and record_path.read_bytes() == original_record.read_bytes(),
      {"rc": made.returncode, "stdout": made.stdout, "stderr": made.stderr})
first_sha = sha(record_path)
repeat = subprocess.run(cmd, text=True, capture_output=True)
check("revalidation_cli_write_once", repeat.returncode != 0 and "refusing to overwrite" in repeat.stderr
      and sha(record_path) == first_sha, {"rc": repeat.returncode, "stderr": repeat.stderr.strip()})

# Independent failure-path probes. Population functions are explicit tripwires in early/parity failure paths.
import pytest
from unittest.mock import patch
pilots = rd.expand_cells(json.loads(rd.GRID.read_text()))
labels = {}
with tempfile.TemporaryDirectory(prefix="codex-a17cd40-label-") as d:
    root = Path(d)
    def forbidden(*args, **kwargs):
        raise AssertionError("population/checkpoint access should not occur")
    with patch.object(rd, "bind_cells", side_effect=forbidden), patch.object(rd, "parity", side_effect=forbidden), \
            patch.object(rd, "reserved_rows", side_effect=forbidden):
        rep = rd.readings(root, {}, {"memsub": "wrong", "manifest": "wrong"}, root / "early")
    labels["early_identity_refusal"] = rep
    with patch.object(rd, "bind_cells", side_effect=[({c: root for c in pilots if c != spec["cell"]},
                     "learned-n32-s1: state FAILED"), ({c: root for c in pilots}, None)]), \
            patch.object(rd, "sha", wraps=rd.sha) as sh, \
            patch.object(rd, "parity", return_value="independent parity refusal"), \
            patch.object(rd, "reserved_rows", side_effect=forbidden):
        (root / "trained_parameters.safetensors").write_bytes(b"local-label-probe")
        rep = rd.readings(root, {}, rd.current_identity(), root / "parity")
    labels["parity_refusal"] = rep
    testmod = load("tests/test_sgm_pk_posthoc_validation_amendment.py", "codex_labels")
    with pytest.MonkeyPatch.context() as mp:
        # testmod owns a separately imported module; replace its end binding only, with all evaluation faked.
        sequence = iter([None, "independent end binding refusal"])
        mp.setattr(testmod.rd, "binding_problem", lambda *a, **k: next(sequence))
        p = root / "end"
        p.mkdir()
        rep, _ = testmod.run_readings(mp, p)
    labels["end_binding_refusal"] = rep
    for kind, rep in labels.items():
        check("labels_" + kind, rep["campaign_label"] == "post-hoc amended"
              and all(v["label"] == "post-hoc amended" and v["reading"].startswith("unavailable:")
                      for v in rep["n"].values()) and len(rep["n"]) == 2)
    check("original_outcome_retained_after_end_refusal", all(v["original_reading"] ==
          "unavailable: learned-n32-s1: state FAILED" and "reading_before_end_binding_failure" in v
          for v in labels["end_binding_refusal"]["n"].values()))
(OUT / "label-probes.json").write_text(json.dumps(labels, indent=2) + "\n")

tracked = ["memsub", "scripts", "configs", "modal-runners", str(PLAN / "pk-campaign-posthoc-amendment"),
           str(PLAN / "prereg-amendment-posthoc-validation-learned-n32-s1.md")]
dirty = subprocess.check_output(["git", "status", "--porcelain", "--", *tracked], text=True)
check("submitted_tree_still_frozen", not dirty and subprocess.check_output(["git", "rev-parse", "--short", "HEAD"],
      text=True).strip() == "a17cd40", dirty)
result = {"status": "PASS", "checks": checks, "completed_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
          "remote_mutations": 0, "shared_artifact_edits": 0}
(OUT / "local-audit.json").write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps({"status": result["status"], "checks": len(checks), "completed_utc": result["completed_utc"]}))

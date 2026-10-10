"""Read/validate receipts only. Never call runner.main/body, capture or model loaders."""
import importlib.util
import json
import pathlib
import shutil

OUT = pathlib.Path(__file__).resolve().parent
ROOT = OUT.parents[2]
spec = importlib.util.spec_from_file_location("rx_audit", ROOT / "scripts/sgm-p2p5-previous-key-probe-stage-receipts-and-admission-validation.py")
RX = importlib.util.module_from_spec(spec)
spec.loader.exec_module(RX)
fixtures = OUT / "receipt-fixtures"
fixtures.mkdir()
fake = next((OUT / "pytest-isolated").glob("test_s2_path_runs_end_to_end*/o"))
shas = RX.source_shas()
checks = []

def validate(name, stage, mode):
    try:
        value = RX.validate_receipt(stage, mode)
        checks.append({"case": name, "accepted": True, "value": value})
    except Exception as exc:
        checks.append({"case": name, "accepted": False, "error": repr(exc)})

d = fixtures / "actual-fake-s2"
shutil.copytree(fake, d)
pathlib.Path(str(d) + ".exit").write_text("0\n")
res = json.loads((d / "result.json").read_text())
assert res["run"]["identities"] == {"fake": True}
assert res["run"]["fit"][1] == 8 and res["run"]["ev"][1] == 6
validate("actual fake S2 (8+6 episodes, 2 layers, fake identities)", d, "s2")

def s1_fixture(name):
    d = fixtures / name
    d.mkdir()
    pathlib.Path(str(d) + ".exit").write_text("0\n")
    (d / "status.json").write_text(json.dumps({"state": "COMPLETE", "mode": "s1"}))
    r = {"run": {"mode": "s1", "sha256": shas, "wall_s": 1800},
         "metrics": {"m": 0.5}, "timing_s": {"t": 1}, "reading": {"label": "x"}}
    return d, r

d, r = s1_fixture("contradictory-admission")
r["admission"] = {"admit": False, "wall_s": 20000, "estimate_s": 10000}
(d / "result.json").write_text(json.dumps(r))
(d / "admission.json").write_text(json.dumps({"admit": True, "wall_s": 1, "estimate_s": 10000}))
validate("external admits 1s; result rejects 20000s, no run/features records", d, "s1")

d, r = s1_fixture("nonfinite-profile")
(d / "result.json").write_text(json.dumps(r))
(d / "admission.json").write_text('{"admit":true,"wall_s":1000,"estimate_s":1e999,"components":{"fit_s":-1}}')
validate("profile estimate overflows to infinity, negative fit component", d, "s1")

d, r = s1_fixture("changed-source")
r["run"]["sha256"] = {**shas, "extra": "0"}
(d / "result.json").write_text(json.dumps(r))
(d / "admission.json").write_text(json.dumps({"admit": True, "wall_s": 1000}))
validate("source mismatch control", d, "s1")

(OUT / "receipt-counterexamples.json").write_text(json.dumps(checks, indent=2) + "\n")
print(json.dumps(checks, indent=2))

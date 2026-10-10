"""Use retained model-free fixtures with the immutable reviewed validator. No model/runner/fit calls."""
import importlib.util
import json
import pathlib
import shutil

OUT = pathlib.Path(__file__).resolve().parent
SOURCE = OUT / "sources-94d85af/scripts/sgm-p2p5-previous-key-probe-stage-receipts-and-admission-validation.py"
spec = importlib.util.spec_from_file_location("rx05_regressions", SOURCE)
RX = importlib.util.module_from_spec(spec)
spec.loader.exec_module(RX)
parent = next(p for p in (OUT / "pytest-isolated").glob("test_full_mode_valid_receipts_*") if not p.is_symlink())
checks = []

def check(name, fn, accept):
    try:
        value = fn()
        row = {"case": name, "accepted": True, "value": value}
    except Exception as exc:
        row = {"case": name, "accepted": False, "error": repr(exc)}
    assert row["accepted"] == accept, row
    checks.append(row)

check("unmodified frozen-schema fixtures", lambda: RX.full_wall(parent / "s1", parent / "s2"), True)
fixtures = OUT / "regression-fixtures"
fixtures.mkdir()

def copy_stage(name, original):
    d = fixtures / name
    shutil.copytree(original, d)
    pathlib.Path(str(d) + ".exit").write_text("0\n")
    return d

d = copy_stage("admission-mismatch", parent / "s1")
adm = json.loads((d / "admission.json").read_text())
adm["wall_s"] = 1.0
(d / "admission.json").write_text(json.dumps(adm))
check("external/embedded admission mismatch", lambda: RX.validate_receipt(d, "s1"), False)

d = copy_stage("overflow-admission", parent / "s1")
for name in ("admission.json", "result.json"):
    text = (d / name).read_text()
    assert text.count('"fit_s": 100.0') == 1
    (d / name).write_text(text.replace('"fit_s": 100.0', '"fit_s": 1e999'))
check("overflowing profile component in matching admissions", lambda: RX.validate_receipt(d, "s1"), False)

d = copy_stage("negative-admission", parent / "s1")
adm = json.loads((d / "admission.json").read_text())
adm["components"]["fit_s"] = -1.0
adm["estimate_s"] -= 101.0
adm["wall_s"] = 2 * adm["estimate_s"]
(d / "admission.json").write_text(json.dumps(adm))
res = json.loads((d / "result.json").read_text())
res["admission"] = adm
(d / "result.json").write_text(json.dumps(res))
check("negative profile part despite recomputed estimate", lambda: RX.validate_receipt(d, "s1"), False)

d = copy_stage("source-mismatch", parent / "s2")
run = json.loads((d / "run.json").read_text())
run["sha256"]["memsub_tree"] = "0" * 64
(d / "run.json").write_text(json.dumps(run))
res = json.loads((d / "result.json").read_text())
res["run"] = run
(d / "result.json").write_text(json.dumps(res))
check("consumed source mismatch", lambda: RX.validate_receipt(d, "s2"), False)

fake = next((OUT / "pytest-isolated").glob("test_s2_path_runs_end_to_end*/o"))
d = copy_stage("fake-s2-with-run-record-repaired", fake)
res = json.loads((d / "result.json").read_text())
(d / "run.json").write_text(json.dumps(res["run"]))
check("fake S2 refused after eliminating producer mismatch", lambda: RX.validate_receipt(d, "s2"), False)
assert "episode counts/splits/seeds differ" in checks[-1]["error"]

(OUT / "receipt-regressions.json").write_text(json.dumps(checks, indent=2) + "\n")
print(json.dumps(checks, indent=1))

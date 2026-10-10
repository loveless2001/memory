"""Verify r2 source/evidence bindings locally; no model load, GPU, Modal RPC or build."""
import hashlib
import importlib.util
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
PLAN = ROOT / "plans/261008-0144-m4-sgm-p2p5-readout-recipe-rescue-probe"
PKG = PLAN / "implementation-r2"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def hashes(path):
    return {rel: h for h, rel in (line.split(maxsplit=1) for line in path.read_text().splitlines())}


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


bound = hashes(PKG / "SHA256SUMS-implementation-package-r2.txt")
assert len(bound) == 26 and all(sha(ROOT / rel) == h for rel, h in bound.items())
old = hashes(PLAN / "implementation/SHA256SUMS-implementation-package.txt")
old_source = {rel: h for rel, h in old.items() if "/implementation/" not in rel}
changed = {rel for rel, h in old_source.items() if sha(ROOT / rel) != h}
expected_changed = {
    "modal-runners/modal-m4-sgm-p2p5-readout-probe-slot-runner.py",
    "scripts/sgm-p2p5-readout-probe-local-gpu-smoke.py",
    "tests/test_sgm_p2p5_readout_probe_runner_reaper_reading.py",
}
new_test = "tests/test_sgm_p2p5_readout_probe_build_stage_and_smoke_bound.py"
assert len(old_source) == 14 and changed == expected_changed
source_paths = ("memsub", "scripts", "configs", "modal-runners", "tests")
assert set(git("diff", "--name-only", "c3c6fa2", "51b333d", "--", *source_paths).decode().splitlines()) == changed | {new_test}
assert not git("diff", "c3c6fa2", "51b333d", "--", "memsub", "configs",
               "plans/261006-1345-m4-sgm-p2p5-qwen3-0p6b-screen")
assert (PKG / "fix-diff-c3c6fa2-to-51b333d.patch").read_bytes() == git("diff", "c3c6fa2", "51b333d", "--", *source_paths)
assert not git("diff", "51b333d", "30e2b3e", "--", "memsub", "scripts", "configs", "modal-runners", "tests")

run1 = json.loads((PKG / "mutation-checks-readout-probe-r2-run1-at-8b476fd-one-survivor.json").read_text())
run2 = json.loads((PKG / "mutation-checks-readout-probe-r2.json").read_text())
entries1 = {k: v for k, v in run1.items() if isinstance(v, dict) and "aimed_test" in v}
entries2 = {k: v for k, v in run2.items() if isinstance(v, dict) and "aimed_test" in v}
assert len(entries1) == len(entries2) == 38
assert run1["all_ok"] is False and run2["all_ok"] is True
assert [k for k, v in entries1.items() if not v["ok"]] == ["smoke ignores the timeout's argv tail"]
assert run2["baseline"]["rc"] == 0 and "73 passed" in run2["baseline"]["summary"]
assert all(v["ok"] is True and v["rc"] != 0 and v["aimed_test"] in v["failed"] for v in entries2.values())
assert (PKG / "mutation-checks-readout-probe-r2.exit.txt").read_text().strip() == "EXIT_STATUS=0"
assert (PKG / "mutation-checks-readout-probe-r2-run1-at-8b476fd-one-survivor.exit.txt").read_text().strip() == "EXIT_STATUS=1"
assert "565 passed, 2 skipped" in (PKG / "sgm-suite.txt").read_text()
assert (PKG / "sgm-suite.exit.txt").read_text().strip() == "EXIT_STATUS=0"
r1_driver = load(PLAN / "implementation/mutation-checks-readout-probe.py", "r1_mutation_driver")
r2_driver = load(PKG / "mutation-checks-readout-probe-r2.py", "r2_mutation_driver")
assert {k: r2_driver.MUTATIONS[k] for k in r1_driver.MUTATIONS} == r1_driver.MUTATIONS
assert len(r2_driver.MUTATIONS) == 38
assert all(v["refreeze"].startswith("rc=0 ") for v in entries2.values() if v["refreeze"] is not None)

ledger = json.loads((PLAN / "probe-priced-ledger.json").read_text())
result = {
    "package_commit": git("rev-parse", "HEAD").decode().strip(),
    "hashes": {rel: {"expected": h, "actual": sha(ROOT / rel)} for rel, h in bound.items()},
    "package_hashes_verified": 26,
    "changed_r1_source_files": sorted(changed),
    "unchanged_r1_source_files": sorted(set(old_source) - changed),
    "new_test": new_test,
    "source_diff_matches_retained_patch": True,
    "code_to_package_source_diff_empty": True,
    "protected_memsub_configs_campaign_unchanged": True,
    "saved_suite": (PKG / "sgm-suite.txt").read_text().strip().splitlines()[-1],
    "saved_mutations": {"baseline": run2["baseline"], "aimed_caught": 38,
                        "r1_mutations_unchanged": 26,
                        "preserved_first_run_survivor": "smoke ignores the timeout's argv tail",
                        "independently_repeated": False},
    "ledger": {"sha256": sha(PLAN / "probe-priced-ledger.json"), "deadline_s": ledger["deadline_s"],
               "cap_usd": ledger["cap_request_usd"]},
    "rpc_build_model_or_gpu_called": False,
}
(OUT / "package-evidence.json").write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps({k: v for k, v in result.items() if k != "hashes"}, indent=2))

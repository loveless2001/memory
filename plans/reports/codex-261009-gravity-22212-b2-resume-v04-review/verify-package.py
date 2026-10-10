"""Verify immutable package files and the retained real checkpoint without training or restore."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
from dataclasses import asdict
from decimal import Decimal

REPORT = Path(__file__).resolve().parent
ROOT = REPORT / "candidate"
REPO = Path("/home/lenovo/projects/memory")
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))
PLAN = Path("plans/261009-1135-m4-sgm-p2p5-b2-occupied-fill-long-run")


def load(rel, name):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


R = load("modal-runners/modal-m4-sgm-p2p5-b2-occupied-fill-resume-runner.py", "audited_resume_package")
B = load(R.SCRIPT, "audited_b2_identity")
files = []
for line in (PLAN / "SHA256SUMS-b2-resume-package-v0.4.txt").read_text().splitlines():
    if line.startswith("memsub_source_sha256"):
        assert R.local_memsub_sha256() == line.split()[1] == R.EXPECT_MEMSUB_SHA256
        continue
    expected, rel = line.split("  ", 1)
    actual = hashlib.sha256(Path(rel).read_bytes()).hexdigest()
    assert actual == expected, rel
    files.append({"file": rel, "sha256": actual})
unchanged = []
for rel in (R.SCRIPT, R.STAGE_A_SCRIPT, R.INPUT_MANIFEST):
    old = subprocess.check_output(["git", "show", "24b1432:" + rel], cwd=REPO)
    assert old == Path(rel).read_bytes(), rel
    unchanged.append(rel)
subprocess.run(["bash", "-n", str(PLAN / "launch-b2-resume-once.sh")], check=True)
checkpoint = REPO / "plans/reports/codex-261009-gravity-wait38-b2-manual-stop-audit/volume-evidence-verified/b2-run-v1/B2/resume.pt"
assert hashlib.sha256(checkpoint.read_bytes()).hexdigest() == R.RESUME_CKPT_SHA256
state = B.load(checkpoint)
probe = Path(R.INPUT_MANIFEST)
config = B.arm_config(json.loads(probe.read_text())["pilot_config"], "cuda")
assert state["step"] == R.RESUME_CKPT_STEP == 750
assert state["pilot_config"] == asdict(config)
assert state["b2_identity"] == B.run_identity(config, hashlib.sha256(probe.read_bytes()).hexdigest())
assert state["b2_identity"] == json.loads((PLAN / "b2-run-v1-start1-volume-snapshot/B2_identity.json").read_text())
rate = Decimal("0.000542") + Decimal("1.25") * Decimal("4") * Decimal("0.0000131") + Decimal("32") * Decimal("0.00000222")
reservation = Decimal(R.RESUME_S + R.STARTUP_S) * rate
total = Decimal("6.07089738") + reservation
assert total < Decimal("17")
rec = {"commit": "e03ca5a6837db104f79677a492a7d8e889335cdd", "package_files": files,
       "memsub_source_sha256": R.local_memsub_sha256(), "unchanged_vs_24b1432": unchanged,
       "shell_syntax_ok": True, "checkpoint": str(checkpoint), "checkpoint_step": state["step"],
       "checkpoint_sha256": R.RESUME_CKPT_SHA256, "checkpoint_identity_and_config_match": True,
       "ledger": R.ledger(), "decimal_rate_usd_s": str(rate), "decimal_resume_reserve_usd": str(reservation),
       "decimal_campaign_compute_reserve_usd": str(total), "decimal_headroom_usd": str(Decimal("17") - total)}
(REPORT / "package-verification.json").write_text(json.dumps(rec, indent=2))
print(json.dumps({"package_files_verified": len(files), "memsub_matches": True, "unchanged_training": True,
                  "checkpoint_step": state["step"], "identity_matches": True, "reserve_usd": str(total),
                  "headroom_usd": str(Decimal("17") - total)}))

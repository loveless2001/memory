"""Independent CPU clearance checks; no deployment/build/remote mutation.

All proof APIs are explicit substitutes. Real SDK dependency graphs are read
without hydration. Runtime self-stop credentials remain for the paid CPU proof.
"""
from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import io
import json
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from modal._utils.async_utils import synchronizer

ROOT = Path(__file__).resolve().parents[2]
HASHES = {
    "modal-m4-sgm-p2p5-l40s-timing-profile.py": "e26013e6e34545552eb7d6d4fc8e07af2e1fc8c927f5e38818714a3de4069349",
    "modal-m4-sgm-p2p5-reaper-lifetime-stop-logic.py": "32bb3a3a38bf375e4c9107e4b3d7dc4c6392076cb5ba55f7c599fab644329e6c",
    "modal-m4-sgm-p2p5-reaper-self-stop-proof.py": "00509c185b26762eadea126e27b2dc55b71de5cf1e592d6bceda20276de1479b",
}


def load(path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[path.stem] = m
    spec.loader.exec_module(m)
    return m


class Store(dict):
    failure_key = None

    def put(self, key, value, skip_if_exists=False):
        if key == self.failure_key:
            raise RuntimeError("fixture binding RPC failure")
        if key in self and skip_if_exists:
            return False
        self[key] = value
        return True


def fixture(m, label):
    now, stops, lookups = [1000.0], [], []
    store = Store(first_tick=1000.0)
    if label == "binding_exception":
        store.failure_key = "deadline_epoch"

    def deploy():
        if label == "deploy_timeout":
            raise subprocess.TimeoutExpired("fixture deploy", 600, output="retained stdout", stderr="retained stderr")
        return SimpleNamespace(stdout="fixture deployment", stderr="", returncode=0)

    def lookup():
        lookups.append(True)
        if label == "lookup_recovery" and len(lookups) == 1:
            return None
        return "ap-owned-fixture"

    def lifecycle(app_id):
        if label == "observer_exception":
            raise RuntimeError("fixture lifecycle RPC failure")
        at = 1010.0 if label == "premature_stop" else 1140.0
        return SimpleNamespace(stopped_at=datetime.fromtimestamp(at, timezone.utc) if now[0] >= at else None,
                               stopped_by="fixture actor")

    def stop(app_id):
        stops.append(app_id)
        if label == "fallback_stop_failure":
            raise RuntimeError("fixture stop failed")

    marker = f"M4SGM_REAPER_STOP app={m.APP_NAME} bound=ap-owned-fixture reason=deadline passed t=1140"
    log = "fixture missing marker" if label in ("missing_marker", "fallback_stop_failure") else marker
    with tempfile.TemporaryDirectory(prefix=f"codex-9e7b897-{label}-") as tmp:
        old = m.LOCAL_OUT
        root = Path(tmp) / "proof"
        m.LOCAL_OUT = str(root)
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                report = m.prove(deploy=deploy, lookup=lookup, guard=store, lifecycle=lifecycle,
                                 verify=lambda a: {"verified": True, "app_state": "stopped", "app_containers": 0},
                                 stop=stop, logs=lambda a: log, clock=lambda: now[0],
                                 sleep=lambda n: now.__setitem__(0, now[0] + n))
            retained = json.loads((root / "proof_report.json").read_text())
            prov = json.loads((root / "proof_provenance.json").read_text())
            assert retained == report
            if label == "valid_stop":
                assert report["result"] == "PASS" and not stops and "fallback" not in report
                assert (root / "app-logs.txt").read_text() == marker
            else:
                assert report["result"] == "FAILED" and stops == ["ap-owned-fixture"]
                if label == "premature_stop":
                    assert "outside the intended window" in report["judgement"]
                elif label == "missing_marker":
                    assert "no server-side log evidence" in report["judgement"]
                elif label == "fallback_stop_failure":
                    assert "stop_error" in report["fallback"]
                elif label == "deploy_timeout":
                    log_text = (root / "deploy.log").read_text()
                    assert all(s in log_text for s in ("retained stdout", "retained stderr", "EXIT_STATUS=deploy_timeout"))
                elif label == "binding_exception":
                    assert prov["app_id"] == "ap-owned-fixture" and prov["deadline_epoch"] == 1120
                    assert "deadline_epoch" not in store and report["errors"]
                elif label == "observer_exception":
                    assert report["errors"]
                elif label == "lookup_recovery":
                    assert len(lookups) == 2 and report["fallback"]["app_id"] == "ap-owned-fixture"
            return {"result": report["result"], "report_retained": True, "local_stop_calls": stops,
                    "provenance_app_id": prov.get("app_id"), "provenance_deadline": prov.get("deadline_epoch"),
                    "errors": report["errors"], "judgement": report.get("judgement"),
                    "fallback": report.get("fallback")}
        finally:
            m.LOCAL_OUT = old


def main():
    for name, expected in HASHES.items():
        assert hashlib.sha256((ROOT / "modal-runners" / name).read_bytes()).hexdigest() == expected
    profile = load(ROOT / "modal-runners/modal-m4-sgm-p2p5-l40s-timing-profile.py")
    proof = load(ROOT / "modal-runners/modal-m4-sgm-p2p5-reaper-self-stop-proof.py")
    previous = load(ROOT / "plans/reports/codex-261006-p2p5-8f4a27f-proof-checks.py")
    prod_fn, proof_fn = (synchronizer._translate_in(f) for f in (profile.reaper, proof.reaper))
    expected_path = f"/root/{profile.LOGIC_FILE}"
    production_files = previous.image_files(prod_fn._spec.image)
    proof_files = previous.image_files(proof_fn._spec.image)
    assert expected_path in production_files and expected_path in proof_files
    assert prod_fn._spec.gpus is None and proof_fn._spec.gpus is None
    assert not prod_fn._spec.volumes and not proof_fn._spec.volumes
    assert profile.child_timeout_s(1000, 219) == 691
    assert proof.PROOF_ABANDON_S + 2 * proof.PERIOD_S < proof.charge_bound()["max_app_life_s"]
    cases = {label: fixture(proof, label) for label in
             ("valid_stop", "deploy_timeout", "binding_exception", "observer_exception",
              "premature_stop", "missing_marker", "lookup_recovery", "fallback_stop_failure")}
    total = profile.charge_bound()["reserved_total_usd"] + proof.charge_bound()["reserved_usd"]
    assert total <= 3.0
    for name, expected in HASHES.items():
        assert hashlib.sha256((ROOT / "modal-runners" / name).read_bytes()).hexdigest() == expected
    print(json.dumps({"timestamp_utc": datetime.now(timezone.utc).isoformat(),
                     "reviewed_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
                     "hashes": HASHES, "production_logic_mounts": production_files,
                     "proof_logic_mounts": proof_files, "both_reapers_cpu_only_without_volumes": True,
                     "fixtures": cases, "profile_reservation": profile.charge_bound(),
                     "proof_reservation": proof.charge_bound(), "combined_reservation_usd": total,
                     "probe_remote_calls": False, "paid_work": False,
                     "clearance": "one frozen CPU prove attempt only, inside existing $3 scope; GPU remains held"}, indent=2))


if __name__ == "__main__":
    import os
    os.chdir(ROOT)
    main()

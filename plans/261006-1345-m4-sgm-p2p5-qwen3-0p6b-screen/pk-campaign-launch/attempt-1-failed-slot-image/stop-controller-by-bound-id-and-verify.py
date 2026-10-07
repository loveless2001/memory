"""Stop the armed-but-unused campaign controller by its BOUND id (strict, never by name only), then verify."""
import importlib.util
import json
import sys
import time
from pathlib import Path

ROOT = Path("/home/lenovo/projects/memory")
NAME, BOUND = "memsub-m4-sgm-p2p5-pk-campaign-control", sys.argv[1]


def load(rel, name):
    s = importlib.util.spec_from_file_location(name, ROOT / rel)
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m


cp = load("modal-runners/modal-m4-sgm-p2p5-pk-control-plane-reaper-logic.py", "cp")
shared = load("modal-runners/modal-m4-sgm-p2p5-reaper-lifetime-stop-logic.py", "shared")
import modal  # noqa: E402

guard = dict(modal.Dict.from_name("m4-sgm-p2p5-pk-campaign-control-guard").items())
registry = dict(modal.Dict.from_name("m4-sgm-p2p5-pk-campaign-control-registry", create_if_missing=True).items())
out = {"guard": guard, "registry": registry}
if guard.get("app_id") != BOUND:
    raise SystemExit(f"bound id mismatch: guard {guard.get('app_id')} vs {BOUND}")
try:
    cp.strict_stop(shared.stop_bound_app, NAME, BOUND)
except Exception as e:
    out["stop_error"] = repr(e)[:300]
for _ in range(6):
    v = cp.verify_stopped(BOUND, cp.modal_cli_json)
    if v.get("verified") is True:
        break
    time.sleep(10)
out["verification"] = v
print(json.dumps(out, indent=2, default=str))

"""M4-SGM P2.5 Amendment PK — campaign CONTROL-PLANE reaper app: ONE Period schedule for every campaign app
(codex 21596: per-app absolute deadlines and stop-id isolation without ten schedule slots).

    .venv/bin/python -m modal deploy modal-runners/modal-m4-sgm-p2p5-pk-campaign-control-plane-reaper.py
    .venv/bin/python modal-runners/modal-m4-sgm-p2p5-pk-campaign-control-plane-reaper.py arm   # write-once guard

Each tick (CPU, 120 s): every registered app (slot apps register their bound id + absolute deadline at spawn,
write-once) past ITS OWN deadline is stopped-first by its bound id (shared, id-checked stop); apps not due are
never touched. The control app stops itself once its own deadline (armed write-once: latest planned app deadline
+ slack) has passed; if it was deployed but never armed, it stops itself ABANDON_S after its first tick.
"""

import importlib.util
import json
import os
import sys
import time
from pathlib import Path

import modal

APP_NAME = "memsub-m4-sgm-p2p5-pk-campaign-control"
REGISTRY_DICT = "m4-sgm-p2p5-pk-campaign-control-registry"
CONTROL_GUARD = "m4-sgm-p2p5-pk-campaign-control-guard"
PRICE_FILE = "plans/261006-1345-m4-sgm-p2p5-qwen3-0p6b-screen/pk6/priced-estimate-v4.json"
PERIOD_S, ABANDON_S, SLACK_S, ENVIRONMENT = 120, 1800, 1800, "main"
LOGIC, SHARED = "modal-m4-sgm-p2p5-pk-control-plane-reaper-logic.py", "modal-m4-sgm-p2p5-reaper-lifetime-stop-logic.py"

app = modal.App(APP_NAME)
image = (modal.Image.debian_slim(python_version="3.12")
         .add_local_file(f"modal-runners/{LOGIC}", f"/root/{LOGIC}")
         .add_local_file(f"modal-runners/{SHARED}", f"/root/{SHARED}"))


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name.replace("-", "_")[:-3], Path(__file__).with_name(name))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def control_view(guard, now: float) -> dict:
    """The control app's own deadline: armed (write-once) or, if never armed, first tick + ABANDON_S."""
    deadline = guard.get("deadline_epoch", None)
    if not isinstance(deadline, (int, float)):
        guard.put("first_tick", now, skip_if_exists=True)
        deadline = guard.get("first_tick", now) + ABANDON_S
    return {"app_name": APP_NAME, "app_id": guard.get("app_id", None), "deadline_epoch": deadline}


@app.function(image=image, schedule=modal.Period(seconds=PERIOD_S), cpu=0.125, memory=256, timeout=110,
              max_containers=1, retries=0)
def control() -> dict:
    cp, shared = _load(LOGIC), _load(SHARED)
    registry = dict(modal.Dict.from_name(REGISTRY_DICT, create_if_missing=True).items())
    guard = modal.Dict.from_name(CONTROL_GUARD, create_if_missing=True)
    stop = lambda name, app_id: shared.stop_bound_app(name, app_id, ENVIRONMENT)       # noqa: E731
    return cp.control_tick(registry, time.time(), stop, control_view(guard, time.time()), stop)


def arm() -> None:
    """Write-once control deadline = now + the longest planned app life (slots or readings) + slack."""
    price = json.loads(Path(PRICE_FILE).read_text())
    longest = max([v["reserve_life_s"] for v in price["slots"].values()] + [price["readings"]["reserve_life_s"]])
    guard = modal.Dict.from_name(CONTROL_GUARD, create_if_missing=True)
    app_id = modal.App.lookup(APP_NAME).app_id
    if not (guard.put("app_id", app_id, skip_if_exists=True)
            and guard.put("deadline_epoch", time.time() + longest + SLACK_S, skip_if_exists=True)):
        raise SystemExit("control guard already armed")
    print(json.dumps({"app_id": app_id, "deadline_epoch": guard.get("deadline_epoch")}))


if __name__ == "__main__":
    os.chdir(Path(__file__).resolve().parents[1])
    sys.path.insert(0, ".")
    {"arm": arm}[sys.argv[1]]()

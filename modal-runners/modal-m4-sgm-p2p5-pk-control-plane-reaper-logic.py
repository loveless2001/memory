"""Amendment PK campaign CONTROL-PLANE reaper logic (codex 21596 one schedule; hardened per 21600 / 21602).

Pure decisions + owned-subprocess execution, loaded by path both locally (tests) and in the control app.
Registry: one WRITE-ONCE entry per campaign app {app_name: {"app_id": str, "deadline_epoch": float}}.
  * Only VALID entries (non-empty bound id, finite positive deadline, deadline <= the controller's horizon)
    are acted on; anything else is QUARANTINED (never stopped by name alone) and stays unresolved, so the
    controller does not self-stop while an app it cannot vouch for may still run (until its fallback).
  * Every valid entry past ITS OWN deadline gets one OWNED child process (stop-first by bound id + verify),
    all launched in parallel; at `request_timeout_s` every survivor is killed AND reaped (no leaked workers
    across ticks, codex 21602 #1). Apps not yet due are never touched.
  * control_tick never self-stops: it returns (outcomes, self_stop_due). The caller persists the outcomes
    FIRST (bounded) and only then issues a bounded self-stop (codex 21602 #2).
  * The controller is due to self-stop after its own deadline with no unresolved target, or `fallback_s`
    after it regardless (finite fallback; unresolved evidence kept).
"""

from __future__ import annotations

import math
import time


def finite_pos(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x) and x > 0


def valid_entry(entry, horizon: float | None = None) -> bool:
    return (isinstance(entry, dict) and isinstance(entry.get("app_id"), str) and bool(entry["app_id"])
            and finite_pos(entry.get("deadline_epoch"))
            and (horizon is None or entry["deadline_epoch"] <= horizon))


def due(entry, now: float) -> bool:
    return valid_entry(entry) and now > entry["deadline_epoch"]


def run_owned(procs: dict, timeout_s: float, poll_s: float = 0.05) -> dict:
    """{name: Popen} -> {name: outcome}; survivors past the deadline are killed and reaped."""
    deadline, out = time.monotonic() + timeout_s, {}
    try:
        while len(out) < len(procs) and time.monotonic() < deadline:
            for n, p in procs.items():
                if n not in out and p.poll() is not None:
                    out[n] = "stopped_verified" if p.returncode == 0 else f"unverified (child rc {p.returncode})"
                    kill_group(p)                             # leader done: its group's descendants too (21606 #1)
            time.sleep(poll_s)
    finally:
        for n, p in procs.items():                            # timeout OR exception: clean every owned group
            if n not in out:
                kill_group(p)
                out[n] = "stop/verify timeout (child killed and reaped)"
    return out


def kill_group(p) -> None:
    """Children are started with start_new_session=True: kill their WHOLE process group (codex 21604 #1:
    a nested CLI must not outlive its killed parent), then reap the leader."""
    import os
    import signal
    try:
        os.killpg(p.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError, OSError):
        p.kill()
    p.wait()


def control_tick(registry: dict, now: float, launch, control: dict | None = None,
                 request_timeout_s: float = 20.0, fallback_s: float = 1800.0) -> tuple[dict, bool]:
    """launch(name, app_id) -> Popen of an owned child that stops-first by bound id and exits 0 iff verified
    stopped. Returns (outcomes, self_stop_due); never self-stops."""
    horizon = control.get("deadline_epoch") if isinstance(control, dict) and finite_pos(control.get("deadline_epoch")) else None
    out, unresolved, procs = {}, [], {}
    for name, entry in sorted(registry.items()):
        if not valid_entry(entry, horizon):
            out[name] = "quarantined: malformed entry or deadline beyond the controller horizon (no name-only stop)"
            unresolved.append(name)
        elif due(entry, now):
            try:
                procs[name] = launch(name, entry["app_id"])
            except Exception as e:
                out[name] = f"launch error {e!r:.160}"
                unresolved.append(name)
        else:
            out[name] = "not due"
    out.update(run_owned(procs, request_timeout_s))
    unresolved += [n for n in procs if out[n] != "stopped_verified"]
    out["__unresolved__"] = sorted(unresolved)
    self_due = False
    if isinstance(control, dict) and valid_entry(control) and now > control["deadline_epoch"]:
        self_due = (not unresolved) or now > control["deadline_epoch"] + fallback_s
        out["__control__"] = ("self stop due" + (" (fallback; unresolved kept)" if unresolved else "")) if self_due \
            else "holding: unresolved targets"
    return out, self_due


def register(store, app_name: str, app_id: str, deadline_epoch: float, horizon: float | None = None) -> bool:
    """Write-once registration of a VALID entry inside the controller horizon; raises on malformed input."""
    entry = {"app_id": app_id, "deadline_epoch": deadline_epoch}
    if not valid_entry(entry, horizon):
        raise ValueError(f"refusing registration for {app_name}: {entry!r} (horizon {horizon})")
    return bool(store.put(app_name, {"app_id": app_id, "deadline_epoch": float(deadline_epoch)}, skip_if_exists=True))

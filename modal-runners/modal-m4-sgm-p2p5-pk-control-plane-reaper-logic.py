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


def binding_problem(control: dict, price_sha: str, live_id, live_state, candidate_deadline: float,
                    window_after_s: float) -> str | None:
    """None iff the control plane is completely bound and live for an app whose ONE candidate deadline is
    `candidate_deadline` (codex 21604 #3 / 21606 #3): write-once controller id + finite deadline + price sha; the
    price sha equals the caller's bound price/horizon file; the live controller id equals the bound id and the app
    is running; the candidate leaves `window_after_s` (slots: validation + readings + slack; readings: slack)
    before the controller deadline. Read-only; callers run it before consuming any launch state."""
    if not (isinstance(control.get("app_id"), str) and control["app_id"] and finite_pos(control.get("deadline_epoch"))
            and isinstance(control.get("price_sha256"), str)):
        return f"controller binding incomplete: {sorted(control)}"
    if control["price_sha256"] != price_sha:
        return "controller was armed for a different price/horizon file"
    try:
        if live_id() != control["app_id"]:
            return "live controller app id differs from the bound id"
        if str(live_state(control["app_id"])).lower() in ("stopped", "stopping", "none", ""):
            return "controller app is not running"
    except Exception as e:
        return f"controller lookup failed: {e!r:.120}"
    if not finite_pos(candidate_deadline) or candidate_deadline > control["deadline_epoch"] - window_after_s:
        return "candidate deadline beyond the controller horizon"
    return None


def provenance_problem(prov, slot: str | None = None) -> str | None:
    """None iff launch provenance binds a NONEMPTY app id, a finite positive deadline, an expected identity and (slot
    apps) this slot. Checked BEFORE any poll, stop or fetch (codex 21617 R3): no bound id -> no collector action."""
    if not isinstance(prov, dict):
        return "launch provenance is not an object"
    if not (isinstance(prov.get("deployed_app_id"), str) and prov["deployed_app_id"].strip()):
        return "launch provenance has no bound app id (a name-only stop is never allowed)"
    if not finite_pos(prov.get("deadline_epoch")):
        return "launch provenance deadline missing or non-finite"
    if not (isinstance(prov.get("expected_identity"), dict) and isinstance(prov["expected_identity"].get("memsub"), str)):
        return "launch provenance has no expected identity"
    if slot is not None and prov.get("slot") != slot:
        return f"launch provenance is for slot {prov.get('slot')!r}, not {slot!r}"
    return None


def strict_stop(stop_bound_app, name: str, app_id) -> None:
    """Collector stop: a nonempty bound id is REQUIRED (the shared helper skips its live-id check for None and
    would stop by name); the helper then refuses when the live app under `name` is not the bound one."""
    if not (isinstance(app_id, str) and app_id.strip()):
        raise ValueError("no bound app id: name-only stop refused")
    stop_bound_app(name, app_id, "main")


def shutdown_verdict(app_id: str, app_rows: list, container_rows: list) -> bool:
    """stopped_verified iff every listed row of the bound app is stopped with zero tasks (or it is unlisted) AND no
    container of it is listed (codex 21617 R4)."""
    mine = [r for r in app_rows if r.get("app_id") == app_id]
    app_ok = all(str(r.get("state", "")).lower() == "stopped" and str(r.get("tasks")) == "0" for r in mine)
    return app_ok and not any(r.get("app_id") == app_id for r in container_rows)


def verify_stopped(app_id: str, modal_json) -> dict:
    """Independent verification by the bound id; the bound app's raw rows and any query error are retained.
    `modal_json(args)` returns the parsed JSON of `modal <args> --json`; any failure leaves it unverified."""
    out = {"app_id": app_id, "verified": False}
    try:
        apps, conts = modal_json(["app", "list"]), modal_json(["container", "list"])
        if not (isinstance(apps, list) and isinstance(conts, list)):
            raise ValueError("unexpected modal JSON shape")
        out.update(app_rows=[r for r in apps if r.get("app_id") == app_id],
                   container_rows=[r for r in conts if r.get("app_id") == app_id],
                   verified=shutdown_verdict(app_id, apps, conts))
    except Exception as e:
        out["verify_error"] = repr(e)[:300]
    return out


def modal_cli_json(args: list) -> list:
    import json
    import subprocess
    import sys
    return json.loads(subprocess.run([sys.executable, "-m", "modal", *args, "--json"], check=True, capture_output=True,
                                     text=True, timeout=60).stdout)


MANIFEST_FILE = "configs/m4_sgm_p2p5_campaign_analysis_manifest.json"


def launch_manifest_problem(root) -> str | None:
    """Local spawn check: the clean tree equals the frozen dependency manifest in BOTH sections (analysis + launch)
    and memsub (codex 21617 R2). Read-only."""
    import importlib.util
    import json
    import sys
    from pathlib import Path
    root = Path(root)
    spec = importlib.util.spec_from_file_location(
        "pk_manifest", root / "scripts/sgm-p2p5-pk-campaign-analysis-dependency-manifest.py")
    man = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(man)
    sys.path.insert(0, str(root))
    from memsub.sgm.synthetic_pilot_run import source_tree_sha256
    try:
        manifest = json.loads((root / MANIFEST_FILE).read_text())
    except (OSError, ValueError) as e:
        return f"dependency manifest unreadable: {e!r:.120}"
    return man.manifest_problem(root, manifest, source_tree_sha256(root / "memsub"), sections=("analysis", "launch"))

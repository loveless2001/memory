"""Amendment PK campaign CONTROL-PLANE reaper logic (codex 21596 one schedule; hardened per codex 21600).

Pure functions on Dict-like stores, loaded by path both locally (tests) and in the control app.
Registry: one WRITE-ONCE entry per campaign app {app_name: {"app_id": str, "deadline_epoch": float}}, set at
spawn before any GPU work, never reset. Each tick:
  * only VALID entries (non-empty bound id, finite positive deadline) can be stopped; a malformed entry is
    QUARANTINED (never stopped by name alone) and stays unresolved;
  * every valid entry past ITS OWN deadline gets stop-first-by-bound-id + verification, all requests in
    parallel, each bounded by `request_timeout_s` (a hung request cannot starve the others);
  * apps not yet due are never touched;
  * the control app stops itself only after its own deadline AND with no unresolved target — or, as the finite
    fallback, `fallback_s` after its deadline regardless (unresolved evidence is returned for the record).
Every error is recorded, never raised; the next tick retries.
"""

from __future__ import annotations

import math
from concurrent.futures import ThreadPoolExecutor, wait


def finite_pos(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x) and x > 0


def valid_entry(entry) -> bool:
    return (isinstance(entry, dict) and isinstance(entry.get("app_id"), str) and bool(entry["app_id"])
            and finite_pos(entry.get("deadline_epoch")))


def due(entry, now: float) -> bool:
    """For a VALID entry only: past its own absolute deadline."""
    return valid_entry(entry) and now > entry["deadline_epoch"]


def _stop_and_verify(stopper, verifier, name: str, app_id: str) -> str:
    try:
        stopper(name, app_id)
    except Exception as e:                                   # e.g. already stopped: verification decides
        err = f"{e!r:.160}"
    else:
        err = None
    try:
        ok = verifier(name, app_id)
    except Exception as e:
        return f"unverified (verify error {e!r:.120}; stop error {err})"
    return "stopped_verified" if ok else f"unverified (stop error {err})"


def control_tick(registry: dict, now: float, stopper, verifier, control: dict | None = None, self_stopper=None,
                 request_timeout_s: float = 20.0, fallback_s: float = 1800.0) -> dict:
    out, unresolved, targets = {}, [], []
    for name, entry in sorted(registry.items()):
        if not valid_entry(entry):
            out[name] = "quarantined: malformed entry (no name-only stop)"
            unresolved.append(name)
        elif due(entry, now):
            targets.append((name, entry["app_id"]))
        else:
            out[name] = "not due"
    if targets:
        pool = ThreadPoolExecutor(max_workers=len(targets))
        futs = {pool.submit(_stop_and_verify, stopper, verifier, n, i): n for n, i in targets}
        done, _ = wait(futs, timeout=request_timeout_s)
        for f, n in futs.items():
            out[n] = f.result() if f in done else "stop/verify timeout"
        pool.shutdown(wait=False, cancel_futures=True)       # never block on a hung request
        unresolved += [n for n, _ in targets if out[n] != "stopped_verified"]
    out["__unresolved__"] = sorted(unresolved)
    if control is not None and self_stopper is not None and valid_entry(control) and now > control["deadline_epoch"]:
        if unresolved and now <= control["deadline_epoch"] + fallback_s:
            out["__control__"] = "holding: unresolved targets"
        else:
            try:
                self_stopper(control["app_name"], control["app_id"])
                out["__control__"] = "self stop issued" + (" (fallback; unresolved kept)" if unresolved else "")
            except Exception as e:
                out["__control__"] = f"self stop error {e!r:.200}"
    return out


def register(store, app_name: str, app_id: str, deadline_epoch: float) -> bool:
    """Write-once registration of a VALID entry; False if already registered. Raises on malformed input."""
    entry = {"app_id": app_id, "deadline_epoch": deadline_epoch}
    if not valid_entry(entry):
        raise ValueError(f"refusing malformed registration for {app_name}: {entry!r}")
    return bool(store.put(app_name, {"app_id": app_id, "deadline_epoch": float(deadline_epoch)}, skip_if_exists=True))

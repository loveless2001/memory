"""Amendment PK campaign CONTROL-PLANE reaper logic (codex 21596: one schedule slot for all apps).

Pure functions on Dict-like stores, loaded by path both locally (tests) and in the control app.
The registry holds one WRITE-ONCE entry per campaign app (9 slot apps + 1 readings app):
    {app_name: {"app_id": str, "deadline_epoch": float}}
set at spawn before any GPU work and never reset. Each tick stops-first, by the BOUND app id, every
app past its OWN absolute deadline (setup, pre-admission crash/refusal loops and teardown are all
inside it); apps not yet due are never touched (isolation). An entry without a valid id/deadline is
treated as due (fail closed). The control app stops itself once its own deadline has passed, after
the others. Every stop/verify error is recorded, never raised (the next tick retries).
"""

from __future__ import annotations


def due(entry, now: float) -> bool:
    deadline = entry.get("deadline_epoch") if isinstance(entry, dict) else None
    if not isinstance(deadline, (int, float)) or not isinstance(entry.get("app_id"), str):
        return True                                          # malformed / missing: fail closed
    return now > deadline


def control_tick(registry: dict, now: float, stopper, control: dict | None = None, self_stopper=None) -> dict:
    """stopper(app_name, bound_app_id) stops-first one app (id-bound); returns per-app outcomes."""
    out = {}
    for name, entry in sorted(registry.items()):
        if not due(entry, now):
            out[name] = "not due"
            continue
        try:
            stopper(name, entry.get("app_id") if isinstance(entry, dict) else None)
            out[name] = "stop issued"
        except Exception as e:                               # already stopped / transient: retried next tick
            out[name] = f"stop error {e!r:.200}"
    if control is not None and self_stopper is not None and due(control, now):
        try:
            self_stopper(control["app_name"], control.get("app_id"))
            out["__control__"] = "self stop issued"
        except Exception as e:
            out["__control__"] = f"self stop error {e!r:.200}"
    return out


def register(store, app_name: str, app_id: str, deadline_epoch: float) -> bool:
    """Write-once registration (put skip_if_exists); False if the app was already registered."""
    return bool(store.put(app_name, {"app_id": app_id, "deadline_epoch": float(deadline_epoch)},
                          skip_if_exists=True))

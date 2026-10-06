"""Shared reaper (server-side lifetime stop) logic for the P2.5 paid L40S profile runner
and its CPU-only self-stop proof (codex 21454/21456). Imported by file path by both
runners and mounted next to them in their images, so the proof exercises exactly the
production stop path. Plain functions; Modal is touched only inside `stop_bound_app`.
"""

ENVIRONMENT = "main"                                    # the only Modal environment (modal environment list)


def reap_decision(store, now: float, abandon_s: float) -> str | None:
    """'stop' reason or None. Past the spawn deadline -> stop; never spawned within
    abandon_s of the first reaper tick -> stop (abandoned deploy)."""
    store.put("first_tick", now, skip_if_exists=True)
    deadline = store.get("deadline_epoch", None)
    if isinstance(deadline, (int, float)):
        return "deadline passed" if now > deadline else None
    first = store.get("first_tick", now)
    return "abandoned deploy (never spawned)" if now > first + abandon_s else None


def reap_and_stop(store, now: float, app_name: str, stopper, canceller=None, abandon_s: float = 1800) -> dict:
    """The WHOLE-APP STOP comes first, bound to the app id recorded at spawn (or the
    looked-up app before spawn); optional call cancellation and evidence writes only
    follow it and can never delay it."""
    reason = reap_decision(store, now, abandon_s)
    if reason is None:
        return {"stop": False}
    stopper(app_name, store.get("app_id", None))            # binding action, independent of the rest
    for optional in (lambda: canceller and store.get("call_id", None) and canceller(store.get("call_id")),
                     lambda: store.put("reaper_fired", {"t": now, "reason": reason}, skip_if_exists=True)):
        try:
            optional()
        except Exception:
            pass
    return {"stop": True, "reason": reason}


def stop_bound_app(app_name: str, expected_app_id: str | None, environment: str = ENVIRONMENT) -> None:
    """Stop `app_name` in `environment`; refuse if it no longer is the app bound at spawn."""
    import modal
    from modal.experimental import stop_app
    if expected_app_id is not None:
        live = modal.App.lookup(app_name, environment_name=environment).app_id
        if live != expected_app_id:
            raise RuntimeError(f"bound app {expected_app_id} != live {live}; not stopping another app")
    stop_app(app_name, environment_name=environment)

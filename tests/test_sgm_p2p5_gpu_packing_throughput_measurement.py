"""Option-B packing test measurement and cleanup (codex 21531/21532). Primary = fixed-work
rate over the whole measured span; windowed / reciprocal rates are secondary; malformed,
disjoint or inconsistent worker records fail; started workers never outlive a test; the
parent-death signal is armed and the parent verified."""

import copy
import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/sgm-p2p5-gpu-packing-concurrent-training-throughput-test.py"
SPEC = importlib.util.spec_from_file_location("packing", SCRIPT)
pk = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pk)
N = pk.WARMUP + pk.MEASURED


def worker(rank, k, t0, step_s, phase=2):
    """Back-to-back updates from t0 (step_s: one duration or a per-update list); the barrier
    releases at the end of the final warmup update; measured start = that release."""
    steps = step_s if isinstance(step_s, list) else [step_s] * N
    ups, t = [], t0
    for u in range(N):
        t += steps[u]
        ups.append({"update": u, "seconds": steps[u], "t_end": t})
    ups[pk.WARMUP - 1]["barrier_release"] = ups[pk.WARMUP - 1]["t_end"]
    meas = steps[pk.WARMUP:]
    return {"phase": phase, "rank": rank, "k": k, "seed": pk.SEED0 + rank, "updates": ups,
            "mean_measured_s": sum(meas) / len(meas), "peak_allocated_bytes": 1,
            "measured_start": ups[pk.WARMUP - 1]["barrier_release"], "measured_end": ups[-1]["t_end"]}


def shifted(rank, k, measured_start, step_s):
    """Worker whose MEASURED span starts at `measured_start` (constant step)."""
    return worker(rank, k, measured_start - pk.WARMUP * step_s, step_s)


def test_disjoint_measured_windows_fail():                     # codex 21532: [0,6] / [20,26]
    w = [shifted(0, 2, 0.0, 1.0), shifted(1, 2, 20.0, 1.0)]
    assert pk.validate_workers(w, 2, 2) is None
    out = pk.summarize(w, 2, 2)
    assert out["status"] == "failed" and "overlap" in out["problem"]


def test_unequal_simultaneous_windows_use_fixed_work_rate():    # codex 21532: [0,.6] / [0,60]
    w = [shifted(0, 2, 0.0, 0.1), shifted(1, 2, 0.0, 10.0)]
    out = pk.summarize(w, 2, 2)
    assert out["status"] == "ok"
    assert abs(out["fixed_work_updates_per_s"] - 12 / 60) < 1e-9
    assert out["secondary"]["reciprocal_mean_sum_updates_per_s"] > 10        # the rejected aggregate


def test_early_finisher_inflates_only_secondary_estimates():
    a = worker(0, 2, 0.0, 1.0)                                   # measured [2, 8]
    b = worker(1, 2, 0.0, [1.0, 1.0, 10.0] + [2.0] * (N - 3))    # measured [2, 22]
    out = pk.summarize([a, b], 2, 2)
    assert abs(out["fixed_work_updates_per_s"] - 12 / 20) < 1e-12
    assert abs(out["secondary"]["windowed_updates_per_s"] - 6.6 / 6) < 1e-12
    assert abs(out["secondary"]["reciprocal_mean_sum_updates_per_s"] - 1.3) < 1e-12


def test_nan_mean_fails_summarize():                             # codex 21535 probe
    w = [worker(0, 2, 0.0, 1.0), worker(1, 2, 0.0, 1.1)]
    w[0]["mean_measured_s"] = float("nan")
    assert pk.summarize(w, 2, 2)["status"] == "failed"


def test_fractional_counting_inside_window():
    w = worker(0, 1, 0.0, 2.0)                                   # measured updates [4,6] ... [14,16]
    assert pk.window_updates([w], 5.0, 9.0) == 0.5 + 1.0 + 0.5
    assert pk.window_updates([w], w["measured_start"], w["measured_end"]) == pk.MEASURED


def _span_gap(w):
    """Insert a 30 s gap after update 4 (rows and measured end stay mutually consistent)."""
    for u in w[0]["updates"]:
        if u["update"] >= 5:
            u["t_end"] += 30
    w[0]["measured_end"] = w[0]["updates"][-1]["t_end"]


@pytest.mark.parametrize("mutate, needle", [
    (lambda w: w[1].__setitem__("rank", 0), "ranks"),
    (lambda w: w[0]["updates"].pop(), "update ids"),
    (lambda w: w[0]["updates"][3].__setitem__("seconds", float("nan")), "non-finite"),
    (lambda w: w[0]["updates"][3].__setitem__("seconds", 0.0), "non-finite"),
    (lambda w: w[1]["updates"][pk.WARMUP - 1].pop("barrier_release"), "barrier"),
    (lambda w: w[0].__setitem__("phase", 1), "mismatch"),
    (lambda w: w[1].__setitem__("seed", 7), "mismatch"),
    (lambda w: w[0].__setitem__("mean_measured_s", 0.5), "inconsistent"),
    (lambda w: w[0]["updates"][5].__setitem__("t_end", w[0]["updates"][4]["t_end"]), "increasing"),
    (_span_gap, "span"),
    (lambda w: w[0].__setitem__("mean_measured_s", float("nan")), "non-finite or non-positive mean"),
    (lambda w: w[1].__setitem__("measured_start", float("nan")), "non-finite or non-positive mean"),
    (lambda w: w[1].__setitem__("measured_end", float("inf")), "non-finite or non-positive mean"),
])
def test_validate_rejects_malformed_records(mutate, needle):
    w = [worker(0, 2, 0.0, 1.0), worker(1, 2, 0.0, 1.1)]
    assert pk.validate_workers(w, 2, 2) is None
    bad = copy.deepcopy(w)
    mutate(bad)
    assert needle in pk.validate_workers(bad, 2, 2)


def _alive(tag: str) -> int:
    """Live processes whose command line is exactly `sleep <tag>` (tags are unique per test)."""
    out = subprocess.run(["pgrep", "-fx", f"sleep {tag}"], capture_output=True, text=True)
    return len(out.stdout.split())


def test_launch_failure_kills_already_started_workers(tmp_path):
    tag = "30.4711"                                           # exec'd directly: the Popen pid IS sleep

    def cmd(phase, r, k, d, smoke):
        return ["sleep", tag] if r == 0 else ["/nonexistent/worker"]
    res = pk.run_test(2, 2, tmp_path, cmd=cmd)
    assert res["status"] == "failed" and "launch/wait" in res["problem"]
    assert _alive(tag) == 0


def test_test_timeout_kills_workers(tmp_path, monkeypatch):
    monkeypatch.setattr(pk, "TEST_TIMEOUT_S", 0.5)
    tag = "30.4712"

    def cmd(phase, r, k, d, smoke):
        return ["sleep", tag]
    res = pk.run_test(1, 3, tmp_path, cmd=cmd)
    assert res["status"] == "failed" and res["worker_exit"] == ["timeout"] * 3
    assert _alive(tag) == 0


def test_parent_death_arming_refuses_a_wrong_parent():
    load = (f"import importlib.util as u, os; s=u.spec_from_file_location('p', {str(SCRIPT)!r}); "
            "m=u.module_from_spec(s); s.loader.exec_module(m); ")
    bad = subprocess.run([sys.executable, "-c", load + "m.arm_parent_death(1)"], capture_output=True, text=True,
                         timeout=60)
    assert bad.returncode != 0 and "already gone" in bad.stderr
    ok = subprocess.run([sys.executable, "-c", load + "m.arm_parent_death(os.getppid()); print('armed')"],
                        capture_output=True, text=True, timeout=60)
    assert ok.stdout.strip() == "armed"

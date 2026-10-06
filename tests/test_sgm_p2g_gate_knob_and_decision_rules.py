"""P2G (prereg v0.2 25fdbc5): beta-bias init knob identity + registered
decision rules (classifier, Q1/Q2 tables, half-oracle, rho, AUROC)."""

from __future__ import annotations

import hashlib
import importlib.util
import itertools
import json
import math
import random
from dataclasses import asdict
from pathlib import Path

import pytest

from memsub.sgm.synthetic_pilot import PilotConfig, build

ROOT = Path(__file__).resolve().parents[1]
# default build parameter hashes recorded at cb452fb, BEFORE the knob existed
PRE_KNOB_DEFAULT_BUILD = {0: "420ec93d2e2d2a8587b3a1b58680c0faddf7ce93f43a87ebddf4ffbf1591351c",
                          1: "db4f84630e7e16fb17e0942155e5654ec9f68041192a7024700c115823448ee3"}


def _load(name):
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


R = _load("sgm-p2g-decision-rules")


def _params(pcfg):
    rt, _be, head = build(pcfg)
    return {**{f"adapters.{k}": v for k, v in rt.adapters.state_dict().items()},
            **{f"head.{k}": v for k, v in head.state_dict().items()}}


# ---------------- knob ----------------

def _recorded_hash(pcfg):
    """The exact procedure used to record PRE_KNOB_DEFAULT_BUILD at cb452fb."""
    rt, _be, head = build(pcfg)
    h = hashlib.sha256()
    for k, v in sorted(rt.adapters.state_dict().items()) + sorted(head.state_dict().items()):
        h.update(k.encode())
        h.update(v.detach().contiguous().numpy().tobytes())
    return h.hexdigest()


@pytest.mark.parametrize("seed", [0, 1])
def test_default_build_is_bitwise_the_pre_knob_build(seed):
    assert _recorded_hash(PilotConfig(n_bindings=16, seed=seed)) == PRE_KNOB_DEFAULT_BUILD[seed]
    assert _recorded_hash(PilotConfig(n_bindings=16, seed=seed, beta_bias_init=None)) == PRE_KNOB_DEFAULT_BUILD[seed]


@pytest.mark.parametrize("seed", [0, 1])
def test_gate_build_differs_only_in_beta_bias(seed):
    base, gate = _params(PilotConfig(seed=seed)), _params(PilotConfig(seed=seed, beta_bias_init=-3.0))
    assert base.keys() == gate.keys()
    changed = {k for k in base if not (base[k] == gate[k]).all()}
    assert changed == {k for k in base if k.endswith("beta_proj.bias")} and len(changed) == 2
    assert all((gate[k] == -3.0).all() for k in changed)


def test_result_label_and_legacy_configs():
    assert PilotConfig(beta_bias_init=-3.0).result_label().endswith("+DIAGNOSTIC-beta-bias-3")
    assert PilotConfig().result_label() == "tiny-random-lm+taskhead"
    v2 = json.loads((ROOT / "configs" / "m4_sgm_p2g_inputs.json").read_text())["reused"]
    for ref in v2.values():                     # legacy manifests without the field still build
        assert PilotConfig(**ref["pilot_config"]).beta_bias_init is None


def test_grid_pilots_round_trip_through_the_manifest_equality_check():
    spec = importlib.util.spec_from_file_location("v1", ROOT / "modal-runners" / "modal-m4-sgm-p2d-diagnostics-grid.py")
    v1 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(v1)
    cells = v1.expand(json.loads((ROOT / "configs" / "m4_sgm_p2g_grid.json").read_text()))
    assert len(cells) == 6
    later_defaults = {"filler_len_schedule": [], "backbone": "tiny", "device": "cpu"}   # added after P2G (P2C, P2.5)
    for _rid, tag, pilot in cells:              # validator requires manifest pilot_config == grid pilot
        written = json.loads(json.dumps(asdict(PilotConfig(**pilot))))
        assert {k: v for k, v in written.items() if k in pilot} == pilot      # P2G source wrote exactly this
        assert {k: v for k, v in written.items() if k not in pilot} == later_defaults
        assert pilot["beta_bias_init"] == (-3.0 if tag == "gateclosed" else None)
        assert pilot["filler_writes"] is (tag != "filleroff")


# ---------------- rules ----------------

def _ci(diff, lo, hi):
    return {"diff": diff, "lo": lo, "hi": hi, "n": 256}


@pytest.mark.parametrize("seeds,label", [
    ((_ci(.05, .01, .09), _ci(.3, .2, .4)), R.GAIN),
    ((_ci(-.05, -.09, -.01), _ci(-.3, -.4, -.2)), R.LOSS),
    ((_ci(.01, -.02, .04), _ci(-.3, -.4, -.2)), R.EXCLUDED),
    ((_ci(.3, .2, .4), _ci(.01, -.02, .04)), R.NEITHER),       # one-seed gain is not reproducible
    ((_ci(.049, .01, .09), _ci(.3, .2, .4)), R.NEITHER),       # below the 5pp floor
    ((_ci(.04, -.01, .049), _ci(.0, -.03, .03)), R.EXCLUDED),
])
def test_classifier_is_ordered_and_total(seeds, label):
    assert R.classify({"0": seeds[0], "1": seeds[1]}) == label


def test_classifier_needs_both_seeds():
    with pytest.raises(SystemExit):
        R.classify({"0": _ci(.3, .2, .4)})


def test_q1_table_is_total_and_half_null_is_its_own_reading():
    seen = {}
    for gain, sup, mem, half in itertools.product((R.GAIN, R.NEITHER), (True, False), (True, False), (True, False, None)):
        seen[(gain, sup, mem, half)] = R.q1_reading(gain, sup, mem, half)
    assert len(seen) == 24 and all(isinstance(v, str) and v for v in seen.values())
    rows = {seen[(R.GAIN, True, True, h)] for h in (True, False, None)}
    assert len(rows) == 3 and seen[(R.GAIN, True, True, True)].startswith("SUPPORTS")
    assert "unavailable" in seen[(R.GAIN, True, True, None)]
    assert not any(v.startswith("SUPPORTS") for k, v in seen.items() if k != (R.GAIN, True, True, True))
    assert "mechanism unresolved" in seen[(R.GAIN, False, True, True)]
    assert R.EXCLUDED in R.q1_reading(R.EXCLUDED, False, False, None)


def test_half_status_null_unless_oracle_is_a_reproducible_gain():
    ok = {"0": _ci(.1, .01, .2), "1": _ci(.1, .02, .2)}
    assert R.half_status(R.NEITHER, ok) is None and R.half_status(R.EXCLUDED, ok) is None
    assert R.half_status(R.GAIN, ok) is True
    assert R.half_status(R.GAIN, {**ok, "1": _ci(.1, -.01, .2)}) is False


def test_q2_four_conjunction_readings():
    def labels(t, e):
        return {"C_T|off": t, "C_T|on": t, "C_E|Ton": e, "C_E|Toff": e}
    out = {(t, e): R.q2_reading(labels(R.GAIN if t else R.NEITHER, R.GAIN if e else R.LOSS))
           for t in (True, False) for e in (True, False)}
    assert len(set(out.values())) == 4 and out[(False, False)] == "neither conjunction met"
    assert R.q2_reading({**labels(R.GAIN, R.GAIN), "C_T|on": R.NEITHER}).startswith("reproducible gain for the no-filler-write eval")


def _rows(scores):
    """Rows for 256 episodes x 4 queries with per-episode hit counts `scores`."""
    return [{"batch": e // 16, "episode": e % 16, "episode_hash": f"h{e}", "query": q, "key": 0,
             "label": 1, "pred": 1 if q < k else 2, "correct": q < k, "intervention": "none"}
            for e, k in enumerate(scores) for q in range(4)]


def test_linear_contrasts_match_brute_force_and_need_shared_episodes():
    rng = random.Random(0)
    g, v, o = ([rng.randint(0, 4) for _ in range(256)] for _ in range(3))
    got = R.half_oracle(_rows(g), _rows(v), _rows(o))
    d = [(a - b) / 4 - 0.5 * (c - b) / 4 for a, b, c in zip(g, v, o)]
    mean = sum(d) / 256
    sd = math.sqrt(sum((x - mean) ** 2 for x in d) / 255)
    assert got["diff"] == pytest.approx(mean, abs=1e-12)
    assert got["hi"] - got["diff"] == pytest.approx(1.96 * sd / 16, abs=1e-12)
    bad = _rows(o)
    bad[0] = {**bad[0], "episode_hash": "other"}
    for r in bad[1:4]:
        r["episode_hash"] = "other"
    with pytest.raises(SystemExit):
        R.half_oracle(_rows(g), _rows(v), bad)


def test_suppression_ratio_fails_closed():
    assert R.suppression_ratio([0.1, 0.1], [0.5, 0.5]) == pytest.approx(0.2)
    assert R.suppression_ratio([0.0, 0.0], [0.5]) == 0.0              # skipped filler writes count as 0
    for f, b in (([], [1.0]), ([1.0], []), ([1.0], [0.0]), ([1.0], [-1.0]), ([math.nan], [1.0]), ([1.0], [math.inf])):
        with pytest.raises(SystemExit):
            R.suppression_ratio(f, b)


def test_auroc_ranks_ties_and_undefined():
    assert R.auroc([0.9, 0.8], [0.1, 0.2]) == 1.0 and R.auroc([0.1], [0.9]) == 0.0
    assert R.auroc([0.5, 0.5], [0.5]) == 0.5 and R.auroc([], [0.1]) is None and R.auroc([0.1], []) is None
    rng = random.Random(1)
    pos, neg = [rng.choice([0.1, 0.2, 0.3]) for _ in range(40)], [rng.choice([0.1, 0.2]) for _ in range(30)]
    brute = sum((p > n) + 0.5 * (p == n) for p in pos for n in neg) / (40 * 30)
    assert R.auroc(pos, neg) == pytest.approx(brute, abs=1e-12)

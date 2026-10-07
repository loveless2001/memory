"""Readout probe: priced FULL-ENVELOPE ledger (proposal v0.2 §9; codex 21750 #4, 21752), write-once.

The deadline is the v6 learned-n32 slot reserve life (same 2-cell workload, smaller head). The cap request prices
that WHOLE immutable deadline at the v6 worst-case billing basis (rate(2.0)), plus:
  * the stop tail: one reaper period plus one stop latency (120 + 120 s). This is a DECLARED operational assumption,
    not a guarantee from the earlier 60 s CPU self-stop proof;
  * the in-app reaper ticks over the pre-spawn window (<= ABANDON_S) + the deadline + the tail;
  * two image builds (GPU image, reaper image) and a margin.
The expected cost is the actual P2.5 learned-n32 slot billing (reference only). Nothing here is an approval.

    .venv/bin/python scripts/sgm-p2p5-readout-probe-priced-ledger.py
"""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
V6 = ROOT / "plans/261006-1345-m4-sgm-p2p5-qwen3-0p6b-screen/pk6/priced-estimate-v6.json"
V6_SCRIPT = ROOT / "scripts/sgm-p2p5-pk6-packed-campaign-priced-estimate.py"
BILLING = ROOT / "plans/261006-1345-m4-sgm-p2p5-qwen3-0p6b-screen/pk-campaign-launch/attempt-2/94-billing-hourly-prelim-20261007T1744Z.json"
OUT = ROOT / "plans/261008-0144-m4-sgm-p2p5-readout-recipe-rescue-probe/probe-priced-ledger.json"
# the v6 script's rates and allowances (2026-10-06), copied verbatim; the script is bound by sha below
GPU_USD_S, CPU_USD_CORE_S, MEM_USD_GIB_S, CORES, GIB = 0.000694, 0.0000131, 0.00000222, 8, 64
IMAGE_USD, TICK_S, TICK_STARTUP_S = 0.168384, 110, 30
REAPER_PERIOD_S, STOP_LATENCY_S, ABANDON_S, MARGIN_USD = 120, 120, 1800, 2.0
REAPER_CPU, REAPER_GIB, BASIS = 0.125, 0.25, 2.0


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def rate(basis: float) -> float:
    return GPU_USD_S + basis * (CORES * CPU_USD_CORE_S + GIB * MEM_USD_GIB_S)


def ledger() -> dict:
    v6 = json.loads(V6.read_text())
    deadline = float(v6["slots"]["learned-n32"]["reserve_life_s"])
    tail = REAPER_PERIOD_S + STOP_LATENCY_S
    gpu_app = (deadline + tail) * rate(BASIS)
    reaper_life = ABANDON_S + deadline + tail
    reaper = (reaper_life / REAPER_PERIOD_S) * (TICK_S + TICK_STARTUP_S) * BASIS * (
        REAPER_CPU * CPU_USD_CORE_S + REAPER_GIB * MEM_USD_GIB_S)
    images = 2 * IMAGE_USD
    total = gpu_app + reaper + images + MARGIN_USD
    rows = json.loads(BILLING.read_text())
    actual = sum(float(r["cost"]) for r in rows if r["description"] == "memsub-m4-sgm-p2p5-pk-campaign-learned-n32")
    return {"format": "p2p5-readout-probe-ledger-v1",
            "inputs": {"v6_sha256": sha(V6), "v6_script_sha256": sha(V6_SCRIPT), "billing_reference_sha256": sha(BILLING)},
            "deadline_s": deadline, "deadline_source": "v6 slots.learned-n32.reserve_life_s",
            "rate_usd_s": {"basis": BASIS, "value": rate(BASIS)},
            "assumptions": {"stop_tail_s": tail, "reaper_period_s": REAPER_PERIOD_S, "stop_latency_s": STOP_LATENCY_S,
                            "abandon_s": ABANDON_S,
                            "note": "the 240 s stop tail and the 120 s period are DECLARED operational assumptions"},
            "items_usd": {"gpu_app_full_deadline": gpu_app, "reaper_ticks": reaper, "images": images,
                          "margin": MARGIN_USD},
            "cap_request_usd": round(total + 0.005, 2),
            "expected_reference_usd": {"p2p5_learned_n32_slot_actual_prelim": actual,
                                       "note": "actual P2.5 learned-n32 slot billing (prelim snapshot); reference only"}}


def main():
    if OUT.exists():
        raise SystemExit(f"refusing to overwrite {OUT}")
    d = ledger()
    OUT.write_text(json.dumps(d, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"deadline_s": d["deadline_s"], "cap_request_usd": d["cap_request_usd"],
                      "expected": round(d["expected_reference_usd"]["p2p5_learned_n32_slot_actual_prelim"], 2)}))


if __name__ == "__main__":
    main()

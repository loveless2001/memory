"""P2G common observer (prereg v0.2 § Runtime): ONE runtime — the P2G memsub
source — evaluates every train-write × eval-write corner. Eval-write E=off is
the existing `filler_writes=False` ingest mask (tail-filler steps skip writes).

  * `load_checkpoint` rebuilds a cell from its OWN saved pilot config, then
    loads its parameters, so a learned beta bias is retained (the gate init
    knob runs inside `build()` BEFORE the weights are loaded, never after).
  * `eval_rows` reproduces the legacy final-eval loop (P2 v2 / P2D runs and the
    Step 2 baselines: same interventions order, 16x16 episodes, row format).
  * `gate_events` collects per-token write-gate events on dev 4242 for the
    registered pooled suppression statistic and descriptive AUROCs.
"""

from __future__ import annotations

import importlib.util
import json
import math
import sys
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from memsub.sgm.synthetic_binding_task import sample_batch  # noqa: E402
from memsub.sgm.synthetic_pilot import PilotConfig, build  # noqa: E402
from memsub.sgm.synthetic_pilot_evaluation import evaluate, ingest  # noqa: E402

LEGACY_IVS = ("none", "bank_derange", "coord_shuffle", "read_offset", "query_off")   # parity fixtures
FINAL_IVS = ("none", "bank_derange", "read_offset")                                 # P2G final protocol
FINAL_BATCHES = FINAL_BATCH_SIZE = 16
DEV_SEED, DEV_BATCHES, DEV_BATCH_SIZE, SINKS = 4242, 4, 16, 4
REGISTERED_HEADS = frozenset({(1, 0), (1, 1), (3, 0), (3, 1)})    # layers {1,3} x heads {0,1}

_spec = importlib.util.spec_from_file_location("p2g_rules", ROOT / "scripts" / "sgm-p2g-decision-rules.py")
RULES = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(RULES)


def load_checkpoint(pilot: dict, params: Path):
    """(pcfg, backend, head) for a saved cell; parameters loaded AFTER build."""
    from safetensors.torch import load_file
    pcfg = PilotConfig(**pilot)
    runtime, backend, head = build(pcfg)
    t = load_file(str(params))
    runtime.adapters.load_state_dict({k[9:]: v for k, v in t.items() if k.startswith("adapters.")})
    head.load_state_dict({k[5:]: v for k, v in t.items() if k.startswith("head.")})
    return pcfg, backend, head


def eval_rows(backend, head, pcfg, seed: int, interventions: tuple, filler_writes: bool) -> list:
    """Per-example heldout rows, legacy loop order (one evaluate() per intervention)."""
    rows: list = []
    for iv in interventions:
        evaluate(backend, head, pcfg.task_spec(), pcfg.arm, pcfg.readout, split="heldout",
                 batches=FINAL_BATCHES, batch_size=FINAL_BATCH_SIZE, seed=seed, intervention=iv,
                 per_example=rows, filler_writes=filler_writes)
    return rows


def rows_text(rows: list) -> str:
    """Byte format of every legacy per-example file (one json.dumps per line)."""
    return "".join(json.dumps(r) + "\n" for r in rows)


def token_class(t: int, n_bindings: int) -> str:
    if t < SINKS:
        return "sink"
    if t >= SINKS + 2 * n_bindings:
        return "filler"
    return "key" if (t - SINKS) % 2 == 0 else "value"


@torch.no_grad()
def gate_events(backend, pcfg, filler_writes: bool) -> dict:
    """{(layer, head): {class: {"projected": [...], "effective": [...], "applied": [...]}}}
    over dev 4242 = 4 batches x 16 rows = 64 episodes. Binding = key ∪ value;
    sinks excluded. A skipped write is effective 0 and absent from `applied`."""
    spec, gen = pcfg.task_spec(), torch.Generator().manual_seed(DEV_SEED)
    layers, heads = backend.runtime.cfg.selected_layers, backend.runtime.cfg.memory_heads
    ev = {(l, h): {c: {"projected": [], "effective": [], "applied": []} for c in ("binding", "filler")}
          for l in layers for h in range(heads)}
    for _ in range(DEV_BATCHES):
        batch = sample_batch(spec, "heldout", DEV_BATCH_SIZE, gen)
        traces: list = []
        ingest(backend, batch, "learned", traces, filler_writes, spec.n_bindings)
        for t, tr in enumerate(traces):
            cls = token_class(t, spec.n_bindings)
            if cls == "sink":
                continue
            cls = "filler" if cls == "filler" else "binding"
            for l in layers:
                proj = tr["beta_projected"][l]                               # [B, H]
                applied = l in tr.get("beta", {})
                eff = tr["beta"][l] if applied else torch.zeros_like(proj)
                for h in range(heads):
                    slot = ev[(l, h)][cls]
                    slot["projected"] += proj[:, h].tolist()
                    slot["effective"] += eff[:, h].tolist()
                    if applied:
                        slot["applied"] += eff[:, h].tolist()
    return ev


def check_gate_events(ev: dict, want: dict) -> None:
    """Fail closed unless telemetry covers exactly the registered heads with the
    expected populations, every beta is finite and in [0, 1], and applied events
    are all-or-none per class: all applied (== effective) or all skipped (effective 0)."""
    if not isinstance(ev, dict) or set(ev) != REGISTERED_HEADS:
        raise SystemExit(f"gate telemetry heads {sorted(ev) if isinstance(ev, dict) else ev} != registered")
    for (l, h), cls in ev.items():
        if set(cls) != set(want):
            raise SystemExit(f"L{l}h{h}: classes {sorted(cls)} != {sorted(want)}")
        for c, n in want.items():
            arr = cls[c]
            if set(arr) != {"projected", "effective", "applied"}:
                raise SystemExit(f"L{l}h{h} {c}: malformed event record")
            if len(arr["projected"]) != n or len(arr["effective"]) != n:
                raise SystemExit(f"L{l}h{h} {c}: {len(arr['effective'])} events != {n}")
            for k in ("projected", "effective", "applied"):
                if not all(isinstance(x, float) and math.isfinite(x) and 0.0 <= x <= 1.0 for x in arr[k]):
                    raise SystemExit(f"L{l}h{h} {c} {k}: non-finite or out-of-range beta")
            if arr["applied"] != (arr["effective"] if arr["applied"] else []) or len(arr["applied"]) not in (0, n):
                raise SystemExit(f"L{l}h{h} {c}: partial or inconsistent applied events")
            if not arr["applied"] and any(x != 0.0 for x in arr["effective"]):
                raise SystemExit(f"L{l}h{h} {c}: skipped events must have effective beta 0")


def gate_summary(ev: dict, n_bindings: int) -> dict:
    """Registered pooled rho + descriptive per-(layer, head) means and AUROCs.
    Validation runs BEFORE any AUROC or rho computation."""
    episodes = DEV_BATCHES * DEV_BATCH_SIZE
    want = {"filler": episodes * 40, "binding": episodes * 2 * n_bindings}
    check_gate_events(ev, want)
    per_head, fill_eff, bind_eff, aucs = {}, [], [], []
    for (l, h), cls in sorted(ev.items()):
        auc = RULES.auroc(cls["binding"]["applied"], cls["filler"]["applied"])
        aucs.append(auc)
        fill_eff += cls["filler"]["effective"]
        bind_eff += cls["binding"]["effective"]
        per_head[f"L{l}h{h}"] = {
            "auroc_applied": auc,
            **{f"{c}_{k}_mean": (sum(cls[c][k]) / len(cls[c][k]) if cls[c][k] else None)
               for c in ("binding", "filler") for k in ("projected", "effective")},
            **{f"{c}_applied_events": len(cls[c]["applied"]) for c in ("binding", "filler")}}
    defined = [a for a in aucs if a is not None]
    return {"episodes": episodes, "events_per_head": want,
            "rho_pooled_effective": RULES.suppression_ratio(fill_eff, bind_eff),
            "auroc_mean_defined": sum(defined) / len(defined) if defined else None,
            "auroc_min_defined": min(defined) if defined else None,
            "auroc_defined_heads": len(defined), "per_head": per_head}

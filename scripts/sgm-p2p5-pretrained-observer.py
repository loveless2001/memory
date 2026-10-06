"""P2.5 observer for the pinned frozen Qwen3-0.6B-Base (prereg v0.2 § R5).

Reuses the cleared common-observer functions (checkpoint loading after
build, legacy-order evaluation loop, canonical row text, gate summary with its
fail-closed population checks) through a PRIVATE module instance whose
registered head set is rebound to the P2.5 16-head set (layers 6/13/20/27 ×
heads 0–3); the closed P2G/P2C observer file stays byte-identical. Gate events
are collected arm-aware (oracle addresses only for the oracle arm); telemetry
for `memory_off` (SGM disabled) is reported as unavailable, never as a zero
population. Episodes are sampled on CPU; the runtime moves them to its device.
"""

import importlib.util
import sys
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from memsub.sgm.pinned_pretrained_qwen3_backbone import P2P5_SGM_DEFAULTS  # noqa: E402
from memsub.sgm.synthetic_binding_task import sample_batch  # noqa: E402
from memsub.sgm.synthetic_pilot_evaluation import ingest  # noqa: E402

_spec = importlib.util.spec_from_file_location("p2g_observer_for_p2p5",
                                               ROOT / "scripts" / "sgm-p2g-common-observer-evaluation.py")
OBS = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(OBS)
OBS.REGISTERED_HEADS = frozenset((l, h) for l in P2P5_SGM_DEFAULTS["selected_layers"]
                                 for h in range(P2P5_SGM_DEFAULTS["memory_heads"]))
RULES = OBS.RULES
load_checkpoint, eval_rows, rows_text, FINAL_IVS = OBS.load_checkpoint, OBS.eval_rows, OBS.rows_text, OBS.FINAL_IVS


@torch.no_grad()
def gate_events(backend, pcfg) -> dict:
    """As the common observer's gate_events, but ingesting with the cell's OWN arm."""
    spec, gen = pcfg.task_spec(), torch.Generator().manual_seed(OBS.DEV_SEED)
    layers, heads = backend.runtime.cfg.selected_layers, backend.runtime.cfg.memory_heads
    ev = {(l, h): {c: {"projected": [], "effective": [], "applied": []} for c in ("binding", "filler")}
          for l in layers for h in range(heads)}
    for _ in range(OBS.DEV_BATCHES):
        batch = sample_batch(spec, "heldout", OBS.DEV_BATCH_SIZE, gen)
        traces: list = []
        ingest(backend, batch, pcfg.arm, traces, pcfg.filler_writes, spec.n_bindings)
        for t, tr in enumerate(traces):
            cls = OBS.token_class(t, spec.n_bindings)
            if cls == "sink":
                continue
            cls = "filler" if cls == "filler" else "binding"
            for l in layers:
                proj = tr["beta_projected"][l]
                applied = l in tr.get("beta", {})
                eff = tr["beta"][l] if applied else torch.zeros_like(proj)
                for h in range(heads):
                    slot = ev[(l, h)][cls]
                    slot["projected"] += proj[:, h].tolist()
                    slot["effective"] += eff[:, h].tolist()
                    if applied:
                        slot["applied"] += eff[:, h].tolist()
    return ev


def gate_telemetry(backend, pcfg) -> dict:
    """Descriptive 16-head telemetry; unavailable when SGM is disabled."""
    if pcfg.arm == "memory_off":
        return {"status": "unavailable: SGM disabled (local-only control)"}
    return {"status": "measured", **OBS.gate_summary(gate_events(backend, pcfg), pcfg.n_bindings)}

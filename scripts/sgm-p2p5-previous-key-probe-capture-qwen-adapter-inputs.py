"""Capture the exact SGM adapter inputs x (normalized PRE-attention z passed to project()) for the
previous-key information probe (proposal v0.3). Forward only: torch.no_grad(), no optimizer, no training.

Frozen condition: P2.5 learned arm, seed-0 init, pilot_config from the bound manifest (sha-checked),
device forced to CPU, SGM enabled at init (what the adapter sees at step 0), feature_shift=1.
Returns numpy arrays only; the caller releases the model before any fitting (codex 22395).
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]

def require(ok: bool, msg: str) -> None:
    """Explicit refusal (survives python -O, unlike assert)."""
    if not ok:
        raise RuntimeError(msg)

sys.path.insert(0, str(ROOT))
from memsub.sgm.synthetic_binding_task import SINK_IDS, BindingTaskSpec, sample_batch  # noqa: E402
from memsub.sgm.synthetic_pilot import PilotConfig, build  # noqa: E402
from memsub.sgm.synthetic_pilot_evaluation import ingest  # noqa: E402

MANIFEST = ROOT / "plans/261009-0030-m4-sgm-p2p5-taskhead-read-escape-blocker-screen/inputs/probe-taskhead-learned-n32-s0-run_manifest.json"
MANIFEST_SHA256 = "4e89b95adcff68b73fecb2f071c3fe17498c7e62fd1a97ac04f77691b5fc0bb0"
SPEC = BindingTaskSpec(n_bindings=32, n_queries=4, filler_len=40)


def frozen_pilot_config() -> PilotConfig:
    raw = MANIFEST.read_bytes()
    require(hashlib.sha256(raw).hexdigest() == MANIFEST_SHA256, "manifest hash mismatch")
    base = json.loads(raw)["pilot_config"]
    require(base["arm"] == "learned" and base["backbone"] == "qwen3-0.6b-base" and base["seed"] == 0,
            "manifest is not the frozen learned / qwen3-0.6b-base / seed-0 condition")
    return PilotConfig(**{**base, "device": "cpu"})                 # the only override


def load_model():
    # Test guard (codex 22400): tests and mutation runs set PKPROBE_FORBID_MODEL=1 so no path can load Qwen.
    require(os.environ.get("PKPROBE_FORBID_MODEL") != "1", "MODEL LOAD ATTEMPTED under PKPROBE_FORBID_MODEL=1")
    pcfg = frozen_pilot_config()
    runtime, backend, head = build(pcfg)
    require(runtime.cfg.feature_shift == 1, "frozen condition requires feature_shift=1")
    for p in list(runtime.adapters.parameters()) + list(head.parameters()):
        p.requires_grad_(False)                                    # no training anywhere
    return pcfg, runtime, backend


def capture(runtime, backend, pcfg, split: str, n_episodes: int, seed: int, batch: int = 4,
            log=print) -> dict:
    """Run ingest on n_episodes and return per-layer adapter inputs at key and value positions,
    plus key/value token ids. Asserts exactly one project() call per source step per layer."""
    layers = [int(l) for l in runtime.adapters]
    rec = {l: [] for l in layers}
    origs = {}
    for l, a in runtime.adapters.items():
        origs[l] = a.project

        def wrapped(x, _orig=a.project, _l=int(l)):
            rec[_l].append(x.detach().to(torch.float32).clone())
            return _orig(x)
        a.project = wrapped
    s, n, T = len(SINK_IDS), SPEC.n_bindings, SPEC.source_len()
    gen = torch.Generator().manual_seed(seed)
    zk = {l: [] for l in layers}; zv = {l: [] for l in layers}
    keys, vals = [], []
    try:
        with torch.no_grad():
            done = 0
            while done < n_episodes:
                b = min(batch, n_episodes - done)
                eb = sample_batch(SPEC, split, b, gen)
                for v in rec.values():
                    v.clear()
                ingest(backend, eb, pcfg.arm, None, True, n)
                for l in layers:
                    require(len(rec[l]) == T, f"layer {l}: {len(rec[l])} project() calls, expected {T}")
                    x = torch.cat(rec[l], dim=1)                   # [b, T, d_in]
                    require(torch.isfinite(x).all(), f"nonfinite adapter input at layer {l}")
                    zk[l].append(x[:, s:s + 2 * n:2].numpy()); zv[l].append(x[:, s + 1:s + 2 * n:2].numpy())
                require(torch.equal(eb.source[:, :s], torch.tensor(SINK_IDS).repeat(b, 1)), "unexpected sink layout")
                keys.append(eb.source[:, s:s + 2 * n:2].numpy()); vals.append(eb.source[:, s + 1:s + 2 * n:2].numpy())
                done += b
                log(f"capture {split} seed {seed}: {done}/{n_episodes}")
    finally:
        for l, a in runtime.adapters.items():
            a.project = origs[l]
    out = {"layers": layers, "key_ids": np.concatenate(keys), "value_ids": np.concatenate(vals)}
    for l in layers:
        out[f"zk_L{l}"] = np.concatenate(zk[l]); out[f"zv_L{l}"] = np.concatenate(zv[l])
    return out


def embeddings(runtime, ids: np.ndarray) -> np.ndarray:
    """Pinned input embeddings (float32 copy) for the given token ids."""
    w = runtime.backbone.model.embed_tokens.weight
    return w[torch.as_tensor(ids.reshape(-1))].detach().to(torch.float32).numpy().reshape(*ids.shape, -1)


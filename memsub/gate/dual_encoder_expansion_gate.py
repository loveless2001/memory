"""Dual-encoder expansion gate (GATE.md §4; spec §17.5).

f(query ⊕ recent gloss) · g(block shadow) over FROZEN Qwen3-Embedding-0.6B
(shadow-v1) embeddings — linear-probe tier: two projections, the interaction
score concatenated with cheap features into a small head, plus an auxiliary
workload-type head (pointwise vs aggregative, spec §4.7). BCE on the
counterfactual label y. Temperature scaling is calibrated PER EVICTION
FRACTION on the cal split.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass

import numpy as np
import torch
import torch.nn as nn

from .label_dataset_splits import DOMAINS, GateDataset


@dataclass
class TrainConfig:
    proj_dim: int = 256
    hidden: int = 64
    lr: float = 1e-3
    weight_decay: float = 1e-4
    epochs: int = 8
    batch_size: int = 4096
    aux_weight: float = 0.3
    seed: int = 0

    def config_hash(self) -> str:
        from ..hashing import sha256_json
        return sha256_json(dataclasses.asdict(self))


def _features(ds: GateDataset, idx: np.ndarray) -> np.ndarray:
    dom_onehot = np.stack([(ds.domain[idx] == d).astype(np.float32)
                           for d in DOMAINS], axis=1)
    return np.concatenate([
        ds.fraction[idx, None].astype(np.float32),
        ds.overlap[idx, None].astype(np.float32),
        ds.evicted[idx, None].astype(np.float32),
        dom_onehot], axis=1)


class DualEncoderExpansionGate(nn.Module):
    N_FEATURES = 3 + len(DOMAINS)

    def __init__(self, emb_dim: int, cfg: TrainConfig):
        super().__init__()
        self.cfg = cfg
        self.proj_q = nn.Linear(emb_dim, cfg.proj_dim, bias=False)
        self.proj_b = nn.Linear(emb_dim, cfg.proj_dim, bias=False)
        self.head = nn.Sequential(
            nn.Linear(1 + self.N_FEATURES, cfg.hidden), nn.ReLU(),
            nn.Linear(cfg.hidden, 1))
        self.aux_pointwise = nn.Linear(emb_dim, 1)
        # per-fraction calibration temperatures, set by calibrate()
        self.temperatures: dict[str, float] = {}

    def interaction(self, q, b) -> torch.Tensor:
        fq = torch.nn.functional.normalize(self.proj_q(q), dim=-1)
        fb = torch.nn.functional.normalize(self.proj_b(b), dim=-1)
        return (fq * fb).sum(-1, keepdim=True)

    def forward(self, q, b, feats):
        logit = self.head(torch.cat([self.interaction(q, b), feats], dim=-1))
        return logit.squeeze(-1), self.aux_pointwise(q).squeeze(-1)

    @torch.inference_mode()
    def predict_logits(self, ds: GateDataset, idx: np.ndarray,
                       device: str = "cpu") -> tuple[np.ndarray, np.ndarray]:
        self.eval()
        q = torch.from_numpy(ds.q_emb[idx]).to(device)
        b = torch.from_numpy(ds.b_emb[idx]).to(device)
        f = torch.from_numpy(_features(ds, idx)).to(device)
        logit, aux = self(q, b, f)
        return logit.cpu().numpy(), aux.cpu().numpy()

    def predict_proba(self, ds: GateDataset, idx: np.ndarray,
                      device: str = "cpu", calibrated: bool = True) -> np.ndarray:
        logits, _ = self.predict_logits(ds, idx, device)
        if calibrated and self.temperatures:
            t = np.array([self.temperatures.get(f"{fr:.2f}", 1.0)
                          for fr in ds.fraction[idx]])
            logits = logits / t
        return 1.0 / (1.0 + np.exp(-logits))


def train_gate(ds: GateDataset, train_mask: np.ndarray, cfg: TrainConfig,
               device: str = "cpu") -> DualEncoderExpansionGate:
    torch.manual_seed(cfg.seed)
    idx = np.flatnonzero(train_mask)
    model = DualEncoderExpansionGate(ds.q_emb.shape[1], cfg).to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=cfg.lr,
                            weight_decay=cfg.weight_decay)
    q = torch.from_numpy(ds.q_emb[idx]).to(device)
    b = torch.from_numpy(ds.b_emb[idx]).to(device)
    f = torch.from_numpy(_features(ds, idx)).to(device)
    y = torch.from_numpy(ds.y[idx].astype(np.float32)).to(device)
    aux_y = torch.from_numpy(ds.pointwise[idx].astype(np.float32)).to(device)
    bce = nn.BCEWithLogitsLoss()
    n = len(idx)
    for epoch in range(cfg.epochs):
        model.train()
        perm = torch.randperm(n, device=device)
        total = 0.0
        for s in range(0, n, cfg.batch_size):
            sel = perm[s:s + cfg.batch_size]
            opt.zero_grad()
            logit, aux = model(q[sel], b[sel], f[sel])
            loss = bce(logit, y[sel]) + cfg.aux_weight * bce(aux, aux_y[sel])
            loss.backward()
            opt.step()
            total += float(loss) * len(sel)
    return model


def calibrate_temperature(model: DualEncoderExpansionGate, ds: GateDataset,
                          cal_mask: np.ndarray, device: str = "cpu") -> dict:
    """Per-fraction scalar temperature minimizing NLL on the cal split
    (grid search — convex in log T, a grid is robust and dependency-free)."""
    idx_all = np.flatnonzero(cal_mask)
    logits, _ = model.predict_logits(ds, idx_all, device)
    y = ds.y[idx_all].astype(np.float64)
    out = {}
    for frac in np.unique(ds.fraction[idx_all]):
        m = ds.fraction[idx_all] == frac
        lg, yy = logits[m].astype(np.float64), y[m]
        best_t, best_nll = 1.0, np.inf
        for t in np.geomspace(0.25, 8.0, 61):
            p = 1 / (1 + np.exp(-lg / t))
            p = np.clip(p, 1e-7, 1 - 1e-7)
            nll = -np.mean(yy * np.log(p) + (1 - yy) * np.log(1 - p))
            if nll < best_nll:
                best_t, best_nll = float(t), float(nll)
        out[f"{frac:.2f}"] = best_t
    model.temperatures = out
    return out

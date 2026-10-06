"""Gate label dataset + splits (GATE.md §3).

One row per (item, eviction fraction); the fraction is a feature and labels
are evaluated per fraction. Splits are GROUPED BY SOURCE DOCUMENT and
stratified by domain — items from one document share content, so item-level
splits leak (GT6 keeps an intentionally-leaky item split for the control).
Leave-one-domain-out (LODO) is the generalization row.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

import numpy as np

DOMAINS = ("financial", "legal", "code", "literature")
FRACTIONS = ("0.25", "0.40")


@dataclass
class GateDataset:
    """Flat arrays, one row per (item, fraction)."""
    item_id: np.ndarray
    doc_id: np.ndarray
    domain: np.ndarray
    fraction: np.ndarray        # float feature
    y: np.ndarray               # 1 = expansion required (answers differ)
    overlap: np.ndarray         # evicted fraction of the source chunk
    evicted: np.ndarray         # overlap > 0.5
    pointwise: np.ndarray       # heuristic workload label (aux supervision)
    raw_correct: np.ndarray     # answer under raw span was gold
    compact_correct: np.ndarray  # answer under compacted ctx was gold
    q_emb: np.ndarray           # [n, d] frozen shadow-v1 embeddings
    b_emb: np.ndarray
    extras: dict = field(default_factory=dict)

    def __len__(self) -> int:
        return len(self.y)

    def subset(self, mask: np.ndarray) -> "GateDataset":
        return GateDataset(**{
            k: (v[mask] if isinstance(v, np.ndarray) else v)
            for k, v in self.__dict__.items()})


def build_dataset(rows: list[dict], q_emb: np.ndarray,
                  b_emb: np.ndarray) -> GateDataset:
    """Expand per-item label rows into per-(item, fraction) rows; embedding
    row i of q_emb/b_emb corresponds to rows[i]."""
    cols: dict[str, list] = {k: [] for k in (
        "item_id", "doc_id", "domain", "fraction", "y", "overlap", "evicted",
        "pointwise", "raw_correct", "compact_correct")}
    idx = []
    for i, r in enumerate(rows):
        for f in FRACTIONS:
            gold = r["gold"].strip().upper()[:1]
            cols["item_id"].append(r["item_id"])
            cols["doc_id"].append(r["doc_id"])
            cols["domain"].append(r["domain"])
            cols["fraction"].append(float(f))
            cols["y"].append(int(r[f"y_{f}"]))
            cols["overlap"].append(float(r[f"overlap_{f}"]))
            cols["evicted"].append(int(r[f"evicted_{f}"]))
            cols["pointwise"].append(int(r["pointwise_heuristic"]))
            cols["raw_correct"].append(int(r["raw_correct"]))
            cols["compact_correct"].append(
                int(r[f"pred_compact_{f}"].strip().upper()[:1] == gold))
            idx.append(i)
    idx = np.array(idx)
    return GateDataset(
        **{k: np.array(v) for k, v in cols.items()},
        q_emb=q_emb[idx].astype(np.float32),
        b_emb=b_emb[idx].astype(np.float32))


def _doc_bucket(doc_id: str) -> float:
    """Deterministic uniform hash of a document id into [0, 1)."""
    h = int.from_bytes(hashlib.sha256(doc_id.encode()).digest()[:8], "big")
    return h / 2**64


def make_splits(ds: GateDataset, mode: str = "document",
                holdout_domain: str | None = None,
                ratios: tuple[float, float] = (0.8, 0.9)) -> dict[str, np.ndarray]:
    """Return boolean masks {train, cal, test}.

    mode="document": group split by source document (shipped config).
    mode="item": intentionally leaky item-level split (GT6 control only).
    holdout_domain: that domain is excluded from train/cal and becomes the
    whole test set (LODO generalization row)."""
    n = len(ds)
    if holdout_domain is not None:
        held = ds.domain == holdout_domain
        keys = ds.doc_id if mode == "document" else ds.item_id
        buckets = np.array([_doc_bucket(k) for k in keys])
        train = ~held & (buckets < ratios[0])
        cal = ~held & (buckets >= ratios[0])
        return {"train": train, "cal": cal, "test": held}
    keys = ds.doc_id if mode == "document" else ds.item_id
    buckets = np.array([_doc_bucket(k) for k in keys])
    return {
        "train": buckets < ratios[0],
        "cal": (buckets >= ratios[0]) & (buckets < ratios[1]),
        "test": buckets >= ratios[1],
    }


def assert_no_doc_leakage(ds: GateDataset, splits: dict[str, np.ndarray]) -> None:
    train_docs = set(ds.doc_id[splits["train"]])
    for part in ("cal", "test"):
        overlap = train_docs & set(ds.doc_id[splits[part]])
        if overlap:
            raise AssertionError(
                f"document leakage into {part}: {sorted(overlap)[:5]}")

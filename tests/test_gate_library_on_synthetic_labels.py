"""Gate library logic tests on synthetic labels (no GPU, no real corpus).

Synthetic generator plants a doc-level latent that determines y, so the GT6
property is testable: an item-level (leaky) split must score HIGHER than the
document-level split, because leaked doc latents are memorizable.
"""

import numpy as np
import pytest

from memsub.gate import (
    BudgetedExpansionHarness,
    GateDataset,
    TrainConfig,
    end_to_end_lost_fact,
    expected_calibration_error,
    make_splits,
    threshold_sweep,
    train_gate,
)
from memsub.gate.dual_encoder_expansion_gate import calibrate_temperature
from memsub.gate.expansion_budget_harness import ExpansionDemand
from memsub.gate.gate_evaluation_metrics import baseline_decisions, operating_point
from memsub.gate.label_dataset_splits import assert_no_doc_leakage

DOMS = ("financial", "legal", "code", "literature")


def synthetic_dataset(n_docs=120, items_per_doc=6, dim=32, seed=0) -> GateDataset:
    rng = np.random.default_rng(seed)
    rows = {k: [] for k in ("item_id", "doc_id", "domain", "fraction", "y",
                            "overlap", "evicted", "pointwise", "raw_correct",
                            "compact_correct")}
    q_emb, b_emb = [], []
    for d in range(n_docs):
        doc_latent = rng.normal(size=dim)
        domain = DOMS[d % 4]
        for i in range(items_per_doc):
            qv = doc_latent + 0.5 * rng.normal(size=dim)
            bv = doc_latent + 0.5 * rng.normal(size=dim)
            for frac in (0.25, 0.40):
                evicted = int(rng.random() < frac + 0.1)
                overlap = evicted * (0.6 + 0.4 * rng.random())
                # y depends on content (doc latent) + eviction, plus noise
                logit = 2.5 * evicted + 1.2 * doc_latent[0] + frac - 1.8
                y = int(rng.random() < 1 / (1 + np.exp(-logit)))
                raw_ok = int(rng.random() < 0.85)
                rows["item_id"].append(f"it_{d}_{i}")
                rows["doc_id"].append(f"doc_{d}")
                rows["domain"].append(domain)
                rows["fraction"].append(frac)
                rows["y"].append(y)
                rows["overlap"].append(overlap)
                rows["evicted"].append(evicted)
                rows["pointwise"].append(int(rng.random() < 0.5))
                rows["raw_correct"].append(raw_ok)
                rows["compact_correct"].append(
                    int(raw_ok and (not y) or rng.random() < 0.1))
                q_emb.append(qv)
                b_emb.append(bv)
    return GateDataset(**{k: np.array(v) for k, v in rows.items()},
                       q_emb=np.array(q_emb, dtype=np.float32),
                       b_emb=np.array(b_emb, dtype=np.float32))


@pytest.fixture(scope="module")
def ds():
    return synthetic_dataset()


def _test_auc(model, ds, mask):
    p = model.predict_proba(ds, np.flatnonzero(mask))
    y = ds.y[mask]
    order = np.argsort(p)
    ranks = np.empty(len(p)); ranks[order] = np.arange(len(p))
    pos = ranks[y == 1]
    return (pos.sum() - len(pos) * (len(pos) - 1) / 2) / max(
        len(pos) * (len(p) - len(pos)), 1)


def test_document_split_has_no_leakage_and_partitions(ds):
    splits = make_splits(ds, mode="document")
    assert_no_doc_leakage(ds, splits)
    total = sum(int(m.sum()) for m in splits.values())
    assert total == len(ds)
    # rows of one item (two fractions) land in the same part
    for part in splits.values():
        docs = ds.item_id[part]
        assert set(docs).isdisjoint(set(ds.item_id[~part]) - set(docs))


def test_lodo_split_isolates_domain(ds):
    splits = make_splits(ds, mode="document", holdout_domain="legal")
    assert set(ds.domain[splits["test"]]) == {"legal"}
    assert "legal" not in set(ds.domain[splits["train"]])


def test_gt6_item_level_split_scores_higher(ds):
    cfg = TrainConfig(epochs=6, proj_dim=16, hidden=16)
    doc_splits = make_splits(ds, mode="document")
    item_splits = make_splits(ds, mode="item")
    auc_doc = _test_auc(train_gate(ds, doc_splits["train"], cfg), ds,
                        doc_splits["test"])
    auc_item = _test_auc(train_gate(ds, item_splits["train"], cfg), ds,
                         item_splits["test"])
    # content-dependent labels -> leaky split memorizes doc latents
    assert auc_item > auc_doc, (auc_item, auc_doc)
    assert auc_doc > 0.6  # the gate still learns real signal


def test_temperature_scaling_improves_cal_split_nll(ds):
    """Temperature scaling guarantees NLL improvement on the split it
    optimizes (per fraction); binned-ECE improvement on held-out data is
    GT7's job on the real labels, not a synthetic invariant."""
    cfg = TrainConfig(epochs=6, proj_dim=16, hidden=16)
    splits = make_splits(ds, mode="document")
    model = train_gate(ds, splits["train"], cfg)
    idx = np.flatnonzero(splits["cal"])

    def nll(p, y):
        p = np.clip(p, 1e-7, 1 - 1e-7)
        return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))

    p_raw = model.predict_proba(ds, idx, calibrated=False)
    temps = calibrate_temperature(model, ds, splits["cal"])
    p_cal = model.predict_proba(ds, idx, calibrated=True)
    y = ds.y[idx]
    assert set(temps) == {"0.25", "0.40"}
    assert all(t > 0 for t in temps.values())
    assert nll(p_cal, y) <= nll(p_raw, y) + 1e-9
    # ECE stays finite/sane and the reliability machinery runs
    assert expected_calibration_error(p_cal, y) < 0.5


def test_plane_baselines_ordering(ds):
    idx = np.arange(len(ds))
    base = baseline_decisions(ds, idx)
    never = end_to_end_lost_fact(ds, idx, base["never_expand"])
    always = end_to_end_lost_fact(ds, idx, base["always_expand"])
    oracle = end_to_end_lost_fact(ds, idx, base["oracle_expand"])
    assert always["lost_fact_rate_evicted"] == 0.0
    assert always["expand_rate_all"] == 1.0
    assert never["expand_rate_all"] == 0.0
    assert oracle["lost_fact_rate_evicted"] <= never["lost_fact_rate_evicted"]
    # oracle silent loss conditioned on prior-correct is (near) zero:
    # y=0 rows have compact == raw answers
    assert oracle["lost_fact_rate_evicted_prior_correct"] <= 0.15


def test_operating_point_honest_when_infeasible(ds):
    idx = np.arange(len(ds))
    p = np.zeros(len(ds))  # useless gate: never expands
    sweep = threshold_sweep(ds, idx, p, n_points=5)
    op = operating_point(sweep, target_lost=0.0001, max_expand_rate=0.5)
    assert op["gt9_feasible"] is False


def test_gt10_budget_exhaustion_surfaces_in_trace():
    harness = BudgetedExpansionHarness(max_retrieved_tokens=2000)
    demands = [ExpansionDemand(f"i{k}", score=1 - k * 0.1, token_cost=900)
               for k in range(5)]
    trace = harness.resolve(demands)
    assert harness.granted_tokens <= 2000
    granted = [t for t in trace if t.granted]
    exhausted = [t for t in trace if t.reason == "budget_exhausted"]
    assert len(granted) == 2 and len(exhausted) == 3  # nothing silently dropped
    assert len(trace) == len(demands)
    # highest scores granted first
    assert min(t.score for t in granted) >= max(t.score for t in exhausted)

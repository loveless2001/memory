"""Set-scoring selector s1: top-k grouped expansion (COMPACTOR.md §3).

M3 finding: per-block independent thresholding cannot represent "this query
needs blocks {i, j} jointly", so multi-hop queries over-expand (2.3x
oracle). s1 makes ONE grouped decision per query: rank candidate blocks by
gate score, enter only if the top score clears an entry threshold, then cut
the group at the largest marginal-score gap (budget-capped). For a
single-candidate query this degenerates exactly to the M3 pointwise rule at
tau_entry — the GT18 no-regression property by construction.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class GroupedExpansionDecision:
    expand_mask: list[bool]        # aligned with the candidate order given
    k: int
    entered: bool
    gap_at: float


@dataclass
class SetScoringSelector:
    tau_entry: float               # top score must clear this to expand at all
    min_keep_score: float = 0.05   # never include blocks below this
    k_max: int = 4                 # budget cap per query

    def decide(self, scores: list[float]) -> GroupedExpansionDecision:
        order = np.argsort(-np.asarray(scores, dtype=np.float64))
        s = np.asarray(scores, dtype=np.float64)[order]
        if len(s) == 0 or s[0] < self.tau_entry:
            return GroupedExpansionDecision([False] * len(s), 0, False, 0.0)
        m = min(self.k_max, int((s >= self.min_keep_score).sum()))
        if m <= 1:
            k, gap = 1, 0.0
        else:
            # cut the group at the largest marginal gap within the budget;
            # the tail gap (s[m-1] -> 0-ish) competes so a flat block of
            # high scores keeps all m
            gaps = np.diff(-s[:m])                # positive drops
            tail_gap = s[m - 1] - self.min_keep_score
            candidates = np.append(gaps, tail_gap)
            k = int(np.argmax(candidates)) + 1
            gap = float(candidates.max())
        mask = np.zeros(len(s), dtype=bool)
        mask[order[:k]] = True
        return GroupedExpansionDecision(mask.tolist(), k, True, gap)


def fit_tau_entry(scores_per_query: list[list[float]],
                  needed_sets: list[list[bool]],
                  taus: np.ndarray | None = None,
                  target_recall: float = 0.85, k_max: int = 4) -> dict:
    """Choose tau_entry on a train split: cheapest tau meeting the recall
    target (recall over needed blocks), reported with its expand cost."""
    taus = taus if taus is not None else np.linspace(0.05, 0.95, 37)
    best = None
    for tau in taus:
        sel = SetScoringSelector(tau_entry=float(tau), k_max=k_max)
        need = hit = expanded = total = 0
        for scores, needed in zip(scores_per_query, needed_sets):
            dec = sel.decide(scores)
            for e, n in zip(dec.expand_mask, needed):
                need += n
                hit += n and e
                expanded += e
                total += 1
        recall = hit / max(need, 1)
        row = {"tau_entry": float(tau), "recall": recall,
               "expand_rate": expanded / max(total, 1)}
        if recall >= target_recall and \
                (best is None or row["expand_rate"] < best["expand_rate"]):
            best = row
    return best or {"tau_entry": 0.5, "recall": 0.0, "expand_rate": 0.0,
                    "note": "recall target unreachable on train"}

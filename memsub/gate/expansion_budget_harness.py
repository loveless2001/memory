"""Budgeted expansion harness (GT10; spec §17.7).

Under a max_retrieved_tokens budget smaller than the demanded expansions,
grants go to the highest-scoring demands first and every ungrantable demand
is surfaced in the trace as budget_exhausted — never silently dropped.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ExpansionDemand:
    item_id: str
    score: float          # gate p(insufficient)
    token_cost: int       # raw span length


@dataclass
class ExpansionTraceEntry:
    item_id: str
    score: float
    token_cost: int
    granted: bool
    reason: str           # "granted" | "budget_exhausted"


@dataclass
class BudgetedExpansionHarness:
    max_retrieved_tokens: int
    trace: list[ExpansionTraceEntry] = field(default_factory=list)

    def resolve(self, demands: list[ExpansionDemand]) -> list[ExpansionTraceEntry]:
        """Grant demands in score order until the budget is exhausted; the
        remainder is traced as budget_exhausted."""
        remaining = self.max_retrieved_tokens
        self.trace = []
        for d in sorted(demands, key=lambda d: -d.score):
            if d.token_cost <= remaining:
                remaining -= d.token_cost
                self.trace.append(ExpansionTraceEntry(
                    d.item_id, d.score, d.token_cost, True, "granted"))
            else:
                self.trace.append(ExpansionTraceEntry(
                    d.item_id, d.score, d.token_cost, False, "budget_exhausted"))
        return self.trace

    @property
    def granted_tokens(self) -> int:
        return sum(t.token_cost for t in self.trace if t.granted)

    @property
    def exhausted_count(self) -> int:
        return sum(1 for t in self.trace if t.reason == "budget_exhausted")

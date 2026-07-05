"""Offline certification harness (M1; spec 13.4).

Characterizes a (model build, compaction policy, eviction fraction)
configuration: KL vs full-context teacher + MCQ accuracy delta on the
AGGREGATION axis; needle / lost-fact incident rate on the POINTWISE axis.
The two axes are reported SEPARATELY and never blended (spec 4.7, 13.4 —
GT4 asserts no blended metric exists on the report object).
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field

import torch

from ..runtime import CompactedPrefixCache, HFModelRuntime
from .pilot_mcq_pipeline import McqItem, eq_policy_v1


@dataclass
class AggregationAxisReport:
    """Integration-class workload: KL + answer-accuracy delta (spec 13.4)."""
    mean_kl: float
    full_context_accuracy: float
    compacted_accuracy: float
    accuracy_delta: float
    probe_count: int


@dataclass
class PointwiseAxisReport:
    """Needle-class workload: the lost-fact instrument (spec 13.4, 17.1).
    lost_fact_incident_rate counts probes over evicted spans answered wrongly
    WITHOUT an EXPAND call — the silent failure."""
    needle_probe_count: int
    needle_correct_before_eviction: int
    needle_correct_after_eviction: int
    expand_calls: int
    lost_fact_incident_rate: float


@dataclass
class CertificationReport:
    """No blended/aggregate score field exists by design (spec 4.7 corollary)."""
    certification_id: str
    model_build: str
    compaction_policy_version: str
    eviction_fraction: float
    eq_policy: str
    aggregation_axis: AggregationAxisReport
    pointwise_axis: PointwiseAxisReport
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)


BLENDED_FIELD_NAMES = {"blended", "overall", "aggregate_score", "combined",
                       "total_score", "score"}


def make_certification_id(model_build: str, policy: str, evict_fraction: float) -> str:
    return f"evfid-v1:{model_build}:{policy}:evict-{evict_fraction:.2f}"


class OfflineCertificationHarness:
    def __init__(self, runtime: HFModelRuntime):
        self.runtime = runtime

    @torch.inference_mode()
    def _mean_kl(self, full_cache: CompactedPrefixCache,
                 compact_cache: CompactedPrefixCache,
                 continuation_ids: list[int]) -> float:
        """Mean KL(full || compacted) over a continuation window."""
        logits_a = self.runtime.forward_extend(full_cache.clone_detached(), continuation_ids)
        logits_b = self.runtime.forward_extend(compact_cache.clone_detached(), continuation_ids)
        pa = torch.log_softmax(logits_a, dim=-1)
        pb = torch.log_softmax(logits_b, dim=-1)
        kl = torch.sum(pa.exp() * (pa - pb), dim=-1)
        return float(kl.mean())

    def certify(self, *, context_text: str, evict_logical_range: tuple[int, int],
                mcq_items: list[McqItem], needle_items: list[McqItem],
                continuation_text: str = " The discussion continued.",
                expand_fn=None, policy_version: str = "evict-oldest-nonsink-v1",
                ) -> CertificationReport:
        """Certify one configuration over one pilot context.

        full context (reference) vs compacted state (candidate) per spec 13.4.
        needle_items must probe facts inside the evicted span."""
        rt = self.runtime
        ids = rt.tokenizer.encode(context_text, add_special_tokens=False)
        full_cache, _ = rt.prefill(ids)
        compact_cache = full_cache.clone_detached()
        evicted = compact_cache.evict_logical_range(*evict_logical_range)
        eviction_fraction = evicted / max(len(ids), 1)

        cont_ids = rt.tokenizer.encode(continuation_text, add_special_tokens=False)
        mean_kl = self._mean_kl(full_cache, compact_cache, cont_ids)

        def run_mcqs(cache) -> float:
            if not mcq_items:
                return 0.0
            hits = sum(
                eq_policy_v1(rt.answer_letter("", it.question, it.options, cache=cache),
                             it.gold_letter)
                for it in mcq_items)
            return hits / len(mcq_items)

        acc_full, acc_compact = run_mcqs(full_cache), run_mcqs(compact_cache)

        # Pointwise axis: needle probes over the evicted span.
        before = after = expands = lost = 0
        for item in needle_items:
            if eq_policy_v1(rt.answer_letter("", item.question, item.options,
                                             cache=full_cache), item.gold_letter):
                before += 1
            expanded = expand_fn(item) if expand_fn else None
            if expanded is not None:
                expands += 1
                ok = eq_policy_v1(rt.answer_letter(expanded, item.question,
                                                   item.options, cache=compact_cache),
                                  item.gold_letter)
            else:
                ok = eq_policy_v1(rt.answer_letter("", item.question, item.options,
                                                   cache=compact_cache), item.gold_letter)
            if ok:
                after += 1
            elif expanded is None:
                lost += 1  # wrong WITHOUT an EXPAND call — the silent failure

        model_build = rt.fingerprint().model_id
        return CertificationReport(
            certification_id=make_certification_id(model_build, policy_version,
                                                    eviction_fraction),
            model_build=model_build,
            compaction_policy_version=policy_version,
            eviction_fraction=round(eviction_fraction, 4),
            eq_policy="eq_policy_v1",
            aggregation_axis=AggregationAxisReport(
                mean_kl=round(mean_kl, 6),
                full_context_accuracy=round(acc_full, 4),
                compacted_accuracy=round(acc_compact, 4),
                accuracy_delta=round(acc_compact - acc_full, 4),
                probe_count=len(mcq_items)),
            pointwise_axis=PointwiseAxisReport(
                needle_probe_count=len(needle_items),
                needle_correct_before_eviction=before,
                needle_correct_after_eviction=after,
                expand_calls=expands,
                lost_fact_incident_rate=round(lost / max(len(needle_items), 1), 4)),
        )

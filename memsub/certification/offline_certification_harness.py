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
    WITHOUT an EXPAND call — the silent failure. Denominator = ALL needle
    probes; lost_fact_rate_given_prior_correct conditions on probes the model
    answered correctly under full context (true forgetting, not never-knew)."""
    needle_probe_count: int
    needle_correct_before_eviction: int
    needle_correct_after_eviction: int
    expand_calls: int
    lost_fact_incident_rate: float
    lost_fact_rate_given_prior_correct: float = 0.0


@dataclass
class CertificationReport:
    """No blended/aggregate score field exists by design (spec 4.7 corollary).

    eval_protocol makes the numbers citable: exact item partition per axis,
    what the compacted context contained during probing, and whether EXPAND
    was enabled. probe_records (optional) carry per-needle predictions for
    manual failure audits."""
    certification_id: str
    model_build: str
    compaction_policy_version: str
    eviction_fraction: float
    eq_policy: str
    aggregation_axis: AggregationAxisReport
    pointwise_axis: PointwiseAxisReport
    eval_protocol: dict = field(default_factory=dict)
    probe_records: list[dict] = field(default_factory=list)
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
                eviction_mode: str = "contiguous_span", random_seed: int = 0,
                record_probes: bool = False,
                protocol_notes: dict | None = None,
                compaction_fn=None,
                policy_version_override: str | None = None) -> CertificationReport:
        """Certify one configuration over one pilot context.

        full context (reference) vs compacted state (candidate) per spec 13.4.
        needle_items must probe facts inside the evicted span (for
        eviction_mode="random_nonsink_matched" the same needle set is kept and
        the same NUMBER of tokens is evicted uniformly from non-sink
        positions, isolating the effect of the policy's recency structure)."""
        import random as random_mod
        rt = self.runtime
        ids = rt.tokenizer.encode(context_text, add_special_tokens=False)
        full_cache, _ = rt.prefill(ids)
        compact_cache = full_cache.clone_detached()
        if compaction_fn is not None:
            # Trained-compactor arm (M3.5): the policy replaces eviction;
            # "eviction fraction" reports the physical size reduction so
            # matched-budget rows are comparable across policies.
            compact_cache = compaction_fn(compact_cache)
            evicted = full_cache.physical_length - compact_cache.physical_length
        elif eviction_mode == "contiguous_span":
            evicted = compact_cache.evict_logical_range(*evict_logical_range)
        elif eviction_mode == "random_nonsink_matched":
            span = evict_logical_range[1] - evict_logical_range[0]
            rng = random_mod.Random(random_seed)
            candidates = [p for p in compact_cache.logical_positions
                          if p >= compact_cache.sink_token_count]
            evicted = compact_cache.evict_logical_positions(
                rng.sample(candidates, min(span, len(candidates))))
        else:
            raise ValueError(f"unknown eviction_mode {eviction_mode!r}")
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
        before = after = expands = lost = lost_prior_correct = 0
        probe_records: list[dict] = []
        for item in needle_items:
            pred_full = rt.answer_letter("", item.question, item.options,
                                         cache=full_cache)
            was_correct = eq_policy_v1(pred_full, item.gold_letter)
            before += was_correct
            expanded = expand_fn(item) if expand_fn else None
            pred_compact = rt.answer_letter(expanded or "", item.question,
                                            item.options, cache=compact_cache)
            expands += expanded is not None
            ok = eq_policy_v1(pred_compact, item.gold_letter)
            if ok:
                after += 1
            elif expanded is None:
                lost += 1  # wrong WITHOUT an EXPAND call — the silent failure
                lost_prior_correct += was_correct
            if record_probes:
                probe_records.append({
                    "item_id": item.item_id, "question": item.question,
                    "options": item.options, "gold": item.gold_letter,
                    "pred_full_context": pred_full,
                    "pred_compacted": pred_compact,
                    "expanded": expanded is not None})

        if policy_version_override:
            policy_version = policy_version_override
        eval_protocol = {
            # pointwise denominator: caller-selected needle items — probes
            # whose SOURCE CHUNK lies in the evicted window; aggregation
            # denominator: the disjoint mcq_items set (see caller notes).
            "pointwise_denominator": "needle_items (source chunk in evicted window)",
            "aggregation_denominator": "mcq_items (disjoint from needles)",
            "axes_share_items": False,
            "eviction_mode": ("trained_compactor" if compaction_fn is not None
                              else eviction_mode),
            "compacted_context_contents": "surviving KV only — no summary text "
                                          "or auxiliary representation injected",
            "expand_enabled": expand_fn is not None,
            "kl_window_tokens": len(cont_ids),
            "scoring": "argmax over option-letter logits (eq_policy_v1); "
                       "greedy, no sampling",
            **(protocol_notes or {}),
        }
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
                lost_fact_incident_rate=round(lost / max(len(needle_items), 1), 4),
                lost_fact_rate_given_prior_correct=round(
                    lost_prior_correct / max(before, 1), 4)),
            eval_protocol=eval_protocol,
            probe_records=probe_records,
        )

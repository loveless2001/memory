"""GT4 — Eviction changes behavior, certification catches it (M1).

Evict a span containing a planted fact; the needle probe over that span must
flip from correct to incorrect (or to EXPAND) — proving the lost-fact
instrument detects real loss. The aggregation-axis and pointwise-axis scores
are reported SEPARATELY (spec 13.4, 4.7): the report object must contain no
blended metric.

The semantic flip requires real model weights -> reference config (Modal).
The report-structure assertions run everywhere.
"""

import dataclasses

import pytest

from conftest import REFERENCE

from memsub.certification import (
    CertificationReport,
    McqItem,
    OfflineCertificationHarness,
)
from memsub.certification.offline_certification_harness import BLENDED_FIELD_NAMES

FILLER = ("The quarterly report covered logistics, staffing and budget. " * 30)
FACT = "The security code for vault B is 88231. "
NEEDLE = McqItem(
    item_id="needle-1", doc_id="doc-1", chunk_token_start=0, chunk_token_end=0,
    question="What is the security code for vault B?",
    options=["55402", "88231", "10077", "93314"], gold_letter="B")
MCQ = McqItem(
    item_id="agg-1", doc_id="doc-1", chunk_token_start=0, chunk_token_end=0,
    question="What did the quarterly report cover?",
    options=["logistics, staffing and budget", "sales only",
             "engineering hiring", "legal disputes"], gold_letter="A")


def _run_certification(runtime, expand_fn=None):
    harness = OfflineCertificationHarness(runtime)
    tokenizer = runtime.tokenizer
    prefix_ids = tokenizer.encode(FILLER, add_special_tokens=False)
    fact_ids = tokenizer.encode(FACT, add_special_tokens=False)
    context = FILLER + FACT + FILLER
    evict_range = (len(prefix_ids), len(prefix_ids) + len(fact_ids))
    return harness.certify(
        context_text=context, evict_logical_range=evict_range,
        mcq_items=[MCQ], needle_items=[NEEDLE], expand_fn=expand_fn)


@pytest.mark.golden
def test_gt4_axes_reported_separately_no_blended_metric(runtime):
    report = _run_certification(runtime)
    assert isinstance(report, CertificationReport)

    # Two axes exist as separate structured objects.
    assert report.aggregation_axis.probe_count == 1
    assert report.pointwise_axis.needle_probe_count == 1

    # No blended metric exists anywhere in the report object (spec 4.7).
    def field_names(obj):
        names = set()
        for f in dataclasses.fields(obj):
            names.add(f.name)
            value = getattr(obj, f.name)
            if dataclasses.is_dataclass(value):
                names |= field_names(value)
        return names

    assert field_names(report) & BLENDED_FIELD_NAMES == set()
    # And the two axis reports share no metric fields that could be summed
    # into one number silently.
    agg = {f.name for f in dataclasses.fields(report.aggregation_axis)}
    point = {f.name for f in dataclasses.fields(report.pointwise_axis)}
    assert agg & point == set()

    assert report.certification_id.startswith("evfid-v1:")
    assert report.eq_policy == "eq_policy_v1"
    assert 0 < report.eviction_fraction < 1

    # Eval protocol makes denominators citable (per-axis partition, context
    # contents during probing, EXPAND state).
    proto = report.eval_protocol
    assert proto["axes_share_items"] is False
    assert proto["expand_enabled"] is False
    assert "surviving KV only" in proto["compacted_context_contents"]
    assert proto["eviction_mode"] == "contiguous_span"


@pytest.mark.golden
@pytest.mark.reference
@pytest.mark.skipif(not REFERENCE, reason="needle flip needs real model weights")
def test_gt4_needle_probe_flips_after_eviction(runtime):
    report = _run_certification(runtime)
    point = report.pointwise_axis

    # The planted fact was answerable before eviction...
    assert point.needle_correct_before_eviction == 1
    # ...and flips to incorrect (or EXPAND) after the span is evicted.
    assert point.needle_correct_after_eviction == 0 or point.expand_calls > 0
    assert point.lost_fact_incident_rate == 1.0
    # Eviction is visible on the aggregation axis as nonzero KL.
    assert report.aggregation_axis.mean_kl > 0


@pytest.mark.golden
@pytest.mark.reference
@pytest.mark.skipif(not REFERENCE, reason="needs real model weights")
def test_gt4_expand_recovers_the_needle(runtime):
    report = _run_certification(runtime, expand_fn=lambda item: FACT)
    point = report.pointwise_axis
    assert point.expand_calls == 1
    assert point.needle_correct_after_eviction == 1
    assert point.lost_fact_incident_rate == 0.0

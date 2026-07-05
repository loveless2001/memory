"""M1 smoke: sink-pinned compaction/eviction + offline certification harness
on a toy thread; prints the two-axis report (never blended).

Local: python examples/m1-compaction-certification-smoke.py
Reference: MEMSUB_REFERENCE=1 (real needle flip expected).
"""

import json
import sys
import tempfile

sys.path.insert(0, ".")

from memsub.certification import McqItem, OfflineCertificationHarness
from memsub.errors import SinkEvictionError
from memsub.reference_config import build_runtime, build_substrate, is_reference


def main() -> int:
    with tempfile.TemporaryDirectory() as root:
        sub = build_substrate(root)
        thread_id = sub.new_thread()
        sub.append_turns(thread_id, [
            {"role": "user", "text": "opening pleasantries " * 20},
            {"role": "user", "text": "the migration window starts at 02:00 UTC "
                                     "on Saturday and rollback owner is Dana. " * 4},
            {"role": "assistant", "text": "confirmed, runbook updated with owners. " * 8},
        ])
        cache = sub.prefill_thread(thread_id)

        # Sink invariant is enforced in the compactor path.
        first = sub.archive.spans_for_thread(thread_id)[0]
        try:
            sub.compactor.compact_span(thread_id, cache, first)
            raise AssertionError("sink-covering span must not compact")
        except SinkEvictionError:
            print("sink pinning enforced: first span refused")

        results = sub.compact_under_pressure(thread_id, cache, 96)
        print(f"compacted {len(results)} blocks, cache offset={cache.logical_offset}")

    runtime = sub.runtime if not is_reference() else build_runtime()
    harness = OfflineCertificationHarness(runtime)
    filler = "The weekly sync covered hiring, roadmap and platform costs. " * 20
    fact = "The incident bridge passcode is 55193. "
    prefix = len(runtime.tokenizer.encode(filler, add_special_tokens=False))
    flen = len(runtime.tokenizer.encode(fact, add_special_tokens=False))
    report = harness.certify(
        context_text=filler + fact + filler,
        evict_logical_range=(prefix, prefix + flen),
        mcq_items=[McqItem("agg", "d", 0, 0, "What did the weekly sync cover?",
                           ["hiring, roadmap and platform costs", "a product launch",
                            "legal review", "office relocation"], "A")],
        needle_items=[McqItem("needle", "d", 0, 0,
                              "What is the incident bridge passcode?",
                              ["10021", "77840", "55193", "34019"], "C")])
    print(json.dumps(report.to_dict(), indent=1))
    assert not hasattr(report, "blended_score")
    if is_reference():
        assert report.pointwise_axis.needle_correct_before_eviction == 1
        assert report.pointwise_axis.lost_fact_incident_rate > 0
        print("M1 smoke OK: eviction flipped the needle; instrument caught it")
    else:
        print("M1 smoke OK (tiny config: structural checks only)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

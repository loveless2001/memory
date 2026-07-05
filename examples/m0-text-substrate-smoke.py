"""M0 smoke: raw archive -> segmenter -> summaries -> shadows -> gated EXPAND
on a toy thread (BUILD.md definition of done).

Local: python examples/m0-text-substrate-smoke.py   (tiny config)
Reference: MEMSUB_REFERENCE=1 on a GPU box / Modal.
"""

import sys
import tempfile

sys.path.insert(0, ".")

from memsub.reference_config import build_substrate


def main() -> int:
    with tempfile.TemporaryDirectory() as root:
        sub = build_substrate(root)
        thread_id = sub.new_thread()
        spans = sub.append_turns(thread_id, [
            {"role": "user", "text": "Hello! Let's plan the offsite. " * 4},
            {"role": "user", "text": "Important: the venue booking reference is QX-4417 "
                                     "and the budget cap is 12000 euros. " * 3},
            {"role": "assistant", "text": "Noted. I will arrange catering and transport "
                                          "for the whole team accordingly. " * 3},
            {"role": "user", "text": "Also remind me later who owns the audio setup. " * 3},
        ])
        print(f"archived {len(spans)} spans; next_pos="
              f"{sub.index.get_thread(thread_id)['next_logical_position']}")

        cache = sub.prefill_thread(thread_id)
        results = sub.compact_under_pressure(thread_id, cache, target_evict_tokens=96)
        assert results, "expected at least one compacted block"
        for res in results:
            block = res.block
            summary = sub.blobs.get_text(block.primary.storage_uri)
            print(f"block {block.block_id}: kind={block.semantic_kind} "
                  f"shadow={block.embedding_shadow.embedding_policy_version} "
                  f"summary={summary[:80]!r}")

        expansions = sub.expand(thread_id, "what was the venue booking reference?")
        assert expansions, "runtime gate should EXPAND for the needle query"
        print(f"EXPAND fired: block={expansions[0].block_id} "
              f"score={expansions[0].score:.3f}")
        assert "QX-4417" in expansions[0].injection_text
        print("M0 smoke OK: exact needle recovered through RETRIEVED_EXACT")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

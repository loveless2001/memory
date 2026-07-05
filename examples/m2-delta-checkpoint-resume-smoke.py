"""M2 smoke: delta checkpoints on disk, mmap hydration, fingerprint-gated
hydrate-or-fallback resume on a toy thread.

Local: python examples/m2-delta-checkpoint-resume-smoke.py
Reference: MEMSUB_REFERENCE=1.
"""

import json
import sys
import tempfile

sys.path.insert(0, ".")

from memsub.reference_config import build_substrate


def main() -> int:
    with tempfile.TemporaryDirectory() as root:
        sub = build_substrate(root)
        thread_id = sub.new_thread()
        sub.append_turns(thread_id, [
            {"role": "user", "text": "kickoff notes " * 40},
            {"role": "assistant", "text": "acknowledged with details " * 40},
            {"role": "user", "text": "follow-up questions " * 40},
        ])
        cache = sub.prefill_thread(thread_id)
        sub.compact_under_pressure(thread_id, cache, 64)

        ckpt1 = sub.checkpoint(thread_id, cache)
        pages1 = {p["storage_uri"] for p in json.loads(
            sub.blobs.get(ckpt1.kv_page_table_uri))["pages"]}

        extra = sub.runtime.tokenizer.encode(" appended follow-up",
                                             add_special_tokens=False)
        sub.runtime.forward_extend(cache, extra)
        ckpt2 = sub.checkpoint(thread_id, cache)
        pages2 = {p["storage_uri"] for p in json.loads(
            sub.blobs.get(ckpt2.kv_page_table_uri))["pages"]}
        print(f"delta checkpoint: {len(pages1 & pages2)}/{len(pages2)} pages reused, "
              f"parent={ckpt2.parent_checkpoint_id == ckpt1.checkpoint_id}")

        outcome = sub.resume(thread_id)
        assert outcome.path_taken == "hydrate", outcome
        assert outcome.cache.physical_length == cache.physical_length
        assert outcome.cache.next_logical_position == cache.next_logical_position
        print(f"hydrate OK: K={outcome.cache.physical_length} "
              f"offset={outcome.cache.logical_offset} "
              f"sinks={ckpt2.sink_tokens_retained}")

        # Tamper with one fingerprint field -> resume must fall back.
        row = sub.index.get_checkpoint_row(ckpt2.checkpoint_id)
        body = json.loads(row["body_json"])
        body["compatibility_fingerprint"]["quantization"] = "int8"
        sub.index.conn.execute(
            "UPDATE checkpoints SET body_json = ? WHERE checkpoint_id = ?",
            (json.dumps(body), ckpt2.checkpoint_id))
        sub.index.conn.commit()
        # also invalidate ckpt1 so the resumer cannot pick the older good one
        sub.index.invalidate_artifact(ckpt1.checkpoint_id)

        outcome = sub.resume(thread_id, ckpt2.checkpoint_id)
        assert outcome.path_taken.startswith("fallback"), outcome
        print(f"fingerprint gate OK: fell back via {outcome.path_taken} "
              f"({outcome.reason.split(':')[0]}), re-prefilled "
              f"{outcome.prefill_token_count} tokens")
        print("M2 smoke OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

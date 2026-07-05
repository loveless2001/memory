"""Thin CLI over SubstrateFacade (BUILD.md 1: library with a thin CLI).

Model-free commands (inspect, redact) work anywhere; model-bound commands
(append/compact/resume/smoke) load the configured model — on the reference
config that requires a 24GB-class GPU (use Modal, see modal-runners/).
"""

from __future__ import annotations

import argparse
import json
import os
import sys

REFERENCE_MODEL = "Qwen/Qwen3-4B-Instruct-2507"


def _open_index(root: str):
    from .store import SqliteIndex
    return SqliteIndex(os.path.join(root, "index.sqlite3"))


def cmd_inspect(args) -> int:
    index = _open_index(args.root)
    thread = index.get_thread(args.thread_id)
    if thread is None:
        print(f"unknown thread {args.thread_id}", file=sys.stderr)
        return 1
    out = {
        "thread_id": args.thread_id,
        "next_logical_position": thread["next_logical_position"],
        "redaction_generation": thread["redaction_generation"],
        "spans": [dict(r) for r in index.spans_for_thread(args.thread_id)],
        "blocks": [r["block_id"] for r in index.blocks_for_thread(args.thread_id)],
        "checkpoints": [
            {"checkpoint_id": r["checkpoint_id"], "invalidated": bool(r["invalidated"])}
            for r in index.checkpoints_for_thread(args.thread_id)],
    }
    print(json.dumps(out, indent=1, default=str))
    return 0


def cmd_redact(args) -> int:
    from .redaction_graph_invalidator import RedactionGraphInvalidator
    report = RedactionGraphInvalidator(_open_index(args.root)).redact_span(args.span_id)
    print(json.dumps(report.__dict__, indent=1))
    return 0


def cmd_fingerprint(args) -> int:
    from .runtime import HFModelRuntime
    runtime = HFModelRuntime.load(args.model, device=args.device, dtype=args.dtype)
    print(runtime.fingerprint().canonical_json())
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="memsub")
    parser.add_argument("--root", default=".memsub-store")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("inspect", help="dump thread metadata")
    p.add_argument("thread_id")
    p.set_defaults(fn=cmd_inspect)

    p = sub.add_parser("redact", help="redact a span; invalidates derived artifacts")
    p.add_argument("span_id")
    p.set_defaults(fn=cmd_redact)

    p = sub.add_parser("fingerprint", help="print the live compatibility_fingerprint")
    p.add_argument("--model", default=REFERENCE_MODEL)
    p.add_argument("--device", default="cpu")
    p.add_argument("--dtype", default="bfloat16")
    p.set_defaults(fn=cmd_fingerprint)

    args = parser.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())

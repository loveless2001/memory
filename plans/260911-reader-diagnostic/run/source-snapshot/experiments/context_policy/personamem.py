"""PersonaMem-v2 intake: isolate reader text from generation/scoring metadata.

This is an admission audit, not approval to train on the candidate corpus.
Only the pinned text-training release is used. System messages in the raw
history expose the synthetic persona and must never enter reader input.
"""

import ast
import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path, PurePosixPath


REVISION = "ed956dea41521fc4499acbc63f966e0fd3c053ba"
TRAIN_SHA256 = "62abb042f529818a22be4ced84b683364f000af68608008c20186527740276d6"


def sha256(value):
    return hashlib.sha256(value).hexdigest()


def normalized(text):
    return " ".join(text.split())


def parse_structured(value):
    """The release mixes JSON with Python-literal serialization; never eval."""
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return ast.literal_eval(value)


def history_path(value):
    path = PurePosixPath(value)
    if (path.is_absolute() or ".." in path.parts
            or re.fullmatch(r"data/chat_history_32k/chat_history_[0-9_]+_persona[0-9]+\.json", value) is None):
        raise ValueError("expected a repository-relative text 32k history path")
    return Path(*path.parts)


def reader_history(payload):
    """Whitelist role/content; remove profile-bearing system turns and metadata."""
    raw = payload["chat_history"]
    if not isinstance(raw, list) or not raw:
        raise ValueError("empty or malformed history")
    out = []
    for message in raw:
        role, content = message["role"], message["content"]
        if role not in ("system", "user", "assistant") or not isinstance(content, str):
            raise ValueError("unexpected history role or non-text content")
        if role != "system":
            out.append({"role": role, "content": content})
    if not out or out[0]["role"] != "user":
        raise ValueError("reader history must begin with a user turn")
    return out


def reader_query(row):
    message = parse_structured(row["user_query"])
    if (not isinstance(message, dict) or message.get("role") != "user"
            or not isinstance(message.get("content"), str) or not message["content"].strip()):
        raise ValueError("expected a nonempty user query")
    return {"role": "user", "content": message["content"]}


def reader_record(row, payload):
    # Do not copy/blacklist row keys: new private fields must remain private too.
    return {"history": reader_history(payload), "query": reader_query(row)}


def match_snippet(row, history):
    snippet = parse_structured(row["related_conversation_snippet"])
    if not isinstance(snippet, list) or not snippet:
        raise ValueError("missing supporting snippet")
    def key(message):
        if message["role"] not in ("user", "assistant") or not isinstance(message["content"], str):
            raise ValueError("invalid supporting snippet")
        return message["role"], normalized(message["content"])
    needle, haystack = list(map(key, snippet)), list(map(key, history))
    positions = [i for i in range(len(haystack)-len(needle)+1)
                 if haystack[i:i+len(needle)] == needle]
    # Missing full-span matches remain failures; do not silently fuzzy-match.
    return {"contiguous_starts": positions, "snippet_turns": len(snippet),
            "matched_turn_indices": [[i for i, item in enumerate(haystack) if item == target]
                                     for target in needle]}


def load_training(root):
    path = Path(root) / "benchmark/text/train.csv"
    if sha256(path.read_bytes()) != TRAIN_SHA256:
        raise ValueError("training CSV differs from the pinned audited source")
    with path.open(newline="") as source:
        rows = list(csv.DictReader(source))
    paths_by_persona = {}
    for row in rows:
        pid = row["persona_id"]
        if not pid.isdecimal() or not 0 <= int(pid) < 1000:
            raise ValueError("invalid persona ID")
        path = history_path(row["chat_history_32k_link"])
        if not path.name.endswith(f"_persona{pid}.json"):
            raise ValueError("history filename and persona ID disagree")
        paths_by_persona.setdefault(pid, set()).add(str(path))
    if any(len(paths) != 1 for paths in paths_by_persona.values()):
        raise ValueError("persona has inconsistent history versions")
    return rows


def persona_order(rows):
    return sorted({row["persona_id"] for row in rows},
                  key=lambda pid: sha256(("context-policy-v2-persona-audit-0:"+pid).encode()))


def select_audit(rows):
    """Predeclared first ten training personas, five hash-selected queries each."""
    selected = []
    for pid in persona_order(rows)[:10]:
        candidates = [(i, row) for i, row in enumerate(rows) if row["persona_id"] == pid]
        candidates.sort(key=lambda item: sha256(("context-policy-v2-row-audit-0:"+str(item[0])).encode()))
        if len(candidates) < 5:
            raise ValueError("audit persona lacks five questions")
        selected.extend({"row_index": i, **row} for i, row in candidates[:5])
    return selected


def audit_structure(root):
    root = Path(root)
    rows = load_training(root)
    selected = select_audit(rows)
    histories, raw_histories, ownership = {}, {}, {}
    for row in selected:
        pid = row["persona_id"]
        if pid in histories:
            continue
        payload = json.loads((root / history_path(row["chat_history_32k_link"])).read_text())
        if str(payload["metadata"]["persona_id"]) != pid:
            raise ValueError("history belongs to a different persona")
        raw_histories[pid], histories[pid] = payload, reader_history(payload)
        for turn in histories[pid]:
            digest = sha256(json.dumps(turn, sort_keys=True, ensure_ascii=False).encode())
            ownership.setdefault(digest, set()).add(pid)
    cases = []
    for row in selected:
        history = histories[row["persona_id"]]
        query = reader_query(row)["content"]
        match = match_snippet(row, history)
        cases.append({"row_index": row["row_index"], "persona_id": row["persona_id"], **match,
                      "query_already_in_history": any(normalized(query) == normalized(m["content"]) for m in history)})
    ordered = persona_order(rows)
    split = {"train": ordered[:280], "validation": ordered[280:340],
             "internal_test": ordered[340:400], "unused": ordered[400:]}
    return {"status": "candidate_structure_only_semantic_admission_pending", "revision": REVISION,
            "train_sha256": TRAIN_SHA256, "training_rows": len(rows), "training_personas": len(ordered),
            "queries_per_persona": dict(sorted(Counter(Counter(r["persona_id"] for r in rows).values()).items())),
            "candidate_persona_split": split, "split_status": "prospective_not_trained_or_test_scored",
            "audit_questions": len(cases), "audit_personas": len(histories),
            "exact_snippet_matches": sum(bool(c["contiguous_starts"]) for c in cases),
            "query_collisions": sum(c["query_already_in_history"] for c in cases),
            "system_messages_removed": sum(sum(m["role"] == "system" for m in x["chat_history"]) for x in raw_histories.values()),
            "shared_exact_turns_across_audited_personas": sum(len(v) > 1 for v in ownership.values()),
            "shared_turns": [{"sha256": k, "personas": sorted(v)} for k, v in ownership.items() if len(v) > 1],
            "all_400_history_overlap_audited": False,
            "history_turn_counts": {pid: len(h) for pid, h in histories.items()}, "cases": cases}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit_structure(args.root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2)+"\n")
    print(json.dumps({k: result[k] for k in ("training_rows", "training_personas", "audit_questions", "exact_snippet_matches", "system_messages_removed", "query_collisions", "shared_exact_turns_across_audited_personas")}))

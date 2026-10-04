"""Source-bound reference repair; never infer action labels from reference text.

Authoring consumes the same sanitized history/query that a reader may access.
The old answer, persona profile, preference, update and ownership labels are
not inputs. Semantic review is still required after these structural checks.
"""

import json
import math
import re
from collections import Counter
from pathlib import Path

from .personamem import normalized, reader_history, sha256


def canonical(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))+"\n").encode()


def text_terms(text):
    return re.findall(r"[a-z0-9]+", text.lower())


class TurnSearch:
    """Deterministic lexical aid for annotation, not an oracle evidence pack."""

    def __init__(self, history):
        self.history = history
        self.counts = [Counter(text_terms(m["content"])) for m in history]
        self.lengths = [sum(c.values()) for c in self.counts]
        self.mean_length = sum(self.lengths)/max(1, len(self.lengths))
        self.df = Counter(term for counts in self.counts for term in counts)

    def search(self, query, limit=8):
        stop = set("a an the and or to of in on for with by is are be I you my your me some what how can could would should do does it that this as at from".lower().split())
        terms = sorted(set(text_terms(query))-stop)
        scores = []
        for i, counts in enumerate(self.counts):
            score = 0.0
            for term in terms:
                tf = counts[term]
                idf = math.log(1+(len(self.history)-self.df[term]+0.5)/(self.df[term]+0.5))
                score += idf*tf*2.5/(tf+1.5*(0.25+0.75*self.lengths[i]/max(self.mean_length, 1)))
            scores.append((i, score))
        return [i for i, score in sorted(scores, key=lambda item: (-item[1], item[0]))[:limit] if score > 0]


def authoring_record(root, selected):
    if set(selected) != {"row_index", "persona_id", "history_path", "query"}:
        raise ValueError("authoring selection contains unexpected fields")
    from .personamem import history_path
    source = Path(root)/history_path(selected["history_path"])
    payload = json.loads(source.read_text())
    if str(payload["metadata"]["persona_id"]) != selected["persona_id"]:
        raise ValueError("history persona mismatch")
    history = reader_history(payload)
    return {"id": f"personamem-train-row-{selected['row_index']}",
            "persona_id": selected["persona_id"], "history_path": selected["history_path"],
            "source_sha256": sha256(source.read_bytes()), "visible_history_sha256": sha256(canonical(history)),
            "query_sha256": sha256(canonical(selected["query"])),
            "history": history, "query": dict(selected["query"])}


def evidence(history, turn, quote):
    """Return exact, role-bearing coordinates; never approximate a citation."""
    if type(turn) is not int or not 0 <= turn < len(history) or not isinstance(quote, str) or not quote:
        raise ValueError("invalid evidence coordinates")
    content = history[turn]["content"]
    if content.count(quote) != 1:
        raise ValueError("evidence quote must occur exactly once within its turn")
    start = content.index(quote)
    return {"turn": turn, "role": history[turn]["role"], "start": start,
            "end": start+len(quote), "text_sha256": sha256(quote.encode())}


def validate_reference(record, reference):
    required = {"id", "source_sha256", "visible_history_sha256", "query_sha256", "answer",
                "personal_claims", "constraints", "mode", "rationale", "author", "semantic_review"}
    if set(reference) != required:
        raise ValueError("unexpected or missing repaired-reference fields")
    for key in ("id", "source_sha256", "visible_history_sha256", "query_sha256"):
        if reference[key] != record[key]:
            raise ValueError(f"reference source binding mismatch: {key}")
    if sha256(canonical(record["history"])) != record["visible_history_sha256"]:
        raise ValueError("visible history changed after binding")
    if sha256(canonical(record["query"])) != record["query_sha256"]:
        raise ValueError("query changed after binding")
    if reference["mode"] not in ("personalized", "general", "clarify", "abstain"):
        raise ValueError("unknown answer mode")
    if not isinstance(reference["answer"], str) or not reference["answer"].strip():
        raise ValueError("empty repaired answer")
    if reference["mode"] == "personalized" and not reference["personal_claims"]:
        raise ValueError("personalized answer needs supported personal claims")
    for claim in reference["personal_claims"]:
        if set(claim) != {"claim", "evidence", "ownership", "current_status"} or not claim["evidence"]:
            raise ValueError("personal claim lacks evidence")
        if claim["ownership"] not in ("user", "named_other", "quoted_text_only"):
            raise ValueError("explicit ownership required")
        if claim["current_status"] not in ("current", "uncertain", "withdrawn"):
            raise ValueError("explicit current status required")
        if claim["current_status"] == "withdrawn":
            raise ValueError("withdrawn details belong in constraints, not answer claims")
        if not any(e["role"] == "user" for e in claim["evidence"]):
            raise ValueError("assistant assertion alone cannot establish a personal fact")
    for constraint in reference["constraints"]:
        if set(constraint) != {"rule", "evidence", "kind"}:
            raise ValueError("invalid constraint")
        if constraint["kind"] not in ("withdrawal", "ownership", "uncertainty", "task_scope"):
            raise ValueError("unknown constraint kind")
        if constraint["kind"] == "withdrawal" and not constraint["evidence"]:
            raise ValueError("withdrawal requires a source turn")
    for item in reference["personal_claims"]+reference["constraints"]:
        for span in item["evidence"]:
            if set(span) != {"turn", "role", "start", "end", "text_sha256"}:
                raise ValueError("invalid span schema")
            turn = span["turn"]
            if type(turn) is not int or not 0 <= turn < len(record["history"]):
                raise ValueError("evidence turn out of range")
            message = record["history"][turn]
            start, end = span["start"], span["end"]
            if type(start) is not int or type(end) is not int or not 0 <= start < end <= len(message["content"]):
                raise ValueError("evidence span out of range")
            if message["role"] != span["role"] or sha256(message["content"][start:end].encode()) != span["text_sha256"]:
                raise ValueError("evidence role or text changed")
            if item.get("kind") == "withdrawal" and message["role"] != "user":
                raise ValueError("assistant cannot withdraw a user's preference")
    # This validation certifies coordinates and separation, not semantic entailment.
    return True


def draft_reference(record, answer, mode, claims=(), constraints=(), rationale=""):
    result = {key: record[key] for key in ("id", "source_sha256", "visible_history_sha256", "query_sha256")}
    result.update(answer=answer, mode=mode, personal_claims=list(claims), constraints=list(constraints),
                  rationale=rationale, author="Codex, source-only authoring",
                  semantic_review={"status": "pending", "independent_human_review": False})
    validate_reference(record, result)
    return result


def review_packet(record, limit=8):
    history = record["history"]
    hits = TurnSearch(history).search(record["query"]["content"], limit)
    indices = sorted(set(i for hit in hits for i in (max(0, hit-1), hit, min(len(history)-1, hit+1))))
    withdrawals = [i for i, m in enumerate(history) if m["role"] == "user"
                   and re.search(r"^(please\s+)?forget\b|^please do not remember\b", m["content"], re.I)]
    return {"id": record["id"], "query": record["query"],
            "lexical_turns": [{"turn": i, **history[i]} for i in indices],
            "possible_withdrawals": [{"turn": i, **history[i]} for i in withdrawals],
            "scope": "search aid only; inspect full history where ownership or chronology is unclear"}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--selection", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    records = [authoring_record(args.root, r) for r in json.loads(args.selection.read_text())]
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output/"records.jsonl").write_bytes(b"".join(canonical(r) for r in records))
    (args.output/"review-packets.jsonl").write_bytes(b"".join(canonical(review_packet(r)) for r in records))
    (args.output/"status.json").write_bytes(canonical({"status": "reference_authoring_pending", "training_allowed": False,
                                                      "records": len(records), "source_only": True}))
    print(json.dumps({"records": len(records), "status": "reference_authoring_pending"}))

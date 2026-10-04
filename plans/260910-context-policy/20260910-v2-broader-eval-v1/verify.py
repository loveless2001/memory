"""Verify candidate provenance and optional external reference review; no inference."""

import argparse
import datetime
import json
import re
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
from experiments.context_policy.personamem import sha256
from experiments.context_policy.preflight import canonical as acquisition_canonical
from experiments.context_policy.relabel import canonical, validate_reference
from experiments.context_policy.repair_pilot import validate_bundle

PLAN = HERE.parent / "20260910-v2-broader-eval-plan"
DATA = HERE.parent / "20260910-v2-broader-eval-data"


def read(path):
    return json.loads(path.read_text())


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def require(condition, description):
    if not condition:
        raise ValueError(description)


def span_valid(span, history):
    require(set(span) == {"turn", "role", "start", "end", "text_sha256"}, "review evidence schema")
    turn = span["turn"]
    require(type(turn) is int and 0 <= turn < len(history), "review evidence turn")
    msg = history[turn]
    start, end = span["start"], span["end"]
    require(type(start) is int and type(end) is int and 0 <= start < end <= len(msg["content"]), "review evidence range")
    require(span["role"] == msg["role"] and sha256(msg["content"][start:end].encode()) == span["text_sha256"], "review evidence binding")


def validate_review(path, freeze_hash, records, families):
    review = read(path)
    require(set(review) == {"reviewer", "created_at", "candidate_freeze_sha256", "full_base_histories_read", "cases"}, "review top-level schema")
    require(bool(review["reviewer"].strip()) and bool(review["created_at"].strip()), "review metadata required")
    require(review["candidate_freeze_sha256"] == freeze_hash, "review is for another freeze")
    datetime.datetime.fromisoformat(review["created_at"].replace("Z", "+00:00"))
    expected_families = {f["family_id"] for f in families}
    require(len(review["full_base_histories_read"]) == 20 and set(review["full_base_histories_read"]) == expected_families,
            "review must attest to reading all 20 full original histories")
    source = {r["id"]: r for r in records}
    require(len(review["cases"]) == 120 and {r["id"] for r in review["cases"]} == set(source), "review case coverage")
    statuses = Counter()
    for row in review["cases"]:
        require(set(row) == {"id", "source_sha256", "visible_history_sha256", "query_sha256", "status", "rationale", "supporting_evidence", "contradicting_evidence", "suggested_answer"}, "review case schema")
        record = source[row["id"]]
        for key in ("source_sha256", "visible_history_sha256", "query_sha256"):
            require(row[key] == record[key], "review source binding")
        require(row["status"] in {"accept", "reject", "ambiguous", "insufficient_source"}, "review status is incomplete or invalid")
        require(isinstance(row["rationale"], str) and bool(row["rationale"].strip()), "case-specific rationale required")
        require(isinstance(row["supporting_evidence"], list) and isinstance(row["contradicting_evidence"], list), "review evidence lists")
        if row["status"] == "accept":
            require(bool(row["supporting_evidence"]), "accepted reference needs evidence")
            require(row["suggested_answer"] is None, "a reference requiring correction should not be accepted as-is")
        if row["suggested_answer"] is not None:
            require(isinstance(row["suggested_answer"], str) and 0 < len(row["suggested_answer"].split()) <= 90, "suggested answer length")
        for span in row["supporting_evidence"] + row["contradicting_evidence"]:
            span_valid(span, record["history"])
        statuses[row["status"]] += 1
    return {"case_counts": dict(statuses), "all_proposed_references_accepted": statuses["accept"] == 120,
            "semantic_truth_certified_by_validator": False, "training_authorized": False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--freeze", action="store_true", help="Write the initial manifest only after CPU checks pass")
    parser.add_argument("--review", type=Path, help="Validate an independent review without modifying references")
    args = parser.parse_args()
    start = read(PLAN / "authoring-start.json")
    for path, expected in start["protected_files"].items():
        require(sha256((ROOT / path).read_bytes()) == expected, "prior artifact changed: " + path)
    records = rows(HERE / "records.jsonl")
    references = rows(HERE / "references.jsonl")
    cases = rows(HERE / "packet/cases.jsonl")
    families = read(HERE / "authoring/family-map.json")
    variants = read(HERE / "packet/variants.json")
    bundle = read(HERE / "reader-bundle.json")
    coverage = read(HERE / "coverage.json")
    validate_bundle(bundle)
    selection = read(PLAN / "selection.json")
    acquired = read(DATA / "histories.json")
    require([f["persona_id"] for f in families] == [r["persona_id"] for r in selection["selected"]], "family selection/order changed")
    require(len(records) == len(references) == len(cases) == len(bundle["questions"]) == 120, "120 case coverage")
    require(len(bundle["histories"]) == 60 and len(variants) == 40 and len(families) == 20, "history/variant coverage")
    ids = [r["id"] for r in records]
    require(len(set(ids)) == 120, "duplicate cases")
    require(ids == [r["id"] for r in references] == [r["id"] for r in cases] == [q["id"] for q in bundle["questions"]], "case ordering")
    require(coverage["gaps"] == [] and coverage["candidate_cases"] == 120, "coverage metadata")
    kinds = Counter(c["kind"] for f in families for c in f["cases"])
    require(dict(kinds) == coverage["counts"] == {"historical_recall": 40, "withdrawal": 20, "ownership_control": 20, "synthetic_later_different": 20, "synthetic_later_same": 20}, "case kind coverage")
    record_map = {r["id"]: r for r in records}
    source_hashes = {}
    for family in families:
        base = acquired[family["persona_id"]]
        hid = family["base_history_id"]
        require(bundle["histories"][hid] == base, "base content changed")
        require(sha256(canonical(base)) == family["base_visible_history_sha256"], "base Unicode serialization binding")
        require(sha256(acquisition_canonical(base)) == family["acquisition_visible_history_sha256"], "base acquisition serialization binding")
        require(sha256((ROOT / family["source_path"]).read_bytes()) == family["source_sha256"], "raw source changed")
        source_hashes[hid] = family["source_sha256"]
        expected_text = f"# {family['family_id']}: complete original sanitized history\n\nTurn numbers are zero-based.\n\n" + "\n\n".join(f"[T{i} {m['role']}]\n{m['content']}" for i, m in enumerate(base)) + "\n"
        require((HERE / "packet/histories" / (family["family_id"] + ".md")).read_text() == expected_text, "review history content changed")
        require([c["slot"] for c in family["cases"]] == list(range(1, 7)), "family slot coverage")
        paired = [record_map[family["family_id"] + f"-Q{i}"]["query"] for i in (3, 5, 6)]
        require(paired[0] == paired[1] == paired[2], "withdrawal/continuation query differs")
    for variant in variants:
        hid = variant["history_id"]
        base = bundle["histories"][variant["base_history_id"]]
        history = bundle["histories"][hid]
        n = variant["base_turns"]
        require(n == len(base) and canonical(history[:n]) == canonical(base), "synthetic prefix changed")
        require(len(history) == n + 2 and history[n:] == variant["appended_messages"], "variant suffix mismatch")
        require([m["role"] for m in history[n:]] == ["user", "assistant"] and history[-1]["content"] == "Understood.", "variant roles/acknowledgment")
        source_path = HERE / "derived-sources" / (hid + ".json")
        derived = read(source_path)
        require(derived["history"] == history and derived["appended_messages"] == history[n:] and derived["base_turns"] == n, "derived source content")
        require(derived["origin"] == variant["origin"] == "synthetic_continuation_authored_for_local_evaluation", "synthetic origin")
        require(derived["base_source_sha256"] == source_hashes[variant["base_history_id"]], "derived parent raw binding")
        require(sha256(canonical(base)) == derived["base_visible_history_sha256"] == variant["base_visible_history_sha256"], "derived prefix hash")
        require(sha256(source_path.read_bytes()) == variant["source_sha256"], "derived file hash")
        require(sha256(canonical(history)) == variant["visible_history_sha256"], "variant visible hash")
        source_hashes[hid] = variant["source_sha256"]
    modes = Counter()
    for record, ref, case, question in zip(records, references, cases, bundle["questions"]):
        validate_reference(record, ref)
        require(ref["semantic_review"]["status"] == "pending", "reference silently admitted")
        require(record["source_sha256"] == source_hashes[record["persona_id"]], "record source hash")
        require(record["history"] == bundle["histories"][question["persona_id"]] and record["query"] == question["query"], "reader/record mismatch")
        require(case["query"] == record["query"] and case["proposed_reference"] == ref and case["history_id"] == record["persona_id"], "review case mismatch")
        require(0 < len(ref["answer"].split()) <= 90, "reference word limit")
        require(all(set(m) == {"role", "content"} and m["role"] in {"user", "assistant"} for m in record["history"]), "private fields exposed")
        require(not re.search(r"<(?:answer|retrieve|think|expand)>|\[RETRIEVE\]", ref["answer"], re.I), "reserved action marker in reference")
        modes[ref["mode"]] += 1
    require(dict(modes) == {"general": 60, "abstain": 20, "personalized": 40}, "reference mode metadata")
    freeze_path = HERE / "freeze.json"
    if args.freeze:
        require(not freeze_path.exists(), "refusing to overwrite frozen candidate")
        files = {str(p.relative_to(ROOT)): sha256(p.read_bytes()) for p in sorted(HERE.rglob("*"))
                 if p.is_file() and "__pycache__" not in p.parts and "review" not in p.relative_to(HERE).parts
                 and p.name not in {"verification.json", "freeze.json"}}
        entrypoint = ROOT / "CLAUDE-BROADER-EVAL.md"
        files[str(entrypoint.relative_to(ROOT))] = sha256(entrypoint.read_bytes())
        freeze_path.write_bytes(canonical({"created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "status": "candidate_reference_review_ready", "files": files,
            "prior_protected_files": len(start["protected_files"]), "training_allowed": False,
            "record_serialization": "sorted compact JSON, ensure_ascii=False, UTF-8, trailing newline",
            "acquisition_serialization": "sorted compact JSON, ensure_ascii=True, trailing newline"}))
    require(freeze_path.exists(), "run --freeze once after all deliverables are ready")
    freeze = read(freeze_path)
    for path, expected in freeze["files"].items():
        require(sha256((ROOT / path).read_bytes()) == expected, "frozen candidate changed: " + path)
    result = {"verified_at": datetime.datetime.now(datetime.timezone.utc).isoformat(), "status": "PASS",
              "freeze_sha256": sha256(freeze_path.read_bytes()), "candidate_files_verified": len(freeze["files"]),
              "prior_protected_files_verified": len(start["protected_files"]), "references_structurally_valid": 120,
              "full_base_histories_verified": 20, "synthetic_prefixes_verified": 40,
              "paired_query_triplets_verified": 20, "reader_histories_sanitized": 60,
              "modes_unscored": dict(modes), "semantic_acceptance": "pending independent review",
              "inference_runs": 0, "training_labels": 0}
    if args.review:
        result["external_review"] = validate_review(args.review, result["freeze_sha256"], records, families)
        result["semantic_acceptance"] = "See external reviewer verdicts; structural validation is not semantic certification"
    else:
        (HERE / "verification.json").write_bytes(canonical(result))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

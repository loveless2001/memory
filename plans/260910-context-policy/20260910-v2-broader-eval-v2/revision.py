"""Validate the bounded editorial delta and preserve the independent parent review."""

import argparse
import datetime
import json
import re
from collections import Counter
from pathlib import Path

from verify import HERE, ROOT, canonical, read, require, rows, sha256, span_valid

PARENT = HERE.with_name("20260910-v2-broader-eval-v1")


def audit():
    protected = read(HERE / "parent-preservation.json")["files"]
    for name, expected in protected.items():
        require(sha256((ROOT / name).read_bytes()) == expected, "parent artifact changed: " + name)
    old_records = {r["id"]: r for r in rows(PARENT / "records.jsonl")}
    new_records = {r["id"]: r for r in rows(HERE / "records.jsonl")}
    old_refs = {r["id"]: r for r in rows(PARENT / "references.jsonl")}
    new_refs = {r["id"]: r for r in rows(HERE / "references.jsonl")}
    review = read(PARENT / "review/reference-review.json")
    verdicts = {r["id"]: r for r in review["cases"]}
    intent = read(HERE / "authoring/revision-intent.json")
    require(set(old_records) == set(new_records) == set(old_refs) == set(new_refs) == set(verdicts), "case set changed")
    require(read(HERE / "reader-bundle.json")["histories"] == read(PARENT / "reader-bundle.json")["histories"], "reader histories changed")
    require(read(HERE / "packet/variants.json") == read(PARENT / "packet/variants.json"), "synthetic continuations changed")
    changes, unchanged = [], []
    for cid, new in new_records.items():
        old = old_records[cid]
        expected_record = dict(old)
        expected_ref = json.loads(json.dumps(old_refs[cid]))
        fields = []
        if cid in intent["changed_questions"]:
            expected_record["query"] = {"role": "user", "content": intent["changed_questions"][cid]}
            expected_record["query_sha256"] = sha256(canonical(expected_record["query"]))
            expected_ref["query_sha256"] = expected_record["query_sha256"]
            fields.append("query")
        if cid in intent["changed_answers"]:
            answer = intent["changed_answers"][cid]
            expected_ref["answer"] = answer
            expected_ref["personal_claims"][0]["claim"] = answer
            fields.append("answer")
        require(new == expected_record, "unexpected record change: " + cid)
        require(new_refs[cid] == expected_ref, "unexpected reference/evidence change: " + cid)
        require(not re.search(r"\b(he|she|his|her|hers|him)\b", new["query"]["content"] + " " + new_refs[cid]["answer"], re.I), "authored gendered pronoun remains: " + cid)
        if cid in intent["required_reference_repairs"]:
            require(verdicts[cid]["status"] == "reject" and new_refs[cid]["answer"] == verdicts[cid]["suggested_answer"], "reviewer repair not applied verbatim")
        if fields:
            changes.append({"id": cid, "fields": fields, "parent_status": verdicts[cid]["status"],
                "reason": "review_required_repair" if cid in intent["required_reference_repairs"] else "neutral_authoring_consistency",
                "old_query": old["query"]["content"], "new_query": new["query"]["content"],
                "old_answer": old_refs[cid]["answer"], "new_answer": new_refs[cid]["answer"],
                "old_reference_sha256": sha256(canonical(old_refs[cid])), "new_reference_sha256": sha256(canonical(new_refs[cid]))})
        else:
            require(verdicts[cid]["status"] == "accept", "unrepaired parent rejection")
            unchanged.append(cid)
    require(len(changes) == 12 and len(unchanged) == 108, "expected bounded delta")
    return {"parent_freeze_sha256": sha256((PARENT / "freeze.json").read_bytes()),
            "parent_review_sha256": sha256((PARENT / "review/reference-review.json").read_bytes()),
            "parent_files_preserved": len(protected), "changed_cases": changes,
            "unchanged_accepted_case_ids": unchanged, "answer_changes": 11, "question_changes": 2,
            "history_changes": 0, "evidence_span_changes": 0,
            "changed_case_status": "pending_independent_delta_review",
            "prior_review_counts": dict(Counter(r["status"] for r in verdicts.values())),
            "training_authorized": False}


def check_delta_review(path, manifest):
    review = read(path)
    require(set(review) == {"reviewer", "created_at", "candidate_freeze_sha256", "parent_review_sha256", "cases", "additional_findings"}, "delta review schema")
    require(isinstance(review["reviewer"], str) and bool(review["reviewer"].strip()), "reviewer required")
    datetime.datetime.fromisoformat(review["created_at"].replace("Z", "+00:00"))
    require(review["candidate_freeze_sha256"] == sha256((HERE / "freeze.json").read_bytes()), "delta freeze binding")
    require(review["parent_review_sha256"] == manifest["parent_review_sha256"], "parent review binding")
    changed = {r["id"] for r in manifest["changed_cases"]}
    require(len(review["cases"]) == len(changed) and {r["id"] for r in review["cases"]} == changed, "delta review coverage")
    records = {r["id"]: r for r in rows(HERE / "records.jsonl")}
    extra = review["additional_findings"]
    require(isinstance(extra, list) and len({r["id"] for r in extra}) == len(extra), "additional finding list")
    require(all(r["id"] in manifest["unchanged_accepted_case_ids"] and r["status"] != "accept" for r in extra), "additional findings must flag unchanged cases")
    counts = Counter()
    extra_counts = Counter()
    for row in review["cases"] + extra:
        require(set(row) == {"id", "source_sha256", "visible_history_sha256", "query_sha256", "status", "rationale", "supporting_evidence", "contradicting_evidence", "suggested_answer"}, "delta case schema")
        record = records[row["id"]]
        for key in ("source_sha256", "visible_history_sha256", "query_sha256"):
            require(row[key] == record[key], "delta case binding")
        require(row["status"] in {"accept", "reject", "ambiguous", "insufficient_source"}, "delta review incomplete or invalid")
        require(isinstance(row["rationale"], str) and bool(row["rationale"].strip()), "delta rationale required")
        require(isinstance(row["supporting_evidence"], list) and isinstance(row["contradicting_evidence"], list), "delta evidence lists")
        if row["status"] == "accept":
            require(bool(row["supporting_evidence"]) and row["suggested_answer"] is None, "accept requires supporting evidence and no repair")
        if row["suggested_answer"] is not None:
            require(isinstance(row["suggested_answer"], str) and 0 < len(row["suggested_answer"].split()) <= 90, "delta suggested answer length")
        for span in row["supporting_evidence"] + row["contradicting_evidence"]:
            span_valid(span, record["history"])
        (counts if row["id"] in changed else extra_counts)[row["status"]] += 1
    return {"delta_counts": dict(counts), "unchanged_parent_accepts": 108,
            "additional_findings": dict(extra_counts),
            "all_references_covered_by_parent_plus_delta_accepts": counts["accept"] == len(changed) and not extra,
            "semantic_truth_certified_by_validator": False, "training_authorized": False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--review", type=Path)
    args = parser.parse_args()
    manifest = audit()
    if args.prepare:
        require(not (HERE / "freeze.json").exists(), "cannot prepare a frozen revision")
        (HERE / "revision-manifest.json").write_bytes(canonical(manifest))
        changed = {r["id"] for r in manifest["changed_cases"]}
        cases = [r for r in rows(HERE / "packet/cases.jsonl") if r["id"] in changed]
        (HERE / "packet/delta-cases.jsonl").write_bytes(b"".join(canonical(r) for r in cases))
        template = read(HERE / "review-template.json")
        template.pop("full_base_histories_read")
        template["parent_review_sha256"] = manifest["parent_review_sha256"]
        template["cases"] = [r for r in template["cases"] if r["id"] in changed]
        template["additional_findings"] = []
        (HERE / "delta-review-template.json").write_bytes(canonical(template))
    require(read(HERE / "revision-manifest.json") == manifest, "editorial delta changed")
    result = {"status": "PASS", "changed_cases": len(manifest["changed_cases"]), "unchanged_parent_accepts": 108,
              "answer_changes": 11, "question_changes": 2, "parent_files_preserved": manifest["parent_files_preserved"],
              "source_history_changes": 0, "evidence_span_changes": 0, "independent_delta_review": "pending"}
    if args.review:
        # Verify the full candidate freeze before interpreting any submitted review.
        for path, expected in read(HERE / "freeze.json")["files"].items():
            require(sha256((ROOT / path).read_bytes()) == expected, "candidate changed: " + path)
        result["independent_delta_review"] = check_delta_review(args.review, manifest)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

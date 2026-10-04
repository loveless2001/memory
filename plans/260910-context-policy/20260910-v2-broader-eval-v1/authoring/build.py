"""CPU-only construction. Run from repository root; refuse a frozen target."""

import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
from experiments.context_policy.personamem import sha256
from experiments.context_policy.preflight import canonical as acquisition_canonical
from experiments.context_policy.relabel import canonical, draft_reference, evidence
from experiments.context_policy.repair_pilot import validate_bundle
from specs import SPECS

OUT = Path(__file__).resolve().parents[1]
DATA = OUT.parent / "20260910-v2-broader-eval-data"
PLAN = OUT.parent / "20260910-v2-broader-eval-plan"


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical(value))


def main():
    if (OUT / "freeze.json").exists():
        raise SystemExit("Frozen candidate: create a new version rather than overwrite it.")
    histories = json.loads((DATA / "histories.json").read_text())
    selection = json.loads((PLAN / "selection.json").read_text())
    sources = {r["persona_id"]: r for r in json.loads((DATA / "source-manifest.json").read_text())["files"]}
    order = [r["persona_id"] for r in selection["selected"]]
    assert set(order) == set(SPECS) == set(histories) and len(order) == 20
    bundle = {"histories": {}, "questions": [], "scope": "Answer each user query using its visible conversation history."}
    records, references, cases, variants, families, audit = [], [], [], [], [], []
    for number, pid in enumerate(order, 1):
        family = f"F{number:03d}"
        hid = family + "-base"
        base = histories[pid]
        spec = SPECS[pid]
        source = sources[pid]
        assert sha256(acquisition_canonical(base)) == source["visible_history_sha256"]
        base_sha = sha256(canonical(base))
        bundle["histories"][hid] = base
        full_text = "\n\n".join(f"[T{i} {m['role']}]\n{m['content']}" for i, m in enumerate(base))
        (OUT / "packet" / "histories" / (family + ".md")).write_text(
            f"# {family}: complete original sanitized history\n\nTurn numbers are zero-based.\n\n" + full_text + "\n")
        wt, pattern, wquery, same, same_answer, different, different_answer = spec["withdrawal"]
        assert base[wt]["role"] == "user" and "forget" in base[wt]["content"].lower()
        withdrawals = [i for i, m in enumerate(base) if m["role"] == "user" and
                       re.search(r"\bforget\b|do not remember|don.t remember", m["content"], re.I)]
        later = [i for i, m in enumerate(base) if i > wt and m["role"] == "user"]
        hits = [i for i in later if re.search(pattern, base[i]["content"], re.I)]
        audit.append({"family_id": family, "persona_id": pid, "withdrawal_turn": wt,
                      "topic_pattern": pattern, "all_later_user_turns": later,
                      "lexical_hits": [{"turn": i, **base[i]} for i in hits],
                      "all_possible_withdrawals": withdrawals,
                      "review_note": spec.get("chronology_note", "No later explicit re-establishment identified during source-only authoring. Independent full-history semantic review remains required."),
                      "scan_limit": "Regex is a search aid; absence of a hit is not proof of absence of a semantic restatement."})
        family_cases = []

        def add(slot, kind, history_id, history, query, answer, turns, source_sha,
                ownership="quoted_text_only", mode="general", withdrawal=False):
            cid = f"{family}-Q{slot}"
            question = {"role": "user", "content": query}
            record = {"id": cid, "persona_id": history_id, "family_id": family,
                      "source_sha256": source_sha,
                      "visible_history_sha256": sha256(canonical(history)),
                      "query_sha256": sha256(canonical(question)), "history": history, "query": question}
            spans = [evidence(history, t, history[t]["content"]) for t in turns]
            constraints = []
            claims = []
            if not withdrawal:
                claims = [{"claim": answer, "evidence": spans, "ownership": ownership, "current_status": "current"}]
                if ownership != "user":
                    constraints.append({"rule": "Attribute the answer within the identified source passage; do not turn a quoted speaker's details into current user biography.",
                                        "kind": "task_scope", "evidence": spans})
            if withdrawal or slot in (5, 6):
                constraints.append({"rule": "The original preference/detail was withdrawn. Withdrawal alone establishes neither that value nor its opposite. A later explicit user statement can establish a current value.",
                                    "kind": "withdrawal", "evidence": [evidence(history, wt, history[wt]["content"])]})
            if withdrawal:
                constraints.append({"rule": "The proposed answer treats the current value as unknown; independently check all later messages for a valid re-establishment.",
                                    "kind": "uncertainty", "evidence": spans})
            ref = draft_reference(record, answer, mode, claims, constraints,
                                  "Proposed source-bound reference; independent semantic review is pending.")
            assert len(answer.split()) <= 90
            records.append(record)
            references.append(ref)
            bundle["questions"].append({"id": cid, "persona_id": history_id, "query": question})
            cases.append({"id": cid, "family_id": family, "history_id": history_id,
                          "base_history_file": f"histories/{family}.md", "query": question,
                          "proposed_reference": ref})
            family_cases.append({"id": cid, "slot": slot, "kind": kind, "history_id": history_id})

        for slot, fact in enumerate(spec["facts"], 1):
            turns, query, answer = fact
            add(slot, "historical_recall", hid, base, query, answer, turns, source["sha256"])
        add(3, "withdrawal", hid, base, wquery,
            "The usable history does not establish that current detail about you.", [wt], source["sha256"], mode="abstain", withdrawal=True)
        turns, query, answer = spec["control"]
        add(4, "ownership_control", hid, base, query, answer, turns, source["sha256"], spec.get("control_ownership", "quoted_text_only"))
        for slot, name, statement, answer in [(5, "different", different, different_answer), (6, "same", same, same_answer)]:
            variant_id = family + "-" + name
            appended = [{"role": "user", "content": "Here is a current personal detail I want you to use in future replies: " + statement},
                        {"role": "assistant", "content": "Understood."}]
            extended = base + appended
            derived = {"origin": "synthetic_continuation_authored_for_local_evaluation",
                       "base_source_sha256": source["sha256"], "base_visible_history_sha256": base_sha,
                       "base_turns": len(base), "appended_messages": appended, "history": extended}
            derived_path = OUT / "derived-sources" / (variant_id + ".json")
            write(derived_path, derived)
            derived_sha = sha256(derived_path.read_bytes())
            bundle["histories"][variant_id] = extended
            variants.append({"history_id": variant_id, "family_id": family, "base_history_id": hid,
                             "origin": derived["origin"], "base_turns": len(base), "appended_messages": appended,
                             "source_sha256": derived_sha, "visible_history_sha256": sha256(canonical(extended)),
                             "base_visible_history_sha256": base_sha})
            add(slot, "synthetic_later_" + name, variant_id, extended, wquery, answer,
                [len(base)], derived_sha, ownership="user", mode="personalized")
        families.append({"family_id": family, "persona_id": pid, "base_history_id": hid,
                         "source_path": source["local_path"], "source_sha256": source["sha256"],
                         "base_visible_history_sha256": base_sha,
                         "acquisition_visible_history_sha256": source["visible_history_sha256"], "cases": family_cases})
    validate_bundle(bundle)
    for name, rows in [("records.jsonl", records), ("references.jsonl", references), ("packet/cases.jsonl", cases)]:
        (OUT / name).write_bytes(b"".join(canonical(r) for r in rows))
    write(OUT / "reader-bundle.json", bundle)
    write(OUT / "packet/variants.json", variants)
    write(OUT / "authoring/family-map.json", families)
    write(OUT / "authoring/chronology-audit.json", audit)
    write(OUT / "coverage.json", {"candidate_cases": len(records), "source_families": len(families),
          "original_histories": 20, "synthetic_complete_history_variants": len(variants),
          "counts": dict(Counter(c["kind"] for f in families for c in f["cases"])), "gaps": [],
          "reference_status": "pending_independent_review", "inference_runs": 0, "training_labels": 0,
          "new_family_exact_turn_components": 19, "new_family_components_through_all_acquired_sources": 17,
          "independent_sample_size": None, "official_external_test": False})
    write(OUT / "review-template.json", {"reviewer": "", "created_at": "", "candidate_freeze_sha256": "",
          "full_base_histories_read": [], "cases": [
              {"id": r["id"], "source_sha256": r["source_sha256"], "visible_history_sha256": r["visible_history_sha256"],
               "query_sha256": r["query_sha256"], "status": "pending", "rationale": "",
               "supporting_evidence": [], "contradicting_evidence": [], "suggested_answer": None}
              for r in references]})
    print(json.dumps({"cases": len(records), "families": len(families), "variants": len(variants), "status": "candidate_built_not_reviewed"}))


if __name__ == "__main__":
    main()

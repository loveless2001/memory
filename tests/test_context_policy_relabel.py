import copy

import pytest

from experiments.context_policy.relabel import canonical, draft_reference, evidence, sha256, validate_reference


def record():
    history = [{"role": "user", "content": "I use blue for reports."},
               {"role": "assistant", "content": "You also like red."},
               {"role": "user", "content": "Please forget that I use blue for reports."}]
    query = {"role": "user", "content": "Which color should I use?"}
    return {"id": "example", "source_sha256": "source", "history": history, "query": query,
            "visible_history_sha256": sha256(canonical(history)), "query_sha256": sha256(canonical(query))}


def test_withdrawal_source_bound_but_not_treated_as_negative_preference():
    r = record()
    ref = draft_reference(r, "Which colors suit the report's audience?", "clarify", constraints=[{
        "kind": "withdrawal", "rule": "Do not assert a remembered blue preference; this does not mean the user dislikes blue.",
        "evidence": [evidence(r["history"], 2, r["history"][2]["content"])]}])
    assert validate_reference(r, ref)
    changed = copy.deepcopy(r)
    changed["history"][2]["content"] = "Actually, blue is still my preference."
    with pytest.raises(ValueError, match="history changed"):
        validate_reference(changed, ref)


def test_assistant_guess_cannot_become_personal_fact():
    r = record()
    with pytest.raises(ValueError, match="assistant assertion"):
        draft_reference(r, "Use red, your favorite.", "personalized", claims=[{
            "claim": "User likes red", "ownership": "user", "current_status": "current",
            "evidence": [evidence(r["history"], 1, "You also like red.")]}])


def test_evidence_quotes_and_queries_cannot_be_silently_changed():
    r = record()
    with pytest.raises(ValueError, match="exactly once"):
        evidence(r["history"], 0, "I use green")
    ref = draft_reference(r, "Which colors suit the audience?", "clarify")
    r["query"]["content"] = "Remember blue again."
    with pytest.raises(ValueError, match="query changed"):
        validate_reference(r, ref)


def test_withdrawn_claim_is_rejected_even_with_exact_historical_evidence():
    r = record()
    with pytest.raises(ValueError, match="withdrawn details"):
        draft_reference(r, "Use blue as usual.", "personalized", claims=[{
            "claim": "User uses blue", "ownership": "user", "current_status": "withdrawn",
            "evidence": [evidence(r["history"], 0, "I use blue for reports.")]}])

import pytest

from experiments.context_policy.repair_pilot import chunks_for, retrieve_rounds, validate_bundle


class CharacterTokenizer:
    def encode(self, text, add_special_tokens=False):
        return list(map(ord, text))

    def decode(self, ids):
        return "".join(map(chr, ids))


def test_reader_bundle_rejects_profile_and_scoring_fields():
    valid = {"histories": {"p": [{"role": "user", "content": "blue"}]},
             "questions": [{"id": "q", "persona_id": "p", "query": {"role": "user", "content": "color?"}}],
             "scope": "diagnostic"}
    validate_bundle(valid)
    valid["questions"][0]["correct_answer"] = "blue"
    with pytest.raises(ValueError):
        validate_bundle(valid)


def test_chunks_preserve_source_and_retrieval_rounds_do_not_repeat():
    tokenizer = CharacterTokenizer()
    history = [{"role": "user", "content": "orchid "*80}, {"role": "user", "content": "orchid blue white"}]
    chunks = chunks_for(tokenizer, history, limit=60, overlap=8)
    assert chunks and all(len(c["content"]) <= 60 for c in chunks)
    by_turn = [c for c in chunks if c["turn"] == 0]
    assert by_turn[0]["start"] == 0 and by_turn[-1]["end"] == len(history[0]["content"])
    assert all(b["start"] == a["end"]-8 for a, b in zip(by_turn, by_turn[1:]))
    rounds = retrieve_rounds(tokenizer, chunks, "orchid", cap=130)
    assert all(r["tokens"] <= 130 for r in rounds)
    assert not set(rounds[0]["chunk_ids"]) & set(rounds[1]["chunk_ids"])

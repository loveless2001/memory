import pytest

from experiments.context_policy.personamem import history_path, match_snippet, reader_record


def test_private_profiles_and_labels_cannot_enter_reader_input():
    payload = {"metadata": {"persona": "PRIVATE_PROFILE"}, "chat_history": [
        {"role": "system", "content": "PRIVATE_PROFILE"},
        {"role": "user", "content": "Please use blue.", "preference": "PRIVATE_LABEL"},
        {"role": "assistant", "content": "Blue it is."}]}
    row = {"user_query": "{'role': 'user', 'content': 'Which color?'}", "correct_answer": "PRIVATE_GOLD"}
    expected = {"history": [{"role": "user", "content": "Please use blue."},
                             {"role": "assistant", "content": "Blue it is."}],
                "query": {"role": "user", "content": "Which color?"}}
    assert reader_record(row, payload) == expected
    row.update(expanded_persona="NEW_PRIVATE_PROFILE", unexpected_private_field="FUTURE_LABEL")
    payload["chat_history"][0]["content"] = "CHANGED_PROFILE"
    assert reader_record(row, payload) == expected


def test_support_requires_matching_roles_and_contiguous_actual_turns():
    history = [{"role": "user", "content": "I like blue."}, {"role": "assistant", "content": "Understood."}]
    row = {"related_conversation_snippet": '[{"role":"user","content":"I like blue."}]'}
    assert match_snippet(row, history)["contiguous_starts"] == [0]
    row["related_conversation_snippet"] = '[{"role":"assistant","content":"I like blue."}]'
    assert match_snippet(row, history)["contiguous_starts"] == []


@pytest.mark.parametrize("path", ["../secrets", "/tmp/file.json", "data/raw_data/persona1.json",
                                  "https://example.com/history.json"])
def test_history_path_cannot_select_profiles_or_escape_dataset(path):
    with pytest.raises(ValueError):
        history_path(path)


def test_unexpected_history_role_rejected():
    with pytest.raises(ValueError):
        reader_record({"user_query": '{"role":"user","content":"Hello"}'},
                      {"chat_history": [{"role": "tool", "content": "private"}]})

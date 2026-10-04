import copy
import json
from pathlib import Path
import pytest
from transformers import AutoTokenizer
from experiments.context_policy.preflight import digest
from experiments.context_policy.reader_regression import (strict_body_capture, paired_views,
    validate_topics, neutral_record, reader_messages, append_evidence, answer_prefix_ids)

DATA = Path('plans/260910-context-policy/20260910-v2-withdrawal-regression-data')

def read(name): return json.loads((DATA / name).read_text())

@pytest.fixture(scope='module')
def tokenizer():
    return AutoTokenizer.from_pretrained('Qwen/Qwen3-4B-Instruct-2507',
        revision='cdbee75f17c01a7cc42f958dc650907174af0554', local_files_only=True)

@pytest.mark.parametrize('text,valid', [('ANSWER\nTea.', False), ('Tea.\nRETRIEVE', False),
    ('I would ANSWER this.', False), ('The answer is unknown.', True), ('Tea.', True), ('', False)])
def test_body_markers(tokenizer, text, valid):
    ids = tokenizer.encode(text, add_special_tokens=False) + [tokenizer.eos_token_id]
    assert strict_body_capture(tokenizer, ids, tokenizer.eos_token_id)['body_structurally_valid'] == valid


def test_body_truncation_and_length(tokenizer):
    ids = tokenizer.encode('unknown', add_special_tokens=False)
    assert not strict_body_capture(tokenizer, ids, tokenizer.eos_token_id)['body_structurally_valid']
    ids = tokenizer.encode('word ' * 91, add_special_tokens=False) + [tokenizer.eos_token_id]
    assert not strict_body_capture(tokenizer, ids, tokenizer.eos_token_id)['within_90_words']

@pytest.mark.parametrize('mutation', ['hash', 'role', 'duplicate', 'turn', 'extra', 'topic'])
def test_topic_binding_rejects_invalid(mutation):
    bundle, topics = read('reader-input.json'), read('topics.json')
    pid = next(pid for pid, ts in topics.items() if ts)
    history, selected = copy.deepcopy(bundle['histories'][pid]), copy.deepcopy(topics[pid])
    if mutation == 'hash': selected[0]['source_sha256'] = 'changed'
    elif mutation == 'role':
        history[selected[0]['turn']]['role'] = 'assistant'
        selected[0]['source_sha256'] = digest(history[selected[0]['turn']])
    elif mutation == 'duplicate': selected.append(selected[0])
    elif mutation == 'turn': selected[0]['turn'] = True
    elif mutation == 'extra': selected[0]['answer'] = 'leak'
    elif mutation == 'topic': selected[0]['topic'] = 'line\nbreak'
    with pytest.raises(ValueError): validate_topics(history, selected)


def test_all_frozen_views_and_append_prefixes(tokenizer):
    bundle, notes, topics = read('reader-input.json'), read('notes.json'), read('topics.json')
    contexts = read('expected-contexts.json')
    config = json.loads(Path('experiments/context_policy/design.json').read_text())
    actual = []
    for question, row in zip(bundle['questions'], read('schedule.json')):
        pid = question['persona_id']; history = bundle['histories'][pid]; query = question['query']['content']
        views = paired_views(tokenizer, history, notes[pid], topics[pid], query, config)
        assert views['raw']['retrieval']['chunk_ids'] == views['neutral']['retrieval']['chunk_ids']
        for quote in notes[pid]['selected']:
            assert quote['quote'] in views['neutral']['notes']
        for entry in notes[pid]['withdrawals']:
            match = next((t for t in topics[pid] if t['turn'] == entry['turn']), None)
            assert (neutral_record(match) if match else entry['content']) in views['neutral']['notes']
        for arm in row['arm_order']:
            view = views[arm]
            messages = reader_messages(view['notes'], view['recent'], query)
            initial = tokenizer.apply_chat_template(messages, tokenize=True, add_generation_prompt=True)
            if row['retrieval_rounds']:
                messages = append_evidence(messages, view['retrieval']['text'], query)
                expanded = tokenizer.apply_chat_template(messages, tokenize=True, add_generation_prompt=True)
                assert expanded[:len(initial)] == initial
            expected = contexts[len(actual)]
            assert expected['messages'] == messages
            assert expected['input_tokens'] == len(answer_prefix_ids(tokenizer, messages))
            actual.append((question['id'], arm))
    assert len(actual) == 42 and len(set(actual)) == 42

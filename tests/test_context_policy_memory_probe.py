import copy
import pytest
from transformers import AutoTokenizer
from experiments.context_policy.grounded_notes import render_notes, source_candidates
from experiments.context_policy.memory_probe import validate_reused_notes
from experiments.context_policy.preflight import digest


@pytest.fixture(scope='module')
def source():
    tokenizer = AutoTokenizer.from_pretrained('Qwen/Qwen3-4B-Instruct-2507',
        revision='cdbee75f17c01a7cc42f958dc650907174af0554', local_files_only=True)
    history = [{'role': 'user', 'content': 'In my draft, the meeting is at 8 p.m.'},
               {'role': 'assistant', 'content': 'An unsupported story about someone else.'},
               {'role': 'user', 'content': 'Please forget that I prefer tea.'}]
    quotes, withdrawals = source_candidates(tokenizer, history)
    text = render_notes(quotes, withdrawals)
    bundle = {'histories': {'p': history}, 'questions': [{'id': 'q', 'persona_id': 'p',
              'query': {'role': 'user', 'content': 'What meeting time did the draft give?'}}], 'scope': 'test'}
    notes = {'p': {'history_sha256': digest(history), 'selected': quotes, 'withdrawals': withdrawals,
                   'text': text, 'tokens': len(tokenizer.encode(text, add_special_tokens=False))}}
    return tokenizer, bundle, notes


def test_reuse_accepts_bound_notes_without_regeneration(source):
    tokenizer, bundle, notes = source
    before = copy.deepcopy(notes)
    result = validate_reused_notes(tokenizer, bundle, notes)
    assert result == {'histories': 1, 'quotations': 1, 'withdrawals': 1,
                      'all_source_bindings_valid': True, 'regenerated': False}
    assert notes == before


@pytest.mark.parametrize('mutation', ['history', 'ledger', 'quote', 'role', 'render', 'tokens', 'duplicate', 'missing_persona'])
def test_reuse_rejects_tampering_and_history_mismatch(source, mutation):
    tokenizer, bundle, notes = source
    bundle, notes = copy.deepcopy(bundle), copy.deepcopy(notes)
    note = notes['p']
    if mutation == 'history': bundle['histories']['p'][0]['content'] += ' Changed.'
    elif mutation == 'ledger': note['withdrawals'] = []
    elif mutation == 'quote': note['selected'][0]['quote'] = 'The meeting is at 9 p.m.'
    elif mutation == 'role':
        bundle['histories']['p'][0]['role'] = 'assistant'
        note['history_sha256'] = digest(bundle['histories']['p'])
        note['selected'][0]['source_sha256'] = digest(bundle['histories']['p'][0])
    elif mutation == 'render': note['text'] += '\nUnbound extra fact.'
    elif mutation == 'tokens': note['tokens'] -= 1
    elif mutation == 'duplicate': note['selected'] *= 2
    elif mutation == 'missing_persona': notes.clear()
    with pytest.raises(ValueError): validate_reused_notes(tokenizer, bundle, notes)

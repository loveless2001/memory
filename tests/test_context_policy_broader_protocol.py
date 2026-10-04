"""Source fidelity and archival transcript checks, without reader inference."""
import copy

import pytest
from transformers import AutoTokenizer

from experiments.context_policy.broader_protocol import (chunks_for, recent_view, retrieve, source_span,
    validate_span, render_span, reader_messages, append_evidence, answer_prefix_ids)


@pytest.fixture(scope='module')
def tokenizer():
    return AutoTokenizer.from_pretrained('Qwen/Qwen3-4B-Instruct-2507',
        revision='cdbee75f17c01a7cc42f958dc650907174af0554', local_files_only=True)


def test_unicode_chunks_cover_source_without_rewriting(tokenizer):
    text = ('  Tiếng Việt 👩🏽‍💻 — ฉันเป็นไกด์ 中文 café e\u0301\n' * 35) + 'END'
    history = [{'role': 'user', 'content': text}]
    chunks = chunks_for(tokenizer, history, limit=96, overlap=16)
    cursor = 0
    for span in chunks:
        validate_span(history, span)
        assert span['start'] <= cursor
        assert span['quote'] == text[span['start']:span['end']]
        assert len(tokenizer.encode(render_span(span), add_special_tokens=False)) <= 96
        cursor = max(cursor, span['end'])
    assert cursor == len(text)


@pytest.mark.parametrize('field,value', [('role','user'), ('quote','altered'), ('source_sha256','bad'), ('start',True)])
def test_source_binding_rejects_role_or_content_forgery(field, value):
    history = [{'role':'assistant','content':'My guess is tea.'}]
    span = source_span(history,0,0,len(history[0]['content']))
    changed=copy.deepcopy(span);changed[field]=value
    with pytest.raises(ValueError):
        validate_span(history, changed)


def test_recent_slice_keeps_actual_role_and_offsets(tokenizer):
    history = [{'role':'user','content':'Please forget my preference for tea.'},
               {'role':'assistant','content':('Only a guess. 👩🏽‍💻 ' * 100) + 'Final sentence.'}]
    recent = recent_view(tokenizer,history,cap=80)
    assert recent['tokens'] <= 80 and len(recent['spans'])==1
    span=recent['spans'][0]
    validate_span(history,span)
    assert span['role']=='assistant' and span['start']>0 and span['end']==len(history[1]['content'])


def test_retrieval_keeps_speakers_and_does_not_repeat_chunks(tokenizer):
    history=[{'role':'user','content':'Please forget the tea preference.'},
             {'role':'assistant','content':'I might guess tea, but that is not evidence.'},
             {'role':'user','content':'My current preference is coffee.'}]
    chunks=chunks_for(tokenizer,history,96,16)
    rounds=retrieve(tokenizer,chunks,'What is my current tea or coffee preference?',cap=128)
    selected=[s for r in rounds for s in r['spans']]
    assert len({s['id'] for s in selected})==len(selected)
    assert any(s['role']=='assistant' for s in selected)
    for s in selected:validate_span(history,s)


def test_archival_appends_preserve_prefix_and_question(tokenizer):
    query='Which plan is current?'
    messages=reader_messages('Source quotations only.','',query)
    for evidence in ['[T0 user chars 0:12]\nOld question.', '[T2 user chars 0:10]\nCorrection']:
        before=tokenizer.apply_chat_template(messages,tokenize=True,add_generation_prompt=True)
        messages=append_evidence(messages,evidence,query)
        after=tokenizer.apply_chat_template(messages,tokenize=True,add_generation_prompt=True)
        assert after[:len(before)]==before
        assert messages[-1]['content'].endswith(query)
    assert answer_prefix_ids(tokenizer,messages)[-len(tokenizer.encode('ANSWER\n',add_special_tokens=False)):] == tokenizer.encode('ANSWER\n',add_special_tokens=False)


def test_direct_forget_enters_complete_ledger_and_is_not_selectable(tokenizer):
    import json
    from experiments.context_policy.broader_notes import source_candidates, pack_ranked_selection, withdrawal
    history=[{'role':'user','content':'Forget that I drink tea.'},
             {'role':'assistant','content':'Forget that I drink coffee.'},
             {'role':'user','content':'My current drink is water.'},
             {'role':'user','content':'Please forget my old breakfast preference.'}]
    candidates,ledger=source_candidates(tokenizer,history)
    assert [x['turn'] for x in ledger]==[0,3]
    assert {x['turn'] for x in candidates}=={2}
    assert not withdrawal(history[1])
    selected,text,audit=pack_ranked_selection(tokenizer,json.dumps([candidates[0]['id']]),True,[],candidates,ledger,history)
    assert 'Forget that I drink tea.' in text and 'My current drink is water.' in text
    with pytest.raises(ValueError,match='ledger'):
        pack_ranked_selection(tokenizer,json.dumps([candidates[0]['id']]),True,[],candidates,ledger[1:],history)


def test_note_quote_id_must_match_its_actual_source(tokenizer):
    from experiments.context_policy.broader_notes import source_candidates, validate_quotes
    history=[{'role':'user','content':'My current drink is water.'}]
    candidates,_=source_candidates(tokenizer,history)
    validate_quotes(history,candidates)
    candidates[0]['id']='T99:0-2'
    with pytest.raises(ValueError,match='identity/source'):
        validate_quotes(history,candidates)

"""Versioned explicit-withdrawal coverage; legacy note code stays unchanged."""

import json
import re

from .grounded_notes import (source_candidates as legacy_candidates, withdrawal as legacy_withdrawal,
                             accept_selection, render_notes)
from .preflight import digest


def withdrawal(message):
    return message['role'] == 'user' and re.match(r'^\s*(?:please\s+)?forget\b', message['content'], re.I) is not None


def ledger_for(history, through=None):
    through = len(history)-1 if through is None else through
    return [{'turn': i, 'content': m['content']} for i, m in enumerate(history) if i <= through and withdrawal(m)]


def source_candidates(tokenizer, history, quote_tokens=96):
    candidates, _ = legacy_candidates(tokenizer, history, quote_tokens)
    constraints = ledger_for(history)
    turns = {x['turn'] for x in constraints}
    return [c for c in candidates if c['turn'] not in turns], constraints


def validate_quotes(history, quotes):
    for q in quotes:
        if set(q) != {'id', 'turn', 'start', 'end', 'quote', 'source_sha256'}:
            raise ValueError('unexpected note quotation fields')
        turn, start, end = q['turn'], q['start'], q['end']
        if type(turn) is not int or not 0 <= turn < len(history):
            raise ValueError('note quotation turn invalid')
        message = history[turn]
        if type(start) is not int or type(end) is not int or not 0 <= start < end <= len(message['content']):
            raise ValueError('note quotation offsets invalid')
        if (message['role'] != 'user' or withdrawal(message) or q['source_sha256'] != digest(message)
                or q['quote'] != message['content'][start:end] or q['id'] != f'T{turn}:{start}-{end}'):
            raise ValueError('note quotation identity/source mismatch')


def pack_ranked_selection(tokenizer, raw, ended_at_eos, previous, incoming, constraints,
                          history, note_tokens=768, through_turn=None):
    through = len(history)-1 if through_turn is None else through_turn
    if constraints != ledger_for(history, through):
        raise ValueError('expanded withdrawal ledger changed or incomplete')
    validate_quotes(history, previous + incoming)
    if any(withdrawal(history[q['turn']]) for q in previous + incoming):
        raise ValueError('withdrawal cannot be a selectable fact quotation')
    # Reuse the original exact-quote/ranking validator with its own expected
    # legacy ledger; admission below uses the complete expanded ledger instead.
    legacy_ledger = [{'turn': i, 'content': m['content']} for i, m in enumerate(history)
                     if i <= through and legacy_withdrawal(m)]
    validated, _ = accept_selection(tokenizer, raw, ended_at_eos, previous, incoming,
        legacy_ledger, history, note_tokens=10**9, through_turn=through)
    ranking = json.loads(raw)
    if len(ranking) > 8:
        raise ValueError('ranking exceeds eight choices')
    by_id = {q['id']:q for q in validated}
    if len(tokenizer.encode(render_notes([], constraints), add_special_tokens=False)) >= note_tokens:
        raise ValueError('withdrawals consume note budget')
    selected, omitted = [], []
    for key in ranking:
        trial = sorted(selected + [by_id[key]], key=lambda q:(q['turn'], q['start']))
        count = len(tokenizer.encode(render_notes(trial, constraints), add_special_tokens=False))
        if count <= note_tokens:
            selected = trial
        else:
            omitted.append({'id':key,'reason':'whole_quote_exceeds_remaining_budget','proposed_note_tokens':count})
    if not selected:
        raise ValueError('no ranked quotation fits with expanded ledger')
    text = render_notes(selected, constraints)
    return selected, text, {'mode':'ranked_whole_quote_admission_explicit_forget_v1', 'ranked_ids':ranking,
                           'admitted_ids':[q['id'] for q in selected], 'omitted':omitted,
                           'note_tokens':len(tokenizer.encode(text, add_special_tokens=False))}


def validate_notes(tokenizer, histories, notes, cap=768):
    if set(notes) != set(histories):
        raise ValueError('notes do not cover histories')
    for hid, history in histories.items():
        note = notes[hid]
        if note['history_sha256'] != digest(history) or note['withdrawals'] != ledger_for(history):
            raise ValueError('note history/ledger mismatch')
        quotes = note['selected']
        validate_quotes(history, quotes)
        if not quotes or len(quotes)>8 or len({q['id'] for q in quotes}) != len(quotes):
            raise ValueError('note selections missing, duplicate or excessive')
        if any(withdrawal(history[q['turn']]) for q in quotes):
            raise ValueError('withdrawal selected as fact')
        legacy_ledger = [{'turn':i,'content':m['content']} for i,m in enumerate(history) if legacy_withdrawal(m)]
        accept_selection(tokenizer, json.dumps([q['id'] for q in quotes]), True, [], quotes,
                         legacy_ledger, history, note_tokens=10**9)
        text = render_notes(quotes, note['withdrawals'])
        tokens = len(tokenizer.encode(text, add_special_tokens=False))
        if note['text'] != text or note['tokens'] != tokens or tokens > cap:
            raise ValueError('note text/token budget mismatch')
    return {'histories':len(notes), 'quotations':sum(len(n['selected']) for n in notes.values()),
            'withdrawals':sum(len(n['withdrawals']) for n in notes.values()), 'all_source_bindings_valid':True,
            'regenerated':True, 'base_histories_generated':20, 'synthetic_branches_updated':40}

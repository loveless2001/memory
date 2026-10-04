"""Query-blind extractive note updates for the repaired development probe.

Selection is lossy; quotations certify provenance, never ownership or entailment.
The supported withdrawal detector is deliberately limited to this release's
explicit 'Please forget ...' user turns. It is not a general deletion classifier.
"""

import json
import re

from .preflight import digest


SELECTOR_SYSTEM = """Select useful USER QUOTATIONS for a compact memory for unknown future questions.
Return only a JSON array of candidate IDs, no prose or markdown. You may retain old IDs
or select new ones. Favor concrete enduring context, decisions and corrections over
generic questions. Quotations may be drafts or third-party text: do not infer ownership.
Withdrawal requests are retained separately by the program; do not reverse their meaning.
The complete rendered memory must fit the stated token budget. IDs omitted are forgotten
from the compact memory, but remain in the source archive. Never invent an ID."""


def withdrawal(message):
    return message['role'] == 'user' and re.match(r'^\s*please\s+forget\b', message['content'], re.I) is not None


def source_candidates(tokenizer, history, quote_tokens=96):
    if quote_tokens < 1:
        raise ValueError('quote token budget must be positive')
    candidates, constraints = [], []
    for turn, message in enumerate(history):
        if message['role'] != 'user':
            continue
        text = message['content']
        if withdrawal(message):
            constraints.append({'turn': turn, 'content': text})
            continue
        encoded = tokenizer(text, add_special_tokens=False, return_offsets_mapping=True)
        offsets = encoded['offset_mapping']
        start_index = 0
        while start_index < len(offsets):
            end_index = min(start_index + quote_tokens, len(offsets))
            start, end = offsets[start_index][0], offsets[end_index-1][1]
            # Adjacent byte-level tokens can share a Unicode character offset.
            while end_index < len(offsets) and offsets[end_index][0] < end:
                end_index += 1
                end = offsets[end_index-1][1]
            quote = text[start:end]
            candidates.append({'id': f'T{turn}:{start}-{end}', 'turn': turn,
                               'start': start, 'end': end, 'quote': quote,
                               'source_sha256': digest(message)})
            start_index = end_index
    return candidates, constraints


def render_notes(selected, constraints):
    lines = ['Historical user quotations; drafts and questions are not established personal facts.']
    lines.extend(f"[{x['id']} user quote] {x['quote']}" for x in selected)
    if constraints:
        lines.append('WITHDRAWALS: do not rely on the withdrawn detail; no opposite preference is implied.')
        lines.extend(f"[T{x['turn']} user withdrawal] {x['content']}" for x in constraints)
    return '\n'.join(lines)


def note_batches(tokenizer, candidates, max_tokens=3072):
    batches, current = [], []
    for candidate in candidates:
        trial = current + [candidate]
        if len(tokenizer.encode(json.dumps(trial, ensure_ascii=False), add_special_tokens=False)) > max_tokens:
            if not current:
                raise ValueError('one source candidate exceeds note-update budget')
            batches.append(current)
            current = [candidate]
            if len(tokenizer.encode(json.dumps(current, ensure_ascii=False), add_special_tokens=False)) > max_tokens:
                raise ValueError('one source candidate exceeds note-update budget')
        else:
            current = trial
    if current:
        batches.append(current)
    return batches


def selector_messages(tokenizer, previous, incoming, constraints, note_tokens=768):
    available = {x['id']: x for x in previous + incoming}
    baseline = len(tokenizer.encode(render_notes([], constraints), add_special_tokens=False))
    if baseline >= note_tokens:
        raise ValueError('withdrawals consume the note budget; do not silently drop them')
    candidates = []
    for x in available.values():
        rendered = f"[{x['id']} user quote] {x['quote']}\n"
        candidates.append({'id': x['id'], 'quote': x['quote'],
                           'estimated_tokens': len(tokenizer.encode(rendered, add_special_tokens=False))})
    return [{'role': 'system', 'content': SELECTOR_SYSTEM}, {'role': 'user', 'content': json.dumps({
        'remaining_quote_token_budget': note_tokens-baseline, 'candidates': candidates,
        'withdrawals': constraints}, ensure_ascii=False)}]


def accept_selection(tokenizer, raw, ended_at_eos, previous, incoming, constraints, history, note_tokens=768, through_turn=None):
    through_turn = len(history)-1 if through_turn is None else through_turn
    expected = [{'turn': i, 'content': m['content']} for i, m in enumerate(history)
                if i <= through_turn and withdrawal(m)]
    if constraints != expected:
        raise ValueError('withdrawal ledger changed or incomplete')
    if not ended_at_eos:
        raise ValueError('truncated note selection')
    ids = json.loads(raw)
    if not isinstance(ids, list) or any(not isinstance(x, str) for x in ids):
        raise ValueError('note selection must be an array of source IDs')
    available = {x['id']: x for x in previous + incoming}
    if len(ids) != len(set(ids)) or any(x not in available for x in ids):
        raise ValueError('duplicate or unavailable source ID')
    if available and not ids:
        raise ValueError('empty note selection')
    selected = sorted((available[x] for x in ids), key=lambda x: (x['turn'], x['start']))
    for x in selected:
        message = history[x['turn']]
        if (message['role'] != 'user' or digest(message) != x['source_sha256']
                or message['content'][x['start']:x['end']] != x['quote']):
            raise ValueError('source quote binding changed')
    if len({x['quote'] for x in selected}) != len(selected):
        raise ValueError('repeated note quotation')
    rendered = render_notes(selected, constraints)
    if len(tokenizer.encode(rendered, add_special_tokens=False)) > note_tokens:
        raise ValueError('rendered notes exceed budget; no silent clipping')
    return selected, rendered

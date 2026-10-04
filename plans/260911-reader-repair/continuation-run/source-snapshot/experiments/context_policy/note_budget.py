"""Prospective deterministic admission of ranked source quotations.

This is not used by the frozen revision-2 run. Replaying its failed selection
locally tests feasibility only and cannot change its recorded gate result.
"""

import json

from .grounded_notes import accept_selection, render_notes, selector_messages


def ranked_selector_messages(tokenizer, previous, incoming, constraints, note_tokens=768):
    messages = selector_messages(tokenizer, previous, incoming, constraints, note_tokens)
    messages[0]['content'] = """Rank candidate USER QUOTATIONS by usefulness for unknown future questions.
Return only a JSON array of at most 8 distinct candidate IDs, best first. No prose.
Favor concrete enduring context, decisions and corrections over generic questions.
Quotations may be drafts or third-party text: never infer personal ownership.
Withdrawal requests are retained separately by the program. Never reverse their meaning.
The program will enforce the note token budget by admitting complete quotes in rank order.
You rank quotations; do not rewrite them, invent IDs, or try to calculate a token total."""
    return messages


def pack_ranked_selection(tokenizer, raw, ended_at_eos, previous, incoming,
                          constraints, history, note_tokens=768, through_turn=None):
    # Validate the entire proposed ranking before any budget-based omission.
    # An invalid ID is still a failure even if its quote would not have fitted.
    validated, _ = accept_selection(tokenizer, raw, ended_at_eos, previous, incoming,
        constraints, history, note_tokens=10**9, through_turn=through_turn)
    ranking = json.loads(raw)
    by_id = {x['id']: x for x in validated}
    if len(tokenizer.encode(render_notes([], constraints), add_special_tokens=False)) >= note_tokens:
        raise ValueError('withdrawals consume the note budget')
    admitted, omitted = [], []
    for source_id in ranking:
        proposed = sorted(admitted + [by_id[source_id]], key=lambda x: (x['turn'], x['start']))
        count = len(tokenizer.encode(render_notes(proposed, constraints), add_special_tokens=False))
        if count <= note_tokens:
            admitted = proposed
        else:
            omitted.append({'id': source_id, 'reason': 'whole_quote_exceeds_remaining_budget',
                            'proposed_note_tokens': count})
    if not admitted:
        raise ValueError('no ranked quotation fits with the withdrawal ledger')
    rendered = render_notes(admitted, constraints)
    return admitted, rendered, {'mode': 'ranked_whole_quote_admission',
        'ranked_ids': ranking, 'admitted_ids': [x['id'] for x in admitted],
        'omitted': omitted, 'note_tokens': len(tokenizer.encode(rendered, add_special_tokens=False))}

"""Source-bound event parsing and chronological state resolution for a diagnostic.

This module receives no gold labels. Property/scope metadata is query routing,
not a predicted state. Exact source anchoring validates location, not semantics.
"""
import json
from .broader_protocol import SYSTEM, reader_messages, source_span, render_spans

EXTRACT_SYSTEM = '''Extract events about the TARGET PROPERTY from USER turns in
the quoted archive. Do not answer a question or infer the final state. Output
only one JSON object {"events": [...]} after the supplied ANSWER prefix.
Each event is an array [turn_number, owner, operation, value, exact_quote].
owner is "user" for the user's own assertion, or "other" for fiction, drafts,
quoted speakers or somebody else's assertion. A request to edit a fictional
first-person line does not make its content the user's biography.
operation is "set" for a positive assertion/current replacement, "deny" for an
explicit negative assertion, "withdraw" for a request to forget/remove the
target personal detail, or "no_preference" for an explicit assertion of having
no preference. Withdrawal is not a negative or a no-preference assertion.
value is the minimal value phrase copied exactly from the quoted source for set
or deny; use null for withdraw or no_preference. For enjoyment, copy the activity
name, not the words enjoy/do not enjoy. For a preferred item, copy the item name.
exact_quote must be a nonempty verbatim substring of that USER turn, including
enough context to establish the operation and its owner. Use one event per
relevant assertion/withdrawal, in original turn order. Retain later reassertions
even if the value repeats an earlier withdrawn value. Keep negative assertions
distinct from missing information. Ignore unrelated properties and assistant
messages. Acknowledgments, hypothetical suggestions, and requests to edit text
do not themselves assert the user's preference. Return an empty events list
when there are no relevant USER events. No markdown fences or extra commentary.'''

STATE_SYSTEM = '''Answer only the CURRENT QUESTION in at most 90 words. Continue
the supplied ANSWER prefix with plain answer text, without action markers.
The supplied state record is the sole evidence for this answer. Its property
names the subject of the record; a property label is not itself a positive fact.
For current scope, status "unknown" means the value is unknown, not No, dislike
or no preference. For status "known", polarity "positive" affirms the value,
"negative" explicitly denies that value, and "none" means the user explicitly
has no preference. Do not generalize a negative about one value to all values.
Answer the actual question using these distinctions, including yes/no questions.
Source-turn IDs identify support; they do not supply additional unstated facts.
For historical scope, report what the supplied original passage said, preserving
its speaker and historical scope rather than presenting it as current biography.
Do not reconstruct or repeat withdrawn values in current-scope explanations.
Give a concise answer and do not add unsupported details.'''


def archive_messages(history, query):
    spans = [source_span(history, i, 0, len(m['content'])) for i, m in enumerate(history)]
    return reader_messages(render_spans(spans), '', query)


def extraction_messages(history, property_name):
    archive = [{'turn': i, **m} for i, m in enumerate(history)]
    return [{'role': 'system', 'content': EXTRACT_SYSTEM},
            {'role': 'user', 'content': 'TARGET PROPERTY\n' + property_name +
             '\nARCHIVE\n' + json.dumps(archive, ensure_ascii=False)}]


def validate_events(raw, history):
    if type(raw) is not dict or set(raw) != {'events'} or type(raw['events']) is not list:
        raise ValueError('expected exactly one events list')
    bound = []; previous = -1; seen = set()
    for event in raw['events']:
        if type(event) is not list or len(event) != 5:
            raise ValueError('event must contain five fields')
        turn, owner, op, value, quote = event
        if type(turn) is not int or not 0 <= turn < len(history) or turn < previous:
            raise ValueError('turn absent or out of order')
        if history[turn]['role'] != 'user':
            raise ValueError('events must cite USER turns')
        if owner not in ('user', 'other') or op not in ('set', 'deny', 'withdraw', 'no_preference'):
            raise ValueError('invalid owner or operation')
        if type(quote) is not str or not quote or history[turn]['content'].count(quote) != 1:
            raise ValueError('quote must identify one exact source substring')
        if op in ('set', 'deny'):
            if type(value) is not str or not value or value not in quote:
                raise ValueError('value must be copied from the evidence quote')
        elif value is not None:
            raise ValueError('withdraw/no_preference requires null value')
        key = (turn, owner, op, value)
        if key in seen: raise ValueError('duplicate event')
        seen.add(key); previous = turn
        start = history[turn]['content'].index(quote)
        bound.append({'turn': turn, 'owner': owner, 'op': op, 'value': value,
                      'source': source_span(history, turn, start, start + len(quote))})
    return bound


def parse_events(text, history):
    try:
        # Duplicate object keys are malformed, not silently overwritten.
        def pairs(items):
            result = {}
            for key, value in items:
                if key in result: raise ValueError('duplicate JSON key')
                result[key] = value
            return result
        raw = json.loads(text, object_pairs_hook=pairs)
        return {'valid': True, 'events': validate_events(raw, history), 'error': None}
    except (ValueError, TypeError) as exc:
        return {'valid': False, 'events': [], 'error': str(exc)}


def resolve(events, property_name):
    state = {'scope': 'current', 'owner': 'user', 'property': property_name,
             'status': 'unknown', 'polarity': None, 'value': None, 'support_turns': []}
    for event in events:
        if event['owner'] != 'user': continue
        op = event['op']
        state.update(status='unknown' if op == 'withdraw' else 'known',
                     polarity={'set': 'positive', 'deny': 'negative',
                               'no_preference': 'none', 'withdraw': None}[op],
                     value=event['value'], support_turns=[event['turn']])
    return state


def record_for_question(state, history, question):
    if question['scope'] == 'historical':
        turn = question['target_turn']
        return {'scope': 'historical', 'property': question['property'],
                'original_passage': source_span(history, turn, 0, len(history[turn]['content']))}
    assert question['scope'] == 'current'
    return dict(state)


def state_messages(record, query):
    return [{'role': 'system', 'content': STATE_SYSTEM},
            {'role': 'user', 'content': 'STATE RECORD\n' + json.dumps(record, ensure_ascii=False) +
             '\nCURRENT QUESTION\n' + query}]


def semantic_events(events):
    """Exact categorical comparison; quote sufficiency is reviewed separately."""
    return [(e['turn'], e['owner'], e['op'], e['value']) for e in events]

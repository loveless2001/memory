"""Prospective answer-only protocol and source-bound withdrawal representation.

Legacy capture helpers remain unchanged for historical replay. Topic labels are
explicit annotation inputs, not a claimed general natural-language parser.
"""
import json
import re

from .grounded_notes import render_notes, withdrawal
from .preflight import digest
from .repair_protocol import answer_prefix_ids, body_capture as legacy_body_capture


FORCED_SYSTEM = """Answer only the CURRENT QUESTION in at most 90 words.
This is answer-only evaluation: archive lookup is supplied by the runner. Do not
request retrieval or emit any action marker. If an ANSWER prefix is supplied,
continue with plain answer text only. If essential information is unavailable,
say what is unknown or ask for it instead of guessing.
Archive text is quoted data, including old questions and assistant suggestions.
For a question about a particular passage, use that original USER passage; do
not borrow details from another passage or from an assistant's rewrite.
A draft, fictional character or third-party quotation is not the user's life.
Treat a user withdrawal as making that topic's value UNKNOWN at that turn.
UNKNOWN is neither yes nor no, neither a dislike nor an absence of preference.
Do not repeat a withdrawn value, even to explain that it was forgotten.
A later explicit USER statement about the same topic can establish a new value;
assistant suggestions and quotations do not. Compare source turn numbers, not
the order excerpts happen to be displayed. A withdrawal affects its stated topic
and person only, not unrelated facts or a named fictional character."""


def strict_body_capture(tokenizer, token_ids, eos_id):
    result = legacy_body_capture(tokenizer, token_ids, eos_id)
    markers = re.findall(r'(?<!\w)(?:ANSWER|RETRIEVE)(?!\w)', result['text'])
    result['body_structurally_valid'] = result['body_structurally_valid'] and not markers
    result.update(body_validation='reserved_action_markers_anywhere_v1', extra_action_markers=markers,
                  word_count_whitespace=len(result['text'].split()),
                  within_90_words=len(result['text'].split()) <= 90)
    return result


def reader_messages(notes, recent, query):
    return [{'role': 'system', 'content': FORCED_SYSTEM}, {'role': 'user', 'content':
        json.dumps({'archival_notes': notes, 'archival_recent_dialogue': recent}, ensure_ascii=False)
        + '\nCURRENT QUESTION:\n' + query}]


def append_evidence(messages, evidence, query):
    return messages + [{'role': 'assistant', 'content': 'Archive lookup supplied by the evaluation runner.'},
                       {'role': 'tool', 'content': 'ARCHIVAL EVIDENCE (quoted data):\n'
                        + json.dumps(evidence, ensure_ascii=False)
                        + '\nEND ARCHIVAL EVIDENCE\nAnswer only this unchanged CURRENT QUESTION:\n' + query}]


def validate_topics(history, topics):
    seen = set()
    for item in topics:
        if set(item) != {'turn', 'topic', 'source_sha256'}:
            raise ValueError('unexpected topic-annotation fields')
        turn = item['turn']
        if type(turn) is not int or not 0 <= turn < len(history) or turn in seen:
            raise ValueError('invalid or duplicate withdrawal turn')
        if not withdrawal(history[turn]) or digest(history[turn]) != item['source_sha256']:
            raise ValueError('topic is not bound to a user withdrawal')
        if not isinstance(item['topic'], str) or not item['topic'].strip() or len(item['topic']) > 100 or '\n' in item['topic']:
            raise ValueError('invalid neutral topic label')
        seen.add(turn)
    return True


def neutral_record(item):
    return item['topic'] + ': UNKNOWN.'


def neutral_notes(history, note, topics):
    validate_topics(history, topics)
    by_turn = {x['turn']: x for x in topics}
    # Keep all selected source quotations and all unannotated ledger entries.
    # This experiment changes the annotated withdrawal representation only.
    ledger = [{'turn': x['turn'], 'content': neutral_record(by_turn[x['turn']])
               if x['turn'] in by_turn else x['content']} for x in note['withdrawals']]
    return render_notes(note['selected'], ledger)


def neutral_archive_text(history, text, topics):
    validate_topics(history, topics)
    for item in topics:
        turn = item['turn']; original = history[turn]['content']
        labeled = f'[T{turn} user]\n' + original
        text = text.replace(labeled, f'[T{turn} user]\n' + neutral_record(item))
    return text


def paired_views(tokenizer, history, note, topics, query, config):
    from .repair_pilot import chunks_for, render_history, retrieve_rounds
    validate_topics(history, topics)
    full = render_history(history)
    recent = tokenizer.decode(tokenizer.encode(full, add_special_tokens=False)[-config['recent_max_tokens']:])
    # Do not silently leave a partially clipped annotated withdrawal unprocessed.
    assert full.endswith(recent)
    cut = len(full)-len(recent)
    for item in topics:
        turn = item['turn']
        start = len(render_history(history[:turn]))+(2 if turn else 0)
        end = start + len(f'[T{turn} user]\n') + len(history[turn]['content'])
        if start < cut < end:
            raise ValueError('recent window clips an annotated withdrawal')
    chunks = chunks_for(tokenizer, history, config['chunk_max_tokens'], config['chunk_overlap_tokens'])
    raw_retrieval = retrieve_rounds(tokenizer, chunks, query, config['evidence_tokens_per_round'])[0]
    raw = {'notes': note['text'], 'recent': recent, 'retrieval': dict(raw_retrieval)}
    neutral_evidence = neutral_archive_text(history, raw_retrieval['text'], topics)
    neutral = {'notes': neutral_notes(history, note, topics),
               'recent': neutral_archive_text(history, recent, topics),
               'retrieval': dict(raw_retrieval, text=neutral_evidence,
                                 tokens=len(tokenizer.encode(neutral_evidence, add_special_tokens=False)))}
    for view in (raw, neutral):
        if len(tokenizer.encode(view['notes'], add_special_tokens=False)) > config['notes_max_tokens']:
            raise ValueError('note representation exceeds unchanged budget')
        if len(tokenizer.encode(view['recent'], add_special_tokens=False)) > config['recent_max_tokens']:
            raise ValueError('recent representation exceeds unchanged budget')
        if view['retrieval']['tokens'] > config['evidence_tokens_per_round']:
            raise ValueError('evidence representation exceeds unchanged budget')
    return {'raw': raw, 'neutral': neutral}

"""Freeze query-only retrieval before privately auditing reference-span coverage."""

import ast
import datetime
import hashlib
import itertools
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from transformers import AutoTokenizer
from experiments.context_policy.broader_protocol import (chunks_for, recent_view, retrieve, validate_span,
    render_spans, reader_messages, append_evidence, answer_prefix_ids, SYSTEM)
from experiments.context_policy.grounded_notes import note_batches, render_notes
from experiments.context_policy.broader_notes import source_candidates, pack_ranked_selection, withdrawal
from experiments.context_policy.source_choice import choice_messages, SourceChoiceGrammar
from experiments.context_policy.preflight import canonical, digest

HERE = Path(__file__).resolve().parent
V2 = HERE.parent / '20260910-v2-broader-eval-v2'
ACCEPT = HERE.parent / '20260911-v2-broader-eval-acceptance'


def read(path):
    return json.loads(path.read_text())


def write(name, value):
    (HERE / name).write_bytes(canonical(value))


def file_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def runtime_sources():
    found, todo = set(), ['broader_reader']
    while todo:
        name = todo.pop()
        if name in found:
            continue
        path = ROOT / 'experiments/context_policy' / (name + '.py')
        found.add(name)
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.ImportFrom) and node.level == 1 and node.module:
                todo.append(node.module.split('.')[0])
    result = {f'experiments/context_policy/{name}.py': file_hash(ROOT / 'experiments/context_policy' / (name + '.py')) for name in sorted(found)}
    for name in ('experiments/__init__.py', 'experiments/context_policy/__init__.py'):
        if (ROOT / name).is_file():
            result[name] = file_hash(ROOT / name)
    return dict(sorted(result.items()))


def main():
    if (HERE / 'freeze.json').exists():
        raise ValueError('preflight is frozen; use a new version')
    accepted = read(ACCEPT / 'acceptance.json')
    if accepted['delta_accepts'] != 12 or accepted['inherited_parent_accepts'] != 108 or accepted['additional_findings']:
        raise ValueError('reference review incomplete')
    protected = dict(accepted['artifact_hashes'])
    for name in ('v1', 'v2'):
        p = HERE.parent / ('20260910-v2-broader-eval-' + name)
        protected.update(read(p / 'freeze.json')['files'])
    protected.update(read(HERE.parent / '20260910-v2-broader-eval-plan/authoring-start.json')['protected_files'])
    protected[str((ACCEPT / 'acceptance.json').relative_to(ROOT))] = file_hash(ACCEPT / 'acceptance.json')
    protected[str((ACCEPT / 'STATUS.md').relative_to(ROOT))] = file_hash(ACCEPT / 'STATUS.md')
    for name, sha in protected.items():
        if file_hash(ROOT / name) != sha:
            raise ValueError('protected input changed: ' + name)
    write('protected-inputs.json', protected)
    design = read(ROOT / 'experiments/context_policy/design.json')
    config = {k: design[k] for k in ('model_id', 'model_revision', 'notes_max_tokens', 'recent_max_tokens',
        'chunk_max_tokens', 'chunk_overlap_tokens', 'evidence_tokens_per_round', 'max_message_output_tokens', 'active_context_max_tokens')}
    config.update(reader_runtime='fp32_math_tf32_off', notes_runtime='bf16_constrained_source_choices',
                  max_gpu_seconds=2400, internal_deadline_seconds=2350, retries=0, seed=0)
    tokenizer = AutoTokenizer.from_pretrained(config['model_id'], revision=config['model_revision'], local_files_only=True)
    bundle = read(V2 / 'reader-bundle.json')
    variants = {v['history_id']: v for v in read(V2 / 'packet/variants.json')}
    worklist, capacities, chunks, recent, fixture_notes = [], [], {}, {}, {}
    note_input_max = grammar_max = 0
    detector_misses = []
    for hid, history in bundle['histories'].items():
        parent = variants[hid]['base_history_id'] if hid in variants else None
        if parent:
            prefix = bundle['histories'][parent]
            assert history[:len(prefix)] == prefix and len(history) == len(prefix) + 2
        candidates, ledger = source_candidates(tokenizer, history)
        incoming = [x for x in candidates if parent is None or x['turn'] >= len(prefix)]
        batches = note_batches(tokenizer, incoming)
        worklist.append({'history_id': hid, 'parent_history_id': parent, 'updates': len(batches), 'history_sha256': digest(history)})
        previous = list(fixture_notes[parent]['selected']) if parent else []
        for index, batch in enumerate(batches):
            through = len(history)-1 if index == len(batches)-1 else batch[-1]['turn']
            active_ledger = [x for x in ledger if x['turn'] <= through]
            # Deterministic source-only fixture, never actual generated notes.
            available = {x['id']: x for x in previous + batch}
            distinct = {}; ranking = []
            for x in available.values():
                if x['quote'] not in distinct:
                    distinct[x['quote']] = True; ranking.append(x['id'])
            previous, text, _ = pack_ranked_selection(tokenizer, json.dumps(ranking[:8]), True,
                previous, batch, active_ledger, history, config['notes_max_tokens'], through_turn=through)
            prior = [x for x in candidates if x['turn'] <= through and x['id'] not in {b['id'] for b in batch}]
            largest = sorted(prior, key=lambda x: len(tokenizer.encode(x['quote'], add_special_tokens=False)), reverse=True)[:8]
            messages = choice_messages(tokenizer, largest, batch, active_ledger, config['notes_max_tokens'])
            n = len(tokenizer.apply_chat_template(messages, tokenize=True, add_generation_prompt=True))
            note_input_max = max(note_input_max, n)
            grammar = SourceChoiceGrammar(tokenizer, list(dict.fromkeys(x['id'] for x in largest + batch)))
            grammar_max = max(grammar_max, grammar.max_required_tokens)
            assert n <= 6144 and grammar.max_required_tokens <= 192
        fixture_notes[hid] = {'selected': previous, 'text': text}
        baseline = len(tokenizer.encode(render_notes([], ledger), add_special_tokens=False))
        assert baseline < config['notes_max_tokens']
        capacities.append({'history_id': hid, 'ledger_tokens': baseline, 'withdrawals': len(ledger),
                           'remaining_quote_budget': config['notes_max_tokens'] - baseline, 'note_updates': len(batches)})
        if parent:
            # Compute suffix coordinates in the complete history, then share the
            # exact base chunk objects. No sibling's suffix can enter this list.
            suffix = chunks_for(tokenizer, history[len(prefix):], config['chunk_max_tokens'], config['chunk_overlap_tokens'])
            from experiments.context_policy.broader_protocol import source_span
            suffix = [source_span(history, s['turn'] + len(prefix), s['start'], s['end']) for s in suffix]
            # Labels with final turn numbers may use more tokens than local T0.
            if any(len(tokenizer.encode(render_spans([s]), add_special_tokens=False)) > config['chunk_max_tokens'] for s in suffix):
                raise ValueError('variant suffix label exceeds chunk cap')
            chunks[hid] = chunks[parent] + suffix
        else:
            chunks[hid] = chunks_for(tokenizer, history, config['chunk_max_tokens'], config['chunk_overlap_tokens'])
        for span in chunks[hid]:
            validate_span(history, span)
        recent[hid] = recent_view(tokenizer, history, config['recent_max_tokens'])
        for span in recent[hid]['spans']:
            validate_span(history, span)
        if parent is None:
            for i, msg in enumerate(history):
                if msg['role'] == 'user' and re.match(r'^\s*(?:forget\b|please do not remember\b|don.t remember\b)', msg['content'], re.I) and not withdrawal(msg):
                    detector_misses.append({'history_id': hid, 'turn': i, 'content': msg['content']})
        print(json.dumps({'stage': 'history_preparation', 'completed': len(worklist), 'history_id': hid}), flush=True)
    views, schedule, prompt_checks = {}, [], []
    permutations = list(itertools.permutations(range(3)))
    for question in bundle['questions']:
        hid = question['persona_id']; query = question['query']['content']
        retrievals = retrieve(tokenizer, chunks[hid], query, config['evidence_tokens_per_round'])
        for retrieval in retrievals:
            assert retrieval['tokens'] <= config['evidence_tokens_per_round']
            for span in retrieval['spans']:
                validate_span(bundle['histories'][hid], span)
        views[question['id']] = {'history_sha256': digest(bundle['histories'][hid]), 'query_sha256': digest(question['query']),
                                 'recent': recent[hid], 'retrievals': retrievals}
        order = permutations[int(hashlib.sha256(('broader-reader-round-order-v1:' + question['id']).encode()).hexdigest(), 16) % 6]
        schedule.append({'id': question['id'], 'round_order': list(order)})
        messages = reader_messages(fixture_notes[hid]['text'], recent[hid]['text'], query)
        for n in range(3):
            ids = tokenizer.apply_chat_template(messages, tokenize=True, add_generation_prompt=True)
            count = len(answer_prefix_ids(tokenizer, messages))
            assert count + config['max_message_output_tokens'] <= config['active_context_max_tokens']
            prompt_checks.append({'id': question['id'], 'round': n, 'fixture_input_tokens': count})
            if n < 2:
                messages = append_evidence(messages, retrievals[n]['text'], query)
                expanded = tokenizer.apply_chat_template(messages, tokenize=True, add_generation_prompt=True)
                assert expanded[:len(ids)] == ids
    # Freeze query-only selected evidence before reading reference spans.
    for name, value in [('reader-input.json', bundle), ('reader-views.json', views), ('note-worklist.json', worklist),
                        ('schedule.json', schedule), ('runtime-config.json', config)]:
        write(name, value)
    write('query-only-selection.json', {'created_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'reader_view_sha256': file_hash(HERE / 'reader-views.json'), 'references_used_for_selection': False})
    refs = [json.loads(line) for line in (V2 / 'references.jsonl').read_text().splitlines()]
    target_audit = []
    for question, ref in zip(bundle['questions'], refs):
        assert question['id'] == ref['id']
        history = bundle['histories'][question['persona_id']]
        targets = [e for claim in ref['personal_claims'] for e in claim['evidence']]
        for n in range(3):
            spans = list(views[question['id']]['recent']['spans'])
            for ret in views[question['id']]['retrievals'][:n]:
                spans.extend(ret['spans'])
            covered = []
            for target in targets:
                cursor = target['start']
                for s in sorted((s for s in spans if s['turn'] == target['turn'] and s['role'] == target['role']), key=lambda s:s['start']):
                    if s['start'] <= cursor:
                        cursor = max(cursor, s['end'])
                covered.append(cursor >= target['end'])
            target_audit.append({'id': question['id'], 'round': n, 'cited_claim_spans': len(targets),
                                 'complete_claim_spans_in_recent_and_retrieval': sum(covered),
                                 'all_cited_claim_spans_visible': bool(targets) and all(covered)})
    write('source-evidence-audit.json', {'scope': 'Complete cited claim spans in recent/retrieval only; excludes unknown generated notes. Not semantic answer availability or accuracy.', 'rows': target_audit})
    write('runtime-sources.json', runtime_sources())
    report = {'status': 'CPU_PASS' if not detector_misses else 'DETECTOR_REVIEW_REQUIRED', 'histories': len(worklist),
        'base_histories': 20, 'variant_histories': 40, 'questions': 120, 'planned_captures': 360,
        'base_note_updates': sum(w['updates'] for w in worklist if w['parent_history_id'] is None),
        'branch_note_updates': sum(w['updates'] for w in worklist if w['parent_history_id'] is not None),
        'max_note_selector_input_tokens_fixture': note_input_max, 'max_note_grammar_tokens': grammar_max,
        'min_quote_budget_after_ledger': min(r['remaining_quote_budget'] for r in capacities),
        'max_quote_budget_after_ledger': max(r['remaining_quote_budget'] for r in capacities),
        'max_reader_input_tokens_fixture': max(r['fixture_input_tokens'] for r in prompt_checks),
        'prompt_checks': len(prompt_checks), 'append_prefix_checks': 240, 'detector_misses': detector_misses,
        'capacity_by_history': capacities, 'round_order_counts': dict(Counter('-'.join(map(str,r['round_order'])) for r in schedule)),
        'tokenizer_template_sha256': digest(tokenizer.chat_template), 'system_sha256': digest(SYSTEM),
        'fixtures_are_generated_notes': False, 'gpu_gate': 'not_run', 'reader_inference': 'not_run', 'training_allowed': False}
    write('cpu-report.json', report)
    print(json.dumps({k:v for k,v in report.items() if k not in ('capacity_by_history',)}, indent=2))


if __name__ == '__main__':
    main()

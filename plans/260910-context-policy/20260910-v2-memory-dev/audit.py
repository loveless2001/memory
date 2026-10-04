"""Replay frozen evidence policy without a model, generation or action labels."""
import json
from collections import Counter
from pathlib import Path
from transformers import AutoTokenizer

from experiments.context_policy.personamem import sha256
from experiments.context_policy.relabel import canonical, validate_reference
from experiments.context_policy.repair_pilot import chunks_for, render_history, retrieve_rounds, validate_bundle

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]


def read(name):
    return json.loads((OUT / name).read_text())


def lines(name):
    return [json.loads(s) for s in (OUT / name).read_text().splitlines()]


def source_in_view(span, history, view):
    """Same user turn AND exact target fragment, not words anywhere in a view."""
    import re
    text = history[span['turn']]['content'][span['start']:span['end']]
    if view['kind'] == 'notes':
        return any(x['turn'] == span['turn'] and x['start'] <= span['start'] and x['end'] >= span['end']
                   for x in view['selected']) or (view['history_withdrawals'].get(span['turn']) == text)
    if view['kind'] == 'recent':
        # A clipped first turn is allowed only when its exact suffix survives;
        # derive its turn from the full rendered history, never a free-text match.
        full = render_history(history)
        suffix = view['text']
        assert full.endswith(suffix)
        full_start = len(full) - len(suffix)
        turn_start = len(render_history(history[:span['turn']])) + (2 if span['turn'] else 0)
        source_start = turn_start + len(f"[T{span['turn']} {span['role']}]\n") + span['start']
        return source_start >= full_start and text in suffix
    return any(x['turn'] == span['turn'] and x['role'] == span['role'] and text in x['content']
               for x in view['chunks'])


def main():
    freeze = read('freeze.json')
    for path, digest in freeze['files'].items():
        assert sha256((ROOT / path).read_bytes()) == digest, path
    previous = read('previous-artifact-hashes.json')
    for path, digest in previous.items():
        assert sha256((ROOT / path).read_bytes()) == digest, path
    bundle = read('reader-input.json'); validate_bundle(bundle)
    records = lines('records.jsonl'); refs = lines('references.jsonl'); packets = lines('audit-packets.jsonl')
    assert len(records) == len(refs) == len(packets) == 50
    for r, ref in zip(records, refs): validate_reference(r, ref)
    config = json.loads((ROOT / 'experiments/context_policy/design.json').read_text())
    tok_path = Path('/home/lenovo/.cache/huggingface/hub/models--Qwen--Qwen3-4B-Instruct-2507/snapshots') / config['model_revision']
    tokenizer = AutoTokenizer.from_pretrained(tok_path, local_files_only=True)
    notes = json.loads((ROOT / 'plans/260910-context-policy/20260910-v2-repair-r4/artifacts/notes.json').read_text())
    indexes = {pid: chunks_for(tokenizer, h, config['chunk_max_tokens'], config['chunk_overlap_tokens']) for pid, h in bundle['histories'].items()}
    audits, contexts = [], []
    for record, packet in zip(records, packets):
        pid = record['persona_id']; history = record['history']
        recent = tokenizer.decode(tokenizer.encode(render_history(history), add_special_tokens=False)[-config['recent_max_tokens']:])
        note = notes[pid]
        withdrawals = {i: m['content'] for i, m in enumerate(history) if m['role'] == 'user' and m['content'].lower().startswith('please forget') and f"[T{i} user withdrawal] {m['content']}" in note['text']}
        rounds = retrieve_rounds(tokenizer, indexes[pid], record['query']['content'], config['evidence_tokens_per_round'])
        by_id = {x['id']: x for x in indexes[pid]}
        views = [dict(kind='notes', selected=note['selected'], history_withdrawals=withdrawals), dict(kind='recent', text=recent)]
        views += [dict(kind='retrieval', chunks=[by_id[c] for c in r['chunk_ids']]) for r in rounds]
        spans = packet['required_spans']
        per_span = [[source_in_view(s, history, v) for v in views] for s in spans]
        states = [dict(state=name, required_source_spans=len(spans),
                       source_span_coverage=sum(any(row[:end]) for row in per_span),
                       complete_source_evidence=all(any(row[:end]) for row in per_span) if spans else None)
                  for name, end in [('notes_only', 1), ('notes_recent', 2), ('retrieval_1', 3), ('retrieval_2', 4)]]
        audits.append(dict(id=record['id'], persona_id=pid, kind=packet['kind'], states=states, required_spans=spans,
                           span_present_by_view=per_span, retrieval_tokens=[r['tokens'] for r in rounds],
                           semantic_review_status='pending', answer_accuracy=None, action_target=None))
        contexts.append(dict(id=record['id'], query=record['query']['content'], recent=recent, notes=note['text'], retrievals=rounds,
                             retrieval_chunks=[[by_id[c] for c in r['chunk_ids']] for r in rounds]))
    totals = {kind: {name: sum(a['states'][i]['complete_source_evidence'] is True for a in audits if a['kind'] == kind)
                    for i, name in enumerate(['notes_only', 'notes_recent', 'retrieval_1', 'retrieval_2'])}
              for kind in ('fact_recall', 'withdrawal')}
    for name, value in [('availability.json', audits), ('contexts.json', contexts)]:
        (OUT / name).write_bytes(canonical(value))
    summary = dict(counts=dict(Counter(a['kind'] for a in audits)), source_span_coverage=totals,
                   frozen_files_verified=len(freeze['files']), previous_files_unchanged=len(previous), references_validated=50,
                   source_groups=10, reference_words_max=max(len(r['answer'].split()) for r in refs),
                   tokenizer_files={p.name: sha256(p.read_bytes()) for p in tok_path.iterdir() if p.is_file()},
                   audit_script_sha256=sha256(Path(__file__).read_bytes()), reader_generation=False, training_exported=False,
                   charges_usd=0, semantic_review='pending', limitations='Exact required source spans only. No answer correctness or independent evaluation claim.')
    (OUT / 'availability-summary.json').write_bytes(canonical(summary))
    print(json.dumps({k: v for k, v in summary.items() if k != 'tokenizer_files'}))


if __name__ == '__main__': main()

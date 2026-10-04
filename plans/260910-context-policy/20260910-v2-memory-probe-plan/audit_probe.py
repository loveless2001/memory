"""Verify collection against the prelaunch freeze and CPU evidence replay."""
import json
from pathlib import Path
from transformers import AutoTokenizer
from experiments.context_policy.preflight import canonical, digest
from experiments.context_policy.personamem import sha256
from experiments.context_policy.memory_probe import validate_reused_notes
from experiments.context_policy.repair_protocol import reader_messages, append_retrieval, answer_prefix_ids, body_capture

ROOT = Path(__file__).resolve().parents[3]
PLAN = Path(__file__).resolve().parent
RUN = PLAN.parent / '20260910-v2-memory-probe'
DATA = PLAN.parent / '20260910-v2-memory-dev'


def main():
    def read(p): return json.loads(p.read_text())
    frozen = read(PLAN / 'freeze.json')
    for name, expected in frozen['files'].items():
        # Historical source identity is its launch snapshot. Root status docs
        # may advance after completion; frozen data/references stay in place.
        path = RUN / 'source-snapshot' / name if name in frozen['source_files'] else ROOT / name
        assert sha256(path.read_bytes()) == expected, name
    launch = read(RUN / 'launch.json'); artifacts = RUN / 'artifacts'
    assert launch['source_files'] == frozen['source_files']
    assert launch['source_sha256'] == digest(launch['source_files']) == frozen['source_sha256']
    for name, expected in launch['source_files'].items():
        assert sha256((RUN / 'source-snapshot' / name).read_bytes()) == expected
    hashes = read(artifacts / 'artifact-hashes.json')
    for name, expected in hashes.items(): assert sha256((artifacts / name).read_bytes()) == expected
    manifest = read(artifacts / 'manifest.json')
    assert manifest['source_files'] == launch['source_files']
    assert manifest['reader_input_sha256'] == launch['reader_input_sha256'] == sha256((DATA / 'reader-input.json').read_bytes())
    notes_path = PLAN.parent / '20260910-v2-repair-r4/artifacts/notes.json'
    assert manifest['reused_notes_sha256'] == launch['reused_notes_sha256'] == sha256(notes_path.read_bytes())
    assert manifest['no_references_mounted'] is True
    tokenizer = AutoTokenizer.from_pretrained('Qwen/Qwen3-4B-Instruct-2507',
        revision='cdbee75f17c01a7cc42f958dc650907174af0554', local_files_only=True)
    note_check = validate_reused_notes(tokenizer, read(DATA / 'reader-input.json'), read(notes_path))
    assert note_check == read(artifacts / 'reused-note-checks.json')
    gates = read(artifacts / 'transcript-checks.json')
    assert len(gates) == 40 and all(x['equal'] and all(x['append_argmax_equal']) and x['cached_tokens'] == x['fresh_tokens'] for x in gates)
    captures = read(artifacts / 'captures.json')
    contexts = read(DATA / 'contexts.json')
    assert len(captures) == 150
    verified = []
    for index, context in enumerate(contexts):
        messages = reader_messages(context['notes'], context['recent'], context['query'])
        for n in range(3):
            capture = captures[3*index+n]
            assert capture['id'] == context['id'] and capture['retrieval_rounds'] == n
            assert capture['messages'] == messages
            assert capture['retrieval'] == context['retrievals'][:n]
            ids = answer_prefix_ids(tokenizer, messages)
            assert len(ids) == capture['input_tokens']
            check = body_capture(tokenizer, capture['token_ids'], tokenizer.eos_token_id)
            assert all(capture[k] == v for k, v in check.items())
            assert 1 <= len(capture['token_ids']) <= 192
            assert capture['actual_forwarded_tokens'] == len(ids) + len(capture['token_ids']) - int(capture['ended_at_eos'])
            verified.append(dict(id=capture['id'], round=n, capture_sha256=digest(capture),
                                 exact_cpu_context_match=True, word_count=len(capture['text'].split())))
            if n < 2: messages = append_retrieval(messages, context['retrievals'][n]['text'], context['query'])
    result = dict(status='pass', snapshots_verified=len(launch['source_files']), frozen_files_verified=len(frozen['files']),
                  remote_artifact_hashes_verified=len(hashes), cache_checks=40, note_check=note_check,
                  capture_view_token_checks=len(verified), captures=verified, training_performed=False)
    (RUN / 'source-capture-verification.json').write_bytes(canonical(result))
    print(json.dumps({k: v for k, v in result.items() if k != 'captures'}))


if __name__ == '__main__': main()

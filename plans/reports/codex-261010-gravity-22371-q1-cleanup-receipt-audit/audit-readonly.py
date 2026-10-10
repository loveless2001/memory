"""Independent Q1-only receipt audit. Read-only remote APIs; local audit output only."""
from pathlib import Path
from datetime import datetime, timezone
import ast
import hashlib
import json
import os
import shutil
import subprocess
import modal

ROOT = Path('/home/lenovo/projects/memory')
OUT = Path(__file__).resolve().parent
REVIEW = ROOT / 'plans/reports/codex-261010-gravity-22360-closing-cleanup-review'
OWNER = ROOT / 'plans/reports/claude-261010-0030-m4-sgm-qwen-line-cleanup-receipt'
VOL = 'memsub-m4-sgm-p2p5-b2-occupied-fill-long-v1'

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def save(name, data):
    (OUT / name).write_text(json.dumps(data, indent=2) + '\n')

def cli(*args):
    return json.loads(subprocess.check_output([str(ROOT / '.venv/bin/python'), '-m', 'modal', *args, '--json'], text=True))

# Load only the type codec functions, without executing the original capture.
tree = ast.parse((REVIEW / 'capture-readonly.py').read_text())
ns = {'base64': __import__('base64')}
defs = ast.Module(body=[n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in ('encode', 'decode')], type_ignores=[])
exec(compile(defs, 'retained-type-codec', 'exec'), ns)
encode = ns['encode']

receipt = [json.loads(x) for x in (OWNER / 'receipt.jsonl').read_text().splitlines()]
summary = json.loads((OWNER / 'summary.json').read_text())
assert summary['approved_ids'] == ['Q1'] and summary['dry_run'] is False
assert summary['status'] == 'OK' and set(summary['results']) == {'Q1'}
assert [r['step'] for r in receipt] == ['prechecks', 'Q1-delete']
assert receipt[1]['path'] == str(ROOT / '.venv-gpu')
assert not os.path.lexists(ROOT / '.venv-gpu')
delta = receipt[1]['disk_free_after'] - receipt[1]['disk_free_before']
assert delta == 64651264
owner_hashes = {}
for name in ['receipt.jsonl', 'summary.json', 'q1-run.log', 'q1-space-note.txt', 'qwen-line-cleanup-approved-q1-q3-q4.py']:
    src = OWNER / name
    owner_hashes[name] = sha(src)
    shutil.copyfile(src, OUT / name)
save('owner-artifact-hashes.json', owner_hashes)

manifest = json.loads((REVIEW / 'manifest.json').read_text())
for row in manifest['files']:
    assert sha(REVIEW / row['path']) == row['sha256'], row['path']
save('retained-backup-integrity.json', {'manifest_sha256': sha(REVIEW / 'manifest.json'), 'files_verified': len(manifest['files']), 'status': 'PASS'})

paths = [ROOT / '.venv-gpu', ROOT / '.venv', Path('/home/lenovo/.cache/uv'), Path('/home/lenovo/.cache/huggingface/hub/models--Qwen--Qwen3-0.6B-Base'), Path('/home/lenovo/projects/memory-occupied-fill-v1-worktree')]
save('local-state.json', [{'path': str(p), 'exists': p.exists(), 'lexists': os.path.lexists(p), 'resolved': str(p.resolve())} for p in paths])
assert all(p.exists() for p in paths[1:])

apps = cli('app', 'list')
dicts = cli('dict', 'list')
volumes = cli('volume', 'list')
save('apps-live.json', apps)
save('dicts-live.json', dicts)
save('volumes-live.json', volumes)
assert VOL in {x['name'] for x in volumes}
assert 'memsub-artifacts' in {x['name'] for x in volumes}

vol = modal.Volume.from_name(VOL, create_if_missing=False)
listing = sorted([{'path': x.path, 'type': x.type.name, 'mtime': x.mtime, 'size': x.size} for x in vol.iterdir('/', recursive=True)], key=lambda x: x['path'])
save('q3-live-list.json', listing)
assert listing == json.loads((REVIEW / 'q3-remote-list-before.json').read_text())
q3 = []
for row in json.loads((REVIEW / 'q3-file-verification.json').read_text()):
    h = hashlib.sha256()
    size = 0
    for chunk in vol.read_file(row['path']):
        h.update(chunk)
        size += len(chunk)
    assert h.hexdigest() == row['sha256'] and size == row['size'], row['path']
    q3.append({'path': row['path'], 'bytes': size, 'sha256': h.hexdigest(), 'matches_retained': True})
save('q3-live-file-hashes.json', q3)
print('Q3: all 14 live files still match the retained mirror', flush=True)

whitelist = json.loads((REVIEW / 'q4-name-whitelist.json').read_text())
index = {x['name']: x for x in json.loads((REVIEW / 'q4-export-index.json').read_text())}
assert len(whitelist) == 38 and set(whitelist) <= {x['name'] for x in dicts}
q4 = []
for name in whitelist:
    d = modal.Dict.from_name(name, create_if_missing=False)
    items = [{'key': encode(k), 'value': encode(v)} for k, v in d.items()]
    old = json.loads((REVIEW / 'q4-dicts' / (name + '.json')).read_text())
    assert d.object_id == index[name]['object_id']
    assert items == old['items'], name
    q4.append({'name': name, 'object_id': d.object_id, 'entry_count': len(items), 'matches_retained': True})
save('q4-live-verification.json', q4)
save('audit-summary.json', {'capture_utc': datetime.now(timezone.utc).isoformat(), 'authorization_message': 22370, 'approved_ids': ['Q1'], 'receipt_status': 'OK', 'q1_absent': True, 'retained_backup_files_verified': len(manifest['files']), 'q3_live_files_verified': len(q3), 'q3_live_bytes_verified': sum(x['bytes'] for x in q3), 'q4_live_dicts_verified': len(q4), 'q4_live_entries_verified': sum(x['entry_count'] for x in q4), 'memsub_artifacts_listed': True, 'filesystem_free_delta_from_receipt_bytes': delta, 'remote_mutations': 0, 'compute_dispatches': 0})
print((OUT / 'audit-summary.json').read_text(), flush=True)

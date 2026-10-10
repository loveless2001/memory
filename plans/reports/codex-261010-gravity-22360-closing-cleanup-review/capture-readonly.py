"""Read-only Modal metadata/backups for Q3/Q4 review; no remote mutation or compute."""
import base64
import datetime
import hashlib
import json
import subprocess
import zipfile
from pathlib import Path, PurePosixPath

import modal

ROOT = Path('/home/lenovo/projects/memory')
OUT = Path(__file__).resolve().parent
VOL = 'memsub-m4-sgm-p2p5-b2-occupied-fill-long-v1'
OUT.mkdir(parents=True, exist_ok=True)

def save(name, data):
    (OUT / name).write_text(json.dumps(data, indent=2) + '\n')

def cli(*args):
    return json.loads(subprocess.check_output([str(ROOT / '.venv/bin/python'), '-m', 'modal', *args], text=True))

def encode(x):
    if x is None: return {'t': 'none'}
    if isinstance(x, bool): return {'t': 'bool', 'v': x}
    if isinstance(x, str): return {'t': 'str', 'v': x}
    if isinstance(x, int): return {'t': 'int', 'v': str(x)}
    if isinstance(x, float): return {'t': 'float', 'v': repr(x)}
    if isinstance(x, bytes): return {'t': 'bytes', 'v': base64.b64encode(x).decode()}
    if isinstance(x, (tuple, list, set)): return {'t': type(x).__name__, 'v': [encode(y) for y in x]}
    if isinstance(x, dict): return {'t': 'dict', 'v': [[encode(k), encode(v)] for k, v in x.items()]}
    raise TypeError(f'Unsupported export type: {type(x).__name__}')

def decode(x):
    t = x['t']
    if t == 'none': return None
    if t in ('str', 'bool'): return x['v']
    if t == 'int': return int(x['v'])
    if t == 'float': return float(x['v'])
    if t == 'bytes': return base64.b64decode(x['v'])
    if t in ('tuple', 'list', 'set'): return {'tuple': tuple, 'list': list, 'set': set}[t](decode(y) for y in x['v'])
    if t == 'dict': return {decode(k): decode(v) for k, v in x['v']}
    raise ValueError(t)

apps = cli('app', 'list', '--json')
save('apps-live.json', apps)
assert not any(x.get('state') != 'stopped' for x in apps), 'Active apps: capture halted before backup.'
dicts = cli('dict', 'list', '--json')
save('dicts-all.json', dicts)
names = sorted(x['name'] for x in dicts if x['name'].startswith(('m4-sgm-p2p5-', 'memsub-m4-sgm-p2p5-')))
assert len(names) == 38, f'Q4 whitelist changed: {len(names)}'
save('q4-name-whitelist.json', names)

vol = modal.Volume.from_name(VOL, create_if_missing=False)
def listing():
    return sorted([{'path': x.path, 'type': x.type.name, 'mtime': x.mtime, 'size': x.size}
                   for x in vol.iterdir('/', recursive=True)], key=lambda x: x['path'])
before = listing()
save('q3-remote-list-before.json', before)
assert sum(x['size'] for x in before if x['type'] == 'FILE') < 64 * 2**20, 'Unexpected Q3 size.'
copied = []
for entry in before:
    rel = PurePosixPath(entry['path'].lstrip('/'))
    assert '..' not in rel.parts and rel.parts[0] == 'b2-run-v1', str(rel)
    dst = OUT / 'q3-complete-volume' / str(rel)
    if entry['type'] == 'DIRECTORY':
        dst.mkdir(parents=True, exist_ok=True)
        continue
    assert entry['type'] == 'FILE', f'Unexpected entry type: {entry}'
    dst.parent.mkdir(parents=True, exist_ok=True)
    h = hashlib.sha256()
    with dst.open('wb') as f:
        for chunk in vol.read_file(entry['path']):
            f.write(chunk); h.update(chunk)
    assert dst.stat().st_size == entry['size'], str(rel)
    row = {**entry, 'sha256': h.hexdigest(), 'size_match': True}
    if dst.suffix == '.json': json.loads(dst.read_text()); row['json_parse'] = True
    if dst.suffix == '.pt':
        with zipfile.ZipFile(dst) as z: assert z.testzip() is None
        row['zip_crc'] = 'PASS'
    existing = [Path('/home/lenovo/projects/memory-occupied-fill-v1-worktree/plans/261009-1135-m4-sgm-p2p5-b2-occupied-fill-long-run/b2-resume-v1/volume') / str(rel),
                ROOT / 'plans/reports/codex-261009-gravity-wait42-b2-resume-terminal-audit/volume' / str(PurePosixPath(*rel.parts[1:]))]
    row['existing_matching_copies'] = [str(p) for p in existing if p.is_file() and hashlib.sha256(p.read_bytes()).hexdigest() == row['sha256']]
    copied.append(row)
save('q3-file-verification.json', copied)
after = listing(); save('q3-remote-list-after.json', after)
assert before == after, 'Remote Q3 listing changed during capture.'
exports = []
(OUT / 'q4-dicts').mkdir(exist_ok=True)
for name in names:
    d = modal.Dict.from_name(name, create_if_missing=False)
    rows = list(d.items())
    items = [{'key': encode(k), 'value': encode(v)} for k, v in rows]
    assert all((decode(x['key']), decode(x['value'])) == old for x, old in zip(items, rows))
    doc = {'name': name, 'object_id': d.object_id, 'format': 'typed-json-kv-v1', 'entry_count': len(items), 'items': items}
    file = OUT / 'q4-dicts' / (name + '.json')
    file.write_text(json.dumps(doc, indent=2) + '\n')
    assert json.loads(file.read_text()) == doc
    exports.append({'name': name, 'object_id': d.object_id, 'entry_count': len(items), 'sha256': hashlib.sha256(file.read_bytes()).hexdigest(), 'round_trip': 'PASS'})
save('q4-export-index.json', exports)
save('capture-summary.json', {'capture_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'volume': VOL,
                             'q3_files': len(copied), 'q3_bytes': sum(x['size'] for x in copied),
                             'q3_listing_stable': True, 'q3_files_without_old_matching_copy': [x['path'] for x in copied if not x['existing_matching_copies']],
                             'q4_dicts': len(exports), 'q4_entries': sum(x['entry_count'] for x in exports),
                             'remote_mutations': 0, 'compute_dispatches': 0})
print((OUT / 'capture-summary.json').read_text())

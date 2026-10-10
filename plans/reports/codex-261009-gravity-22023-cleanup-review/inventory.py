"""Read-only B/C cleanup inventory. Writes review manifests only; never deletes files."""
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
PROBE = Path('plans/261008-0144-m4-sgm-p2p5-readout-recipe-rescue-probe')
CELLS = PROBE / 'p2p5-readout-probe-v1/taskhead-learned-n32/volume-evidence/collect-1/taskhead-learned-n32/cells'
OLD_AUDIT = Path('plans/reports/codex-261008-p2p5-pk-21911-run-check')
INDEX = Path('plans/reports/claude-261008-2350-p2p5-taskhead-dead-start-address-diagnosis/inputs-index.json')


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def file_record(rel):
    path = ROOT / rel
    assert path.is_file() and not path.is_symlink(), rel
    st = path.stat()
    return {'path': str(rel), 'bytes': st.st_size, 'allocated_bytes': st.st_blocks * 512,
            'device': st.st_dev, 'inode': st.st_ino, 'nlink': st.st_nlink, 'sha256': sha(path)}


protected = {}
def protect(rel, reason):
    protected.setdefault(str(rel), []).append(reason)


idx = json.loads((ROOT / INDEX).read_text())
for entry in idx['entries']:
    for key in ['manifest', 'telemetry', 'params']:
        rel = entry.get(key)
        if rel and rel != 'init':
            protect(rel, 'frozen diagnosis input: ' + entry['name'])
            expected = entry.get(key + '_sha256')
            if expected:
                assert sha(ROOT / rel) == expected, rel

old = json.loads((ROOT / OLD_AUDIT / 'final-review-evidence.json').read_text())
for row in old['crc_checks']:
    protect(CELLS / row['cell'] / 'epoch-1' / row['file'], 'original damaged-download evidence')
    protect(OLD_AUDIT / 'supplemental-remote-checkpoints' / row['cell'] / row['file'], 'verified supplemental counterpart')
for cell in sorted((ROOT / CELLS).iterdir()):
    for step, reason in [(50, 'earliest saved probe trajectory checkpoint'), (1500, 'final full optimizer/RNG checkpoint')]:
        paths = list((cell / 'epoch-1').glob(f'gen-*-step{step}.pt'))
        assert len(paths) == 1
        protect(paths[0].relative_to(ROOT), reason)

candidates = []
for path in sorted((ROOT / CELLS).glob('*/epoch-1/gen-*.pt')):
    rel = path.relative_to(ROOT)
    if str(rel) not in protected:
        candidates.append({'group': 'B-review', 'reason': 'intermediate real probe training state; removal loses replay/resume at this step', **file_record(rel)})

fixture_dirs = []
for name in ['84f0a69', 'd62602c', 'de656de', 'e1632cb']:
    root = Path('plans/reports') / ('codex-261007-p2p5-pk-' + name)
    subnames = ['pytest-tmp', 'rejection-probes'] + (['rejection-probes-run2'] if name == '84f0a69' else [])
    for subname in subnames:
        relroot = root / subname
        assert (ROOT / relroot).is_dir()
        fixture_dirs.append(str(relroot))
        for path in sorted((ROOT / relroot).rglob('*')):
            if path.is_file() and not path.is_symlink() and path.suffix in {'.pt', '.safetensors'}:
                rel = path.relative_to(ROOT)
                assert str(rel) not in protected
                candidates.append({'group': 'C-recommended', 'reason': 'generated CPU test/rejection fixture tensor; retain source tests and non-tensor evidence', **file_record(rel)})

tracked = set(subprocess.check_output(['git', 'ls-files', '-z'], cwd=ROOT).decode().split('\0'))
assert all(row['path'] not in tracked for row in candidates)
assert len({row['path'] for row in candidates}) == len(candidates)
protected_rows = []
for rel, reasons in sorted(protected.items()):
    protected_rows.append({**file_record(Path(rel)), 'reasons': reasons})
for group in ['B-review', 'C-recommended']:
    rows = [r for r in candidates if r['group'] == group]
    (HERE / (group + '.jsonl')).write_text(''.join(json.dumps(row, sort_keys=True) + '\n' for row in rows))
    (HERE / (group + '.paths.txt')).write_text(''.join(row['path'] + '\n' for row in rows))
(HERE / 'protected-files.json').write_text(json.dumps(protected_rows, indent=2) + '\n')
summary = {'observed_utc': datetime.now(timezone.utc).isoformat(), 'deleted_files': 0,
           'candidate_files_all_untracked': True, 'groups': {}, 'C_fixture_roots': fixture_dirs,
           'protected_prefixes': ['plans/261009-0030-m4-sgm-p2p5-taskhead-read-escape-blocker-screen', str(PROBE / 'smoke')],
           'protected_input_index': str(INDEX), 'preserve_non_tensor_evidence': True,
           'preserve_source_tests_and_runners': True, 'scope': 'exact B/C candidate manifests only; no other project inventoried here'}
for group in ['B-review', 'C-recommended']:
    rows = [r for r in candidates if r['group'] == group]
    summary['groups'][group] = {'files': len(rows), 'bytes': sum(r['bytes'] for r in rows),
                                'GiB': sum(r['bytes'] for r in rows) / 2**30,
                                'allocated_bytes': sum(r['allocated_bytes'] for r in rows),
                                'hardlink_count_distribution': dict(Counter(r['nlink'] for r in rows))}
summary['protected_files'] = len(protected_rows)
(HERE / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
print(json.dumps(summary, indent=2))

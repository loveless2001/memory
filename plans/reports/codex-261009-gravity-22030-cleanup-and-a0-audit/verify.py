"""Read-only receipt and returned A0 verification. No model forward or deletion."""
import hashlib
import importlib.util
import json
import os
from collections import defaultdict
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
RECEIPT = ROOT / 'plans/reports/claude-261009-0237-gravity-cleanup-receipt'
INVENTORY = ROOT / 'plans/reports/codex-261009-gravity-22023-cleanup-review'
P = ROOT / 'plans/261009-0030-m4-sgm-p2p5-taskhead-read-escape-blocker-screen'


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def sums(path, base):
    checks = {}
    for line in path.read_text().splitlines():
        digest, rel = line.split(maxsplit=1)
        assert sha(base / rel) == digest, rel
        checks[rel] = digest
    return checks


record = {'observed_utc': datetime.now(timezone.utc).isoformat(), 'deleted_by_audit': 0,
          'model_forwards': 0, 'paid_calls': 0}
record['receipt_hashes'] = sums(RECEIPT / 'SHA256SUMS.txt', RECEIPT)
record['inventory_hashes'] = sums(INVENTORY / 'SHA256SUMS.txt', ROOT)
record['stage_a_package_hashes'] = sums(P / 'SHA256SUMS-stage-a-package-v0.4.txt', ROOT)
rows = [json.loads(x) for x in (RECEIPT / 'receipt.jsonl').read_text().splitlines()]
summary = json.loads((RECEIPT / 'summary.json').read_text())
assert len({r['path'] for r in rows}) == len(rows)
tracked = set(subprocess.check_output(['git', 'ls-files', '-z'], cwd=ROOT).decode().split('\0'))
grouped = defaultdict(list)
for r in rows:
    rel = Path(r['path'])
    assert not rel.is_absolute() and '..' not in rel.parts
    assert not os.path.lexists(ROOT / rel), rel
    assert str(rel) not in tracked, rel
    assert r['group'] in {'A', 'B', 'C', 'D'}
    grouped[r['group']].append(r)
    if r['group'] == 'A':
        assert rel.parts[:2] == ('plans', '261006-1345-m4-sgm-p2p5-qwen3-0p6b-screen')
        assert rel.name.startswith('gen-') and rel.suffix == '.pt'
    elif r['group'] == 'D':
        assert rel.parts[0] == 'plans' and rel.parts[1][:4] in {'2607', '2609'}
        assert rel.suffix in {'.pt', '.safetensors', '.bin', '.npy', '.npz'}
for group, name in [('B', 'B-review'), ('C', 'C-recommended')]:
    expected = {r['path']: (r['bytes'], r['sha256']) for r in
                map(json.loads, (INVENTORY / (name + '.jsonl')).read_text().splitlines())}
    actual = {r['path']: (r['bytes'], r['sha256']) for r in grouped[group]}
    assert actual == expected, group
group_totals = {g: {'files': len(rs), 'bytes': sum(r['bytes'] for r in rs)} for g, rs in grouped.items()}
assert group_totals == summary['deleted_by_group']
assert len(rows) == summary['deleted_files'] == 12591
assert sum(r['bytes'] for r in rows) == summary['deleted_bytes'] == 16533920717
protected = json.loads((INVENTORY / 'protected-files.json').read_text())
deleted = {r['path'] for r in rows}
for r in protected:
    assert r['path'] not in deleted and sha(ROOT / r['path']) == r['sha256'], r['path']
assert len(protected) == summary['protected_checked'] == 30
assert not summary['skipped'] and not summary['protected_problems']
assert all(not r['path'].startswith('plans/261009-0030-m4-sgm-p2p5-taskhead-read-escape-blocker-screen') for r in rows)
changes = subprocess.check_output(['git', 'diff', '--name-only', 'fe43fc9', 'c3651b1'], cwd=ROOT, text=True).splitlines()
assert len(changes) == 4 and all(x.startswith('plans/reports/claude-261009-0237-gravity-cleanup-receipt/') for x in changes)
record['cleanup'] = {'groups': group_totals, 'files_confirmed_absent': len(rows), 'B_C_exact_manifest_match': True,
                     'protected_hashes_verified': len(protected), 'deleted_logical_bytes': summary['deleted_bytes'],
                     'recorded_free_space_increase_bytes': summary['disk_free_after'] - summary['disk_free_before'],
                     'before_free_bytes_recorded': summary['disk_free_before'], 'after_free_bytes_recorded': summary['disk_free_after'],
                     'git_changes': changes, 'limitations': 'A/D predeletion hashes and filesystem-before reading are receipt evidence; not independently observed before deletion.'}

spec = importlib.util.spec_from_file_location('stage_a_train_audit', ROOT / 'scripts/sgm-p2p5-taskhead-read-escape-stage-a-train.py')
t = importlib.util.module_from_spec(spec)
spec.loader.exec_module(t)
arm = P / 'stage-a-run-v1/A0'
telemetry = [json.loads(x) for x in (arm / 'routing_telemetry.jsonl').read_text().splitlines()]
result = json.loads((arm / 'stage_a_result.json').read_text())
assert result == {'arm': 'A0', **t.classify(telemetry)}
assert result['status'] == 'valid' and result['band_at_100'] == 'escaped'
manifest = json.loads((arm / 'run_manifest.json').read_text())
probe_path = P / 'inputs/probe-taskhead-learned-n32-s0-run_manifest.json'
probe = json.loads(probe_path.read_text())
assert sha(probe_path) == manifest['probe_manifest_sha256'] == t.PROBE_S0_MANIFEST_SHA256
assert manifest['pilot_config'] == json.loads(json.dumps(asdict(t.arm_config(probe['pilot_config'], 'A0', 'cuda'))))
assert manifest['memsub_source_sha256'] == probe['memsub_source_sha256']
assert manifest['dev_seed'] == 4242 and manifest['stage_a'] == {'arm': 'A0', 'overrides': {}}
assert manifest['tf32'] == {'matmul': False, 'cudnn': False}
assert manifest['versions']['torch'] == '2.7.1+cu126' and manifest['versions']['transformers'] == '4.55.2'
assert sha(arm / 'trained_parameters.safetensors') == manifest['trained_parameters_sha256']
run = json.loads((P / 'stage-a-run-v1/run.json').read_text())
assert run['arms']['A0']['returncode'] == 0
assert run['deadline'] == 1791491100.2921758 and run['app_id'] == 'ap-cCYlrnTz0Tj7tcm7TYovau'
record['A0'] = {'recomputed_result': result, 'manifest_bound': True, 'wall_s': run['arms']['A0']['wall_s'],
                'artifact_hashes': {str(f.relative_to(ROOT)): sha(f) for f in sorted(arm.iterdir()) if f.is_file()},
                'other_arms_returned': [k for k in run['arms'] if k != 'A0'],
                'terminal_markers': {str(name): (P / name).exists() for name in
                                     ['stage-a-run-v1.exit.txt', 'stage-a-run-v1.cleanup-exit.txt', 'stage-a-run-v1/cleanup.json']}}
(HERE / 'verification.json').write_text(json.dumps(record, indent=2) + '\n')
print(json.dumps({'cleanup': record['cleanup'], 'A0': result, 'terminal_markers': record['A0']['terminal_markers']}, indent=2))

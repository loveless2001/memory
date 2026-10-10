"""Read-only terminal/index audit. No model loading, training or remote compute."""
from dataclasses import asdict
from decimal import Decimal
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
P = ROOT / 'plans/261009-0030-m4-sgm-p2p5-taskhead-read-escape-blocker-screen'
OUT = P / 'stage-a-run-v1'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sums(path, base):
    rows = {}
    for line in path.read_text().splitlines():
        want, rel = line.split(maxsplit=1)
        assert sha(base / rel) == want, rel
        rows[rel] = want
    return rows


record = {'observed_utc': datetime.now(timezone.utc).isoformat(), 'model_forwards': 0, 'paid_compute_calls': 0}
record['terminal_payload_hashes'] = sums(P / 'stage-a-run-v1.SHA256SUMS-terminal.txt', P)
record['binary_hashes'] = sums(P / 'stage-a-run-v1.SHA256SUMS-binaries-not-in-git.txt', P)
record['launch_package_hashes'] = sums(P / 'SHA256SUMS-stage-a-package-v0.4.txt', ROOT)
assert len(record['terminal_payload_hashes']) == 20 and len(record['binary_hashes']) == 2
client_exit = (P / 'stage-a-run-v1.exit.txt').read_text().strip()
cleanup_exit = (P / 'stage-a-run-v1.cleanup-exit.txt').read_text().strip()
assert client_exit.split()[0] == '124' and cleanup_exit.split()[0] == '0'
run = json.loads((OUT / 'run.json').read_text())
assert run['outcome'] == 'error: SystemExit: SIGTERM (outer timeout)'
assert run['deadline'] == 1791491100.2921758 and run['app_id'] == 'ap-cCYlrnTz0Tj7tcm7TYovau'
cleanup = json.loads((OUT / 'cleanup.json').read_text())
assert cleanup['app_id'] == run['app_id'] and cleanup['status'] == 'stopped_verified'
assert cleanup['checks'][-1]['verified'] is True
live = json.loads((HERE / 'live-terminal-state.json').read_text())
assert live['independent_shutdown_verified'] is True
assert live['starts']['data']['A2'] is None
starts = json.loads((P / 'stage-a-run-v1.starts-dict-after.json').read_text())
assert set(starts) == {'deadline', 'A0', 'A1'}
assert starts['deadline'] == run['deadline']
assert all(starts[a] == live['starts']['data'][a] for a in ['A0', 'A1'])
assert not (OUT / 'A2').exists()
record['exits'] = {'client': client_exit, 'cleanup': cleanup_exit}
record['terminal_outcome'] = run['outcome']
record['shutdown_verified_independently'] = True
record['arm_starts'] = starts
record['A2'] = {'status': 'not run / unevaluable', 'arm_start_claim': False, 'artifacts_returned': False,
                'reason': 'client outer timeout while remote call pending; scheduling cause unverified',
                'billing': 'no-training inference does not independently settle infrastructure charges'}

spec = importlib.util.spec_from_file_location('terminal_stage_a', ROOT / 'scripts/sgm-p2p5-taskhead-read-escape-stage-a-train.py')
t = importlib.util.module_from_spec(spec)
spec.loader.exec_module(t)
probe_path = P / 'inputs/probe-taskhead-learned-n32-s0-run_manifest.json'
probe = json.loads(probe_path.read_text())
assert sha(probe_path) == t.PROBE_S0_MANIFEST_SHA256
record['completed_arms'] = {}
for arm in ['A0', 'A1']:
    d = OUT / arm
    manifest = json.loads((d / 'run_manifest.json').read_text())
    result = json.loads((d / 'stage_a_result.json').read_text())
    telemetry = [json.loads(x) for x in (d / 'routing_telemetry.jsonl').read_text().splitlines()]
    assert result == {'arm': arm, **t.classify(telemetry)}
    assert result['status'] == 'valid'
    assert manifest['pilot_config'] == json.loads(json.dumps(asdict(t.arm_config(probe['pilot_config'], arm, 'cuda'))))
    assert manifest['memsub_source_sha256'] == probe['memsub_source_sha256']
    assert manifest['probe_manifest_sha256'] == t.PROBE_S0_MANIFEST_SHA256
    assert manifest['dev_seed'] == 4242 and manifest['tf32'] == {'matmul': False, 'cudnn': False}
    assert sha(d / 'trained_parameters.safetensors') == manifest['trained_parameters_sha256']
    assert run['arms'][arm]['returncode'] == 0
    record['completed_arms'][arm] = {'result': result, 'worker_wall_s': run['arms'][arm]['wall_s']}
assert record['completed_arms']['A0']['result']['band_at_100'] == 'escaped'
assert record['completed_arms']['A1']['result']['band_at_100'] == 'partial'

index_path = P / 'geometry-index-v1.json'
index = json.loads(index_path.read_text())
assert sha(index_path) == '98d9c3835c9a5377a696bf5828e6b42a33655543224bca1729088856d1e0bb87'
assert len(index['entries']) == 2 and len({e['name'] for e in index['entries']}) == 2
for arm, entry in zip(['A0', 'A1'], index['entries']):
    assert entry['kind'] == 'geometry' and entry['device'] == 'cuda'
    assert entry['name'] == f'stage-a-{arm}-final-step100'
    for key, filename in [('manifest', 'run_manifest.json'), ('telemetry', 'routing_telemetry.jsonl'), ('params', 'trained_parameters.safetensors')]:
        rel = (OUT / arm / filename).relative_to(ROOT)
        assert entry[key] == str(rel) and sha(ROOT / rel) == entry[key + '_sha256']
    manifest = json.loads((ROOT / entry['manifest']).read_text())
    assert manifest['pilot_config']['steps'] == 100 and manifest['trained_parameters_sha256'] == entry['params_sha256']
assert index['run'] == {'memsub_source_sha256': probe['memsub_source_sha256'], 'torch': '2.7.1+cu126', 'transformers': '4.55.2'}
from memsub.sgm.synthetic_pilot_run import source_tree_sha256
assert source_tree_sha256(ROOT / 'memsub') == index['run']['memsub_source_sha256']
script = ROOT / 'scripts/sgm-p2p5-taskhead-dead-start-address-diagnosis.py'
assert sha(script) == 'e9131a62ac57cca62915ae233914315412e302bf5ab954351f20544578311ea7'
assert not (P / 'geometry-run-v1').exists() and not (P / 'geometry-run-v1.exit.txt').exists()
record['geometry'] = {'index_sha256': sha(index_path), 'script_sha256': sha(script), 'entries': [e['name'] for e in index['entries']],
                      'audit': 'CLEAR one scoped local pass after active smollm controller exits and GPU availability is rechecked',
                      'argv': ['timeout', '--signal=KILL', '3600', '.venv-gpu/bin/python', str(script.relative_to(ROOT)),
                               '--index', str(index_path.relative_to(ROOT)), '--out', str((P / 'geometry-run-v1').relative_to(ROOT))],
                      'no_retry': True, 'optimizer_steps': 0, 'paid_compute': False}
billing_path = P / 'stage-a-run-v1.billing-prelim-20261008T2029Z.json'
billing = [r for r in json.loads(billing_path.read_text()) if r['object_id'] == run['app_id']]
assert len(billing) == 1 and billing[0]['interval_start'] == '2026-10-08T19:00:00'
record['billing'] = {'app_rows': billing, 'reported_cost_usd': str(sum(Decimal(r['cost']) for r in billing)),
                     'status': 'preliminary; 20:00 UTC hour incomplete at capture, backfill not verified',
                     'reservation_usd': run['ledger']['reservation_usd'], 'cap_usd': run['ledger']['cap_usd']}
record['local_gpu_snapshot'] = subprocess.run(['nvidia-smi', '--query-gpu=utilization.gpu,memory.used,memory.free', '--format=csv,noheader'], capture_output=True, text=True, timeout=10).stdout.strip()
record['smollm_controller'] = subprocess.run(['ps', '-o', 'pid,ppid,pgid,sid,etime,stat,comm,args', '-p', '2996958'], capture_output=True, text=True, timeout=10).stdout.strip()
(HERE / 'verification.json').write_text(json.dumps(record, indent=2) + '\n')
print(json.dumps({'exits': record['exits'], 'shutdown': True, 'completed': {a:r['result']['band_at_100'] for a,r in record['completed_arms'].items()},
                  'A2': record['A2'], 'billing': record['billing'], 'geometry': record['geometry'], 'gpu': record['local_gpu_snapshot']}, indent=2))

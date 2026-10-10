"""Offline A1 artifact verification plus one read-only app/container snapshot."""
import concurrent.futures
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
P = ROOT / 'plans/261009-0030-m4-sgm-p2p5-taskhead-read-escape-blocker-screen'
OUT = P / 'stage-a-run-v1'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


spec = importlib.util.spec_from_file_location('stage_a_a1_review', ROOT / 'scripts/sgm-p2p5-taskhead-read-escape-stage-a-train.py')
t = importlib.util.module_from_spec(spec)
spec.loader.exec_module(t)
probe_path = P / 'inputs/probe-taskhead-learned-n32-s0-run_manifest.json'
probe = json.loads(probe_path.read_text())
manifest = json.loads((OUT / 'A1/run_manifest.json').read_text())
rows = [json.loads(x) for x in (OUT / 'A1/routing_telemetry.jsonl').read_text().splitlines()]
result = json.loads((OUT / 'A1/stage_a_result.json').read_text())
assert result == {'arm': 'A1', **t.classify(rows)}
assert result['status'] == 'valid' and result['band_at_100'] == 'partial' and result['kept_through_100'] is False
assert manifest['pilot_config'] == json.loads(json.dumps(asdict(t.arm_config(probe['pilot_config'], 'A1', 'cuda'))))
assert manifest['stage_a'] == {'arm': 'A1', 'overrides': {'lr': 3e-4}}
assert manifest['dev_seed'] == 4242 and manifest['tf32'] == {'matmul': False, 'cudnn': False}
assert manifest['versions']['torch'] == '2.7.1+cu126' and manifest['versions']['transformers'] == '4.55.2'
assert manifest['probe_manifest_sha256'] == sha(probe_path) == t.PROBE_S0_MANIFEST_SHA256
assert manifest['memsub_source_sha256'] == probe['memsub_source_sha256']
assert sha(OUT / 'A1/trained_parameters.safetensors') == manifest['trained_parameters_sha256']
a0 = json.loads((OUT / 'A0/run_manifest.json').read_text())
assert {k: v for k, v in a0['pilot_config'].items() if k != 'lr'} == {k: v for k, v in manifest['pilot_config'].items() if k != 'lr'}
assert a0['sgm_config'] == manifest['sgm_config'] and a0['policy_id'] == manifest['policy_id']
r0 = json.loads((OUT / 'A0/stage_a_result.json').read_text())
assert r0['absent_read_weight_by_step']['0'] == result['absent_read_weight_by_step']['0']
run = json.loads((OUT / 'run.json').read_text())
assert run['arms']['A1']['returncode'] == 0
assert run['deadline'] == 1791491100.2921758 and run['app_id'] == 'ap-cCYlrnTz0Tj7tcm7TYovau'


def query(kind):
    try:
        r = subprocess.run([sys.executable, '-m', 'modal', kind, 'list', '--json'], capture_output=True, text=True, timeout=20)
        if r.returncode:
            return {'error': r.stderr[-500:], 'returncode': r.returncode}
        data = json.loads(r.stdout)
        assert isinstance(data, list)
        return {'rows': [x for x in data if x.get('app_id') == run['app_id']]}
    except Exception as e:
        return {'error': repr(e)}


record = {'observed_utc': datetime.now(timezone.utc).isoformat(), 'app_id': run['app_id'], 'deadline_epoch': run['deadline'],
          'remaining_s_at_snapshot': run['deadline'] - datetime.now(timezone.utc).timestamp(),
          'A1_result': result, 'A1_manifest_verified': True, 'A1_worker_wall_s': run['arms']['A1']['wall_s'],
          'A0_A1_config_only_difference': 'global learning rate 0.003 -> 0.0003',
          'A1_artifact_hashes': {str(f.relative_to(ROOT)): sha(f) for f in sorted((OUT / 'A1').iterdir()) if f.is_file()},
          'model_forwards': 0, 'paid_compute_calls': 0, 'intervention': False}
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
    futures = {kind: ex.submit(query, kind) for kind in ['app', 'container']}
    record.update({kind: future.result() for kind, future in futures.items()})
record['terminal_markers'] = {name: (P / name).exists() for name in ['stage-a-run-v1.exit.txt', 'stage-a-run-v1.cleanup-exit.txt', 'stage-a-run-v1/cleanup.json']}
(HERE / 'verification.json').write_text(json.dumps(record, indent=2) + '\n')
print(json.dumps(record, indent=2))

"""Focused CPU audit of frozen 1b66312; no Qwen forward, CUDA or training."""
import hashlib
import json
import subprocess
import sys
import tempfile
import types
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
SCRIPT = 'scripts/sgm-p2p5-taskhead-dead-start-address-diagnosis.py'
INDEX = 'plans/reports/claude-261008-2350-p2p5-taskhead-dead-start-address-diagnosis/inputs-index.json'
sys.path.insert(0, str(ROOT))

def frozen(path):
    return subprocess.run(['git', 'show', f'1b66312:{path}'], cwd=ROOT,
                          capture_output=True, check=True).stdout

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

source = frozen(SCRIPT)
index_bytes = frozen(INDEX)
(OUT / 'script-at-1b66312.py').write_bytes(source)
(OUT / 'index-at-1b66312.json').write_bytes(index_bytes)
m = types.ModuleType('diagnosis_at_1b66312')
m.__file__ = str(ROOT / SCRIPT)
exec(compile(source, str(ROOT / SCRIPT), 'exec'), m.__dict__)
report = {'reviewed_commit': '1b66312', 'script_sha256': hashlib.sha256(source).hexdigest(),
          'index_sha256': hashlib.sha256(index_bytes).hexdigest(), 'qwen_forward': False, 'cuda': False}

# The runtime validates oracle presence before any model forward.
rt, backend, head = m.build(m.PilotConfig(arm='oracle', n_bindings=32))
try:
    backend.evaluate_query(backend.new_state(1), torch.tensor([[10800]]), detach=True, logits=False)
except ValueError as e:
    report['oracle_missing_query_addresses'] = repr(e)
else:
    raise AssertionError('oracle runtime guard unexpectedly accepted missing addresses')
del rt, backend, head

with tempfile.TemporaryDirectory(prefix='codex-diagnosis-check-') as tmp:
    manifest = Path(tmp) / 'run_manifest.json'
    telemetry = Path(tmp) / 'routing_telemetry.jsonl'
    telemetry.write_text('')
    report['missing_telemetry_check_returned'] = m.training_dev_eval_check(manifest, 100, {})
    telemetry.write_text(json.dumps({'step': 100, 'eval': {'query_empty_read_weight': float('nan'),
                           'occupancy_mean': 1.0, 'accuracy': 0.0}}) + '\n')
    got = m.training_dev_eval_check(manifest, 100,
          {'per_layer_head': {'1': {'query_read_empty_weight_mean': [0.5]}}, 'bank': {'occupancy_mean': 1.0}})
    report['nonfinite_telemetry_check_returned_status'] = got['status']

weights = torch.tensor([[[1 - 5e-7, 5e-7, 0, 0, 0, 0, 0, 0, 0]]], dtype=torch.float64)
present = torch.tensor([[[False, True, False, False, False, False, False, False, False]]])
empty_mass = (weights * ~present).sum(-1)
report['near_empty_counterexample'] = {
    'empty_mass': float(empty_mass), 'labelled_fully_empty': bool(empty_mass > 1 - 1e-6),
    'actually_all_positive_weight_cells_absent': not bool(((weights > 0) & present).any())}
linear = torch.nn.Linear(1, 64)
with torch.no_grad():
    linear.bias.zero_()
torch.nn.functional.cross_entropy(linear(torch.zeros(1, 1)), torch.tensor([0])).backward()
report['zero_read_features_head_gradient_counterexample'] = {
    'weight_gradient_norm': float(linear.weight.grad.norm()), 'bias_gradient_norm': float(linear.bias.grad.norm())}

checks = []
for e in json.loads(index_bytes)['entries']:
    man_path = ROOT / e['manifest']
    man = json.loads(man_path.read_text())
    r = {'name': e['name'], 'manifest_matches': sha(man_path) == e['manifest_sha256'],
         'batch': man['pilot_config']['batch'], 'eval_batches': man['pilot_config']['eval_batches'],
         'filler_len': man['pilot_config']['filler_len']}
    if e['params'] != 'init':
        params_path = ROOT / e['params']
        r['parameter_hash_matches_index'] = sha(params_path) == e['params_sha256']
        if params_path.suffix == '.pt':
            ck = torch.load(params_path, map_location='cpu', weights_only=True)
            state = json.loads((params_path.parent / 'state.json').read_text())
            link = next(x for x in state['chain'] if x['file'] == params_path.name)
            r.update(checkpoint_step=ck['step'], config_matches_manifest=ck['pilot_config'] == man['pilot_config'],
                     chain_hash_matches_index=link['sha256'] == e['params_sha256'])
        else:
            r['parameter_hash_matches_manifest'] = e['params_sha256'] == man['trained_parameters_sha256']
    checks.append(r)
report['input_checks'] = checks
assert len(checks) == 14
assert all(all(v is True for k,v in r.items() if 'matches' in k) for r in checks)
(OUT / 'checks.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2))

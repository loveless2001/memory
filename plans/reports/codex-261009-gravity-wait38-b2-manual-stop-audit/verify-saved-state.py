"""Offline CPU verification of the stopped B2 segment. Does not build/evaluate a model."""
from collections import defaultdict
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys

import torch

REPORT = Path(__file__).resolve().parent
ROOT = Path('/tmp/codex-b2-package-24b1432-1a9f5uqo')
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location('frozen_b2', ROOT / 'scripts/sgm-p2p5-b2-occupied-fill-long-run-train.py')
B = importlib.util.module_from_spec(spec)
spec.loader.exec_module(B)
RUN = REPORT / 'volume-evidence-verified/b2-run-v1'
OUT = RUN / 'B2'
META = json.loads((REPORT / 'launcher/b2-run-v1/run.json').read_text())
DICT = json.loads((REPORT / 'start-dict.json').read_text())
base_path = ROOT / 'plans/261009-0030-m4-sgm-p2p5-taskhead-read-escape-blocker-screen/inputs/probe-taskhead-learned-n32-s0-run_manifest.json'
base_hash = hashlib.sha256(base_path.read_bytes()).hexdigest()
assert base_hash == B.STAGE_A.PROBE_S0_MANIFEST_SHA256
pcfg = B.arm_config(json.loads(base_path.read_text())['pilot_config'], 'cuda')
identity = B.run_identity(pcfg, base_hash)
stored_identity = json.loads((OUT / 'identity.json').read_text())
assert identity == stored_identity
campaign = json.loads((RUN / 'campaign.json').read_text())
assert campaign == {'app': 'memsub-m4-sgm-p2p5-b2-occupied-fill-long',
                    'start_dict': 'm4-sgm-p2p5-b2-occupied-fill-long-starts-v1',
                    'volume': 'memsub-m4-sgm-p2p5-b2-occupied-fill-long-v1', 'deadline': META['deadline']}
assert DICT['deadline'] == META['deadline'] and DICT['starts']['start-1']
assert DICT['starts']['start-2'] is None and DICT['starts']['start-3'] is None

checkpoint_path = OUT / 'resume.pt'
state = torch.load(checkpoint_path, map_location='cpu', weights_only=False)
assert state['format'] == 'm4-sgm-train-resume-v1'
assert state['b2_identity'] == identity
assert state['pilot_config'] == asdict(pcfg)
assert type(state['step']) is int and 0 < state['step'] < pcfg.steps
assert state['step'] % B.CHECKPOINT_EVERY == 0
for key in ['adapters', 'head', 'optimizer', 'data_generator', 'torch_rng', 'cuda_rng', 'telemetry', 'checkpoints']:
    assert key in state

tensor_counts = defaultdict(int)
def verify_tensors(value, prefix):
    if isinstance(value, torch.Tensor):
        assert value.device.type == 'cpu'
        assert torch.isfinite(value).all(), prefix
        tensor_counts[prefix.split('.')[0]] += 1
    elif isinstance(value, dict):
        for k, v in value.items():
            verify_tensors(v, prefix + '.' + str(k))
    elif isinstance(value, (tuple, list)):
        for i, v in enumerate(value):
            verify_tensors(v, prefix + '.' + str(i))

for key in ['adapters', 'head', 'optimizer', 'data_generator', 'torch_rng', 'cuda_rng', 'checkpoints']:
    verify_tensors(state[key], key)
assert state['data_generator'].dtype == torch.uint8 and state['data_generator'].numel()
assert state['torch_rng'].dtype == torch.uint8 and state['torch_rng'].numel()
assert len(state['cuda_rng']) == 1 and state['cuda_rng'][0].dtype == torch.uint8
params = {**state['adapters'], **{'head.' + k: v for k, v in state['head'].items()}}
assert params and all(v.dtype == torch.float32 for v in params.values())
assert len(state['optimizer']['param_groups']) == 1
assert state['optimizer']['param_groups'][0]['lr'] == pcfg.lr
assert state['optimizer']['param_groups'][0]['weight_decay'] == 0
assert len(state['optimizer']['param_groups'][0]['params']) == len(params)
assert set(state['optimizer']['state']).issubset(set(state['optimizer']['param_groups'][0]['params']))

rows = [json.loads(x) for x in (OUT / 'routing_telemetry.jsonl').read_text().splitlines()]
normalize = lambda v: json.loads(json.dumps(v, default=float))
saved_rows = normalize(state['telemetry'])
assert rows[:len(saved_rows)] == saved_rows
eval_rows = [r for r in rows if 'eval' in r]
train_rows = [r for r in rows if 'loss' in r]
assert len({r['step'] for r in eval_rows}) == len(eval_rows)
assert [r['step'] for r in eval_rows] == list(range(0, eval_rows[-1]['step'] + 1, pcfg.eval_every))
assert all(B.eval_ok(r['eval']) for r in eval_rows)
assert all(math.isfinite(r['loss']) and math.isfinite(r['read_anchor']) and math.isfinite(r['sec_per_step']) for r in train_rows)
assert not any((OUT / f).exists() for f in ['b2_result.json', 'run_manifest.json',
                                         'trained_parameters.safetensors', 'final_bank_derange_eval.json'])
invalid = B.summarize(rows, None)
assert invalid['status'] == 'INVALID'
starts = [json.loads(x) for x in (RUN / 'B2.starts.jsonl').read_text().splitlines()]
assert len(starts) == 1 and starts[0]['start'] == 1 and starts[0]['resume_step'] is None
losses = [{'logged_step': r['step'], 'total_loss': r['loss'], 'unscaled_anchor': r['read_anchor'],
           'anchor_contribution': 0.1 * r['read_anchor'], 'task_ce': r['loss'] - 0.1 * r['read_anchor'],
           'sec_per_step': r['sec_per_step']} for r in train_rows]
(REPORT / 'loss-decomposition.json').write_text(json.dumps(losses, indent=2)+'\n')
last = eval_rows[-1]
result = {
    'verified_utc': datetime.now(timezone.utc).isoformat(), 'status': 'INTERRUPTED_PARTIAL_NO_FINAL_READOUT',
    'original_app_id': META['app_id'], 'original_campaign_deadline': META['deadline'],
    'admitted_starts': 1, 'worker_task_id': DICT['starts']['start-1']['task'],
    'worker_claim_utc': datetime.fromtimestamp(DICT['starts']['start-1']['t'], timezone.utc).isoformat(),
    'checkpoint': {'path': str(checkpoint_path), 'bytes': checkpoint_path.stat().st_size,
                   'sha256': hashlib.sha256(checkpoint_path.read_bytes()).hexdigest(), 'step': state['step'],
                   'identity': identity, 'pilot_config_exact': True, 'all_tensors_finite': True,
                   'tensor_counts': dict(tensor_counts), 'parameter_tensors': len(params),
                   'parameter_numel': sum(x.numel() for x in params.values()),
                   'optimizer_state_entries': len(state['optimizer']['state']),
                   'has_optimizer_and_cpu_cuda_data_rng': True, 'telemetry_rows': len(saved_rows)},
    'telemetry': {'rows': len(rows), 'checkpoint_telemetry_is_exact_prefix': True,
                  'last_logged_training_step': train_rows[-1]['step'],
                  'completed_updates_lower_bound': train_rows[-1]['step'] + 1,
                  'updates_past_checkpoint_lower_bound': train_rows[-1]['step'] + 1 - state['step'],
                  'exact_final_physical_update_count': None,
                  'eval_steps': [r['step'] for r in eval_rows],
                  'correct_by_step': {str(r['step']): r['eval']['correct'] for r in eval_rows},
                  'absent_weight_by_step': {str(r['step']): r['eval']['query_empty_read_weight'] for r in eval_rows},
                  'last_eval': last, 'last_eval_band': 'kept' if last['eval']['query_empty_read_weight'] <= .2
                                  else 'escaped' if last['eval']['query_empty_read_weight'] >= .9 else 'partial',
                  'last_task_ce': losses[-1]['task_ce'], 'uniform_ce': math.log(64)},
    'resume_state_verification': 'CPU inspection only; no model load, forward, training, or restore performed',
    'missing_final_artifacts': True, 'final_classifier': invalid,
    'first_start_stdout_bytes': (RUN / 'B2.start-1.stdout.txt').stat().st_size,
    'first_start_stderr_bytes': (RUN / 'B2.start-1.stderr.txt').stat().st_size,
}
(REPORT / 'saved-state-verification.json').write_text(json.dumps(result, indent=2)+'\n')
print(json.dumps({'status': result['status'], 'checkpoint_step': state['step'],
                  'checkpoint_bytes': result['checkpoint']['bytes'], 'checkpoint_sha256': result['checkpoint']['sha256'],
                  'all_tensors_finite': True, 'parameter_tensors': len(params),
                  'last_logged_training_step': train_rows[-1]['step'],
                  'completed_updates_lower_bound': result['telemetry']['completed_updates_lower_bound'],
                  'correct_by_step': result['telemetry']['correct_by_step'],
                  'absent_weight_by_step': result['telemetry']['absent_weight_by_step'],
                  'last_task_ce': losses[-1]['task_ce']}, indent=2))

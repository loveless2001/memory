"""CPU-only independent reconciliation of saved B1 artifacts. No forward/eval/training."""
import os
os.environ['CUDA_VISIBLE_DEVICES'] = ''
import hashlib
import importlib.util
import json
from pathlib import Path
import statistics
import sys

ROOT = Path('/tmp/codex-b1-package-7e9213a-goqhtkad')
MAIN = Path('/home/lenovo/projects/memory')
OWNER = Path('/home/lenovo/projects/memory-occupied-fill-v1-worktree')
PLAN = OWNER / 'plans/261009-1040-m4-sgm-p2p5-b1-occupied-fill-retention-screen'
B = PLAN / 'b1-run-v1/B1'
A = MAIN / 'plans/261009-0030-m4-sgm-p2p5-taskhead-read-escape-blocker-screen/stage-a-run-v1/A0'
sys.path.insert(0, str(ROOT))
import torch
from safetensors import safe_open
from memsub.sgm.config import SGMConfig
from memsub.sgm.synthetic_pilot_run import source_tree_sha256

spec = importlib.util.spec_from_file_location('b1_train', ROOT/'scripts/sgm-p2p5-b1-occupied-fill-retention-screen-train.py')
train = importlib.util.module_from_spec(spec)
spec.loader.exec_module(train)
rows = [json.loads(line) for line in (B/'routing_telemetry.jsonl').read_text().splitlines()]
result = json.loads((B/'b1_result.json').read_text())
manifest = json.loads((B/'run_manifest.json').read_text())
run = json.loads((PLAN/'b1-run-v1/run.json').read_text())
cleanup = json.loads((PLAN/'b1-run-v1/cleanup.json').read_text())
a0 = json.loads((A/'run_manifest.json').read_text())
a0_result = json.loads((A/'stage_a_result.json').read_text())
a0_rows = [json.loads(line) for line in (A/'routing_telemetry.jsonl').read_text().splitlines()]
assert train.summarize(rows) == result
assert run['arms_planned'] == ['B1'] and run['arms']['B1']['returncode'] == 0
assert run['outcome'] == 'all arms done'
assert cleanup['status'] == 'stopped_verified' and cleanup['app_id'] == run['app_id']
assert cleanup['checks'][-1]['verified'] is True
assert run['app_id'] == 'ap-ROPSmaSeABkUyr4X1d4RD2'
assert int((PLAN/'b1-run-v1.exit.txt').read_text().split()[0]) == 0
assert int((PLAN/'b1-run-v1.cleanup-exit.txt').read_text().split()[0]) == 0
assert {k:v for k,v in manifest['pilot_config'].items() if k!='sgm'} == {k:v for k,v in a0['pilot_config'].items() if k!='sgm'}
assert manifest['pilot_config']['sgm'] == train.FILL
cfg = SGMConfig.from_json(manifest['sgm_config'])
assert cfg.policy_id == manifest['policy_id']
assert {k:v for k,v in manifest['sgm_config'].items() if not k.startswith('read_fallback')} == a0['sgm_config']
assert manifest['dev_seed'] == a0['dev_seed'] == 4242
assert manifest['tf32'] == a0['tf32'] == {'matmul':False,'cudnn':False}
assert manifest['versions'] == a0['versions']
assert source_tree_sha256(ROOT/'memsub') == source_tree_sha256(OWNER/'memsub') == manifest['memsub_source_sha256'] == run['memsub_source_sha256']
base = ROOT/'plans/261009-0030-m4-sgm-p2p5-taskhead-read-escape-blocker-screen/inputs/probe-taskhead-learned-n32-s0-run_manifest.json'
assert hashlib.sha256(base.read_bytes()).hexdigest() == manifest['probe_manifest_sha256'] == train.STAGE_A.PROBE_S0_MANIFEST_SHA256
parameter_path = B/'trained_parameters.safetensors'
parameter_sha = hashlib.sha256(parameter_path.read_bytes()).hexdigest()
assert parameter_sha == manifest['trained_parameters_sha256']
with safe_open(parameter_path, framework='pt', device='cpu') as states:
    keys = list(states.keys())
    assert keys and all(torch.isfinite(states.get_tensor(k)).all() for k in keys)
    assert any(k.startswith('head.') for k in keys) and any(k.startswith('adapters.') for k in keys)
evs = {r['step']:r['eval'] for r in rows if 'eval' in r}
assert sorted(evs)==[0,25,50,75,100]
assert all(e['total']==256 and e['episodes']==64 and e['accuracy']==e['correct']/e['total'] for e in evs.values())
assert [r['step'] for r in rows if 'loss' in r] == list(range(0,100,10))
assert result['status']=='valid' and result['band_at_100']=='partial' and not result['kept_through_100']
assert 0.2 < evs[100]['query_empty_read_weight'] < 0.9
summary=[]
for step,e in evs.items():
    summary.append({'step':step,'pre_fill_absent_mass':e['query_empty_read_weight'],
                    'a0_pre_fill_absent_mass':a0_result['absent_read_weight_by_step'][str(step)],
                    'fully_absent_fraction':e['query_fully_absent_fraction'],
                    'without_occupied_fraction':e['query_without_occupied_fraction'],
                    'nearest_occupied_cells_mean':e['query_nearest_occupied_cells_mean'],
                    'fill_support_cells_mean':e['query_fill_support_cells_mean'],
                    'correct':e['correct'],'total':e['total'],'accuracy':e['accuracy']})
current_median=statistics.median(r['sec_per_step'] for r in rows if 'loss' in r)
base_median=statistics.median(r['sec_per_step'] for r in a0_rows if 'loss' in r)
print(json.dumps({'device':'cpu','model_forward_or_training':False,'status':'valid','retention_target_met':False,
 'result_exactly_recomputed_from_telemetry':True,'pilot_config_equal_except_sgm':True,'policy_id':cfg.policy_id,
 'memsub_sha256':manifest['memsub_source_sha256'],'parameters_sha256':parameter_sha,
 'parameters_bytes':parameter_path.stat().st_size,'finite_parameter_tensors':len(keys),
 'configured_updates':manifest['pilot_config']['steps'],'final_eval_after_updates':100,
 'terminal_exits':[0,0],'saved_cleanup_status':cleanup['status'],
 'pre_fill_absence_reduction_from_a0_at_100_pp':100*(a0_result['absent_read_weight_by_step']['100']-evs[100]['query_empty_read_weight']),
 'dev_accuracy_gain_from_initialization':evs[100]['accuracy']-evs[0]['accuracy'],
 'dev_readout':summary,'timing':{'b1_child_wall_s':run['arms']['B1']['wall_s'],
 'b1_train_wall_s':manifest['wall_seconds'],'a0_train_wall_s':a0['wall_seconds'],
 'b1_median_logged_step_s':current_median,'a0_median_logged_step_s':base_median,
 'observed_logged_step_ratio':current_median/base_median,'client_wall_s':run['client_wall_s']},
 'continuation_authorized':False},indent=2))

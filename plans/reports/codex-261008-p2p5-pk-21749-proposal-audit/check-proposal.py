"""Static/saved-evidence proposal audit. No model construction, sampling, forwards or remote calls."""
from pathlib import Path
import ast
import hashlib
import json
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
PROPOSAL=ROOT/'plans/261008-0144-m4-sgm-p2p5-readout-recipe-rescue-probe/proposal.md'
inputs={}

def read(p):
    p=Path(p)
    if not p.is_absolute():p=ROOT/p
    b=p.read_bytes()
    inputs[str(p.relative_to(ROOT))]=hashlib.sha256(b).hexdigest()
    return b

def load(p):return json.loads(read(p))

proposal=read(PROPOSAL)
frozen=subprocess.check_output(['git','show',f'277b801:{PROPOSAL.relative_to(ROOT)}'],cwd=ROOT)
assert proposal==frozen
grid=load('configs/m4_sgm_p2p5_grid.json')
base=grid['base']
assert base['readout']=='residual_head' and base['steps']==1500 and base['eval_batches']==4
assert base['filler_len_schedule']==[[0,0],[1000,40]]
assert grid['artifact_eval_seed_base']==9300011
pilot_source=read('memsub/sgm/synthetic_pilot.py').decode()
runner_source=read('modal-runners/modal-m4-sgm-p2p5-pk-packed-campaign-slot-runner.py').decode()
read('memsub/sgm/pinned_pretrained_qwen3_backbone.py')
read('memsub/sgm/layer_adapter.py')
read('memsub/runtime/sgm_model_runtime.py')
read('memsub/sgm/packed_slot_supervisor.py')
read('memsub/sgm/packed_slot_epoch_state.py')
read('memsub/sgm/packed_slot_cell_output_validation.py')
read('modal-runners/modal-m4-sgm-p2p5-pk-campaign-control-plane-reaper.py')
read('modal-runners/modal-m4-sgm-p2p5-pk-control-plane-reaper-logic.py')
read('scripts/sgm-p2d-step2-decision-rules.py')
read('scripts/sgm-p2g-decision-rules.py')
saved=load('plans/261005-0210-m4-sgm-p0-p2/runs/p2c-filler-curriculum-v1/curriculum-learned-n32-s0/metrics.json')
last=saved['train_last']
observed={group:{'grad_norm':last['grad_norm']['L3/'+group],
                 'update_norm':last['update_norm']['L3/'+group]} for group in ['out_proj','alpha']}
assert all(v['grad_norm'] is None and type(v['update_norm']) is float and v['update_norm']==0 for v in observed.values())

# Invoke only the structural schema function on existing saved data; no inference code.
from memsub.sgm.packed_slot_cell_output_validation import structural_schema
try:
    structural_schema(last,{'1','3'},set())
except ValueError as e:
    structural_error=str(e)
else:
    raise AssertionError('expected layer-normalised schema rejection was not reproduced')
assert 'inconsistent schemas' in structural_error

module=ast.parse(runner_source)
bindings=[]
for node in module.body:
    if isinstance(node,(ast.Assign,ast.AnnAssign)):
        text=ast.get_source_segment(runner_source,node)
        if text.startswith(('app =','image =','artifacts =','APP_NAME =','GUARD_DICT, ADMIT_DICT =')):
            bindings.append({'line':node.lineno,'source':text})
    if isinstance(node,ast.FunctionDef) and node.name=='run_slot':
        bindings.extend({'line':d.lineno,'source':ast.get_source_segment(runner_source,d)} for d in node.decorator_list)
assert len(bindings)>=5
read(Path(__file__))
result={'proposal_sha256':inputs[str(PROPOSAL.relative_to(ROOT))],
        'proposal_matches_commit':'277b801','scope':'static source and saved taskhead artifacts only',
        'saved_taskhead_unused_parameter_telemetry':observed,'canonical_schema_failure':structural_error,
        'campaign_import_time_bindings':bindings,'inputs_sha256':dict(sorted(inputs.items()))}
(OUT/'audit-evidence.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
print(json.dumps({'proposal_sha256':result['proposal_sha256'],'saved_telemetry':observed,
                  'canonical_schema_failure':structural_error,'import_time_bindings':len(bindings)}))

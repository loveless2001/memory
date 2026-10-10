"""Offline CPU audit of a live saved-state snapshot; no model construction, forward, training or restore."""
from collections import defaultdict
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import statistics
import sys
import torch

REPORT = Path(__file__).resolve().parent
ROOT = REPORT.parent/'codex-261009-gravity-22212-b2-resume-v04-review/candidate'
OLD = REPORT.parent/'codex-261009-gravity-wait38-b2-manual-stop-audit/volume-evidence-verified/b2-run-v1'
sys.path.insert(0,str(ROOT))
spec=importlib.util.spec_from_file_location('b2_saved_snapshot',ROOT/'scripts/sgm-p2p5-b2-occupied-fill-long-run-train.py')
B=importlib.util.module_from_spec(spec); spec.loader.exec_module(B)
V=REPORT/'volume'
live=json.loads((REPORT/'live-snapshot.json').read_text())
meta, d=live['launch'],live['dict']
assert d['start-2'] and d['start-2']['runner']=='resume-v0.4'
assert d['start-3'] is None
assert d['resume-1-deadline']==meta['deadline']
assert json.loads((V/'campaign.json').read_text())==json.loads((OLD/'campaign.json').read_text())
assert json.loads((V/'campaign.json').read_text())['deadline']==d['deadline']
probe=ROOT/'plans/261009-0030-m4-sgm-p2p5-taskhead-read-escape-blocker-screen/inputs/probe-taskhead-learned-n32-s0-run_manifest.json'
config=B.arm_config(json.loads(probe.read_text())['pilot_config'],'cuda')
identity=B.run_identity(config,hashlib.sha256(probe.read_bytes()).hexdigest())
assert json.loads((V/'B2/identity.json').read_text())==identity
starts=[json.loads(x) for x in (V/'B2.starts.jsonl').read_text().splitlines()]
assert len(starts)==2 and starts[-1]['start']==2 and starts[-1]['resume_step']==750
assert (V/'B2.archive/start-2/routing_telemetry.jsonl').read_bytes()==(OLD/'B2/routing_telemetry.jsonl').read_bytes()
old_state=torch.load(OLD/'B2/resume.pt',map_location='cpu',weights_only=False)
assert hashlib.sha256((OLD/'B2/resume.pt').read_bytes()).hexdigest()=='cd1a7e72cbbf4fc2cf92e029395c7e4f78a727d2b6d165b5030bacc1bd753394'
state=torch.load(V/'B2/resume.pt',map_location='cpu',weights_only=False)
assert state['format']=='m4-sgm-train-resume-v1'
assert state['pilot_config']==asdict(config) and state['b2_identity']==identity
assert type(state['step']) is int and 750<state['step']<=1500 and state['step']%50==0
tensor_counts=defaultdict(int)

def finite(v,path):
    if isinstance(v,torch.Tensor):
        assert v.device.type=='cpu' and torch.isfinite(v).all(),path
        tensor_counts[path.split('.')[0]]+=1
    elif isinstance(v,dict):
        for k,val in v.items(): finite(val,path+'.'+str(k))
    elif isinstance(v,(tuple,list)):
        for k,val in enumerate(v): finite(val,path+'.'+str(k))

for k in ['adapters','head','optimizer','data_generator','torch_rng','cuda_rng','checkpoints']:
    finite(state[k],k)
assert state['data_generator'].numel() and state['torch_rng'].numel() and len(state['cuda_rng'])==1
rows=[json.loads(x) for x in (V/'B2/routing_telemetry.jsonl').read_text().splitlines()]
normalize=lambda x:json.loads(json.dumps(x,default=float))
old_rows=normalize(old_state['telemetry'])
saved_rows=normalize(state['telemetry'])
assert rows[:len(old_rows)]==old_rows
common=min(len(rows),len(saved_rows))
assert rows[:common]==saved_rows[:common]
evals=[r for r in rows if 'eval' in r]
trains=[r for r in rows if 'loss' in r]
new_trains=[r for r in trains if r['step']>=750]
assert new_trains
assert all(B.eval_ok(r['eval']) for r in evals)
assert [r['step'] for r in evals]==list(range(0,evals[-1]['step']+1,config.eval_every))
assert all(math.isfinite(r[k]) for r in trains for k in ['loss','read_anchor','sec_per_step'])
assert (V/'B2.start-2.stderr.txt').stat().st_size==0
params={**state['adapters'],**{'head.'+k:v for k,v in state['head'].items()}}
assert params.keys()=={**old_state['adapters'],**{'head.'+k:v for k,v in old_state['head'].items()}}.keys()
changed=sum(not torch.equal(v,({**old_state['adapters'],**{'head.'+k:x for k,x in old_state['head'].items()}})[k]) for k,v in params.items())
assert changed>0
latest=evals[-1]
incomplete=B.summarize(rows,None)
assert incomplete['status']=='INVALID'
missing=[name for name in ['b2_result.json','run_manifest.json','final_bank_derange_eval.json'] if not (V/'B2'/name).exists()]
now=datetime.fromisoformat(live['capture_finished']).timestamp()
result={'verified_at':datetime.now(timezone.utc).isoformat(),'capture_finished':live['capture_finished'],
 'status':'RUNNING_PARTIAL','app_id':meta['app_id'],'call_id':meta['call_id'],'admitted_starts':2,
 'start3_unused':True,'worker_task_id':d['start-2']['task'],
 'worker_claim_utc':datetime.fromtimestamp(d['start-2']['t'],timezone.utc).isoformat(),
 'training_start_utc':datetime.fromtimestamp(starts[-1]['t'],timezone.utc).isoformat(),
 'spawn_to_worker_claim_s':d['start-2']['t']-meta['spawned'],'resume_step':750,
 'original_deadline_and_start1_preserved':True,'archived_original_partial_byte_identical':True,
 'original_checkpoint_telemetry_prefix_preserved':True,
 'checkpoint':{'step':state['step'],'bytes':(V/'B2/resume.pt').stat().st_size,
   'sha256':hashlib.sha256((V/'B2/resume.pt').read_bytes()).hexdigest(),'identity_and_config_match':True,
   'all_tensors_finite':True,'tensor_counts':dict(tensor_counts),'changed_parameter_tensors':changed,
   'optimizer_entries':len(state['optimizer']['state']),'optimizer_and_cpu_cuda_data_rng_present':True},
 'telemetry':{'rows':len(rows),'saved_checkpoint_rows':len(saved_rows),
   'checkpoint_is_exact_prefix':rows[:len(saved_rows)]==saved_rows,
   'last_logged_train_step':new_trains[-1]['step'],'completed_logical_updates_lower_bound':new_trains[-1]['step']+1,
   'new_physical_updates_lower_bound':new_trains[-1]['step']+1-750,
   'eval_correct_by_step':{str(r['step']):r['eval']['correct'] for r in evals},
   'latest_dev_correct':latest['eval']['correct'],'latest_dev_step':latest['step'],
   'latest_absent_weight':latest['eval']['query_empty_read_weight'],
   'median_resumed_short_logged_step_s':statistics.median([r['sec_per_step'] for r in new_trains if r['step']<1000]),
   'last_task_ce':new_trains[-1]['loss']-.1*new_trains[-1]['read_anchor']},
 'remaining_deadline_s_at_capture':meta['deadline']-now,'missing_final_artifacts':missing,
 'final_classifier':incomplete,'cpu_snapshot_only_no_model_forward_or_restore':True}
(REPORT/'saved-state-verification.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result,indent=2))

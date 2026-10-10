"""Independent CPU-only v3 arithmetic, input hashes and lifecycle design checks."""
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parent
BASE=ROOT/'plans/261006-1345-m4-sgm-p2p5-qwen3-0p6b-screen'
PROOF=BASE/'p2p5-pk-proof-v1'
EVIDENCE=PROOF/'volume-evidence/p2p5-pk-proof-v1'
SCRIPT=ROOT/'scripts/sgm-p2p5-pk6-packed-campaign-priced-estimate.py'
sys.path.insert(0,str(ROOT))
from memsub.sgm.synthetic_pilot_run import source_tree_sha256

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(name,d):
    with (OUT/name).open('x') as f:json.dump(d,f,indent=2,allow_nan=False)

grid=json.loads((ROOT/'configs/m4_sgm_p2p5_grid.json').read_text())
t=json.loads((EVIDENCE/'timing/timing.json').read_text())
ex=json.loads((EVIDENCE/'timing.exit.json').read_text())
original=json.loads((BASE/'pk6/priced-estimate-v3.json').read_text())
cmd=[sys.executable,str(SCRIPT),'--out',str(OUT/'cli-v3-reproduced.json')]
with (OUT/'cli-v3-reproduced.log').open('x') as f:
    p=subprocess.run(cmd,cwd=ROOT,stdout=f,stderr=subprocess.STDOUT,env=dict(os.environ,OMP_NUM_THREADS='2',MKL_NUM_THREADS='2'),timeout=60)
assert p.returncode==0
rerun=json.loads((OUT/'cli-v3-reproduced.json').read_text())
inputs=original['inputs']
hashchecks={
    'proof_timing_sha256':sha(EVIDENCE/'timing/timing.json'),
    'proof_exit_sha256':sha(EVIDENCE/'timing.exit.json'),
    'grid_sha256':sha(ROOT/'configs/m4_sgm_p2p5_grid.json'),
    'script_sha256':sha(SCRIPT),
    'memsub_source_sha256':source_tree_sha256(ROOT/'memsub'),
    'prereg_sha256':sha(BASE/'prereg.md'),
    'amendment_sha256':sha(BASE/'prereg-amendment-pk-packed-a100-resume.md')}
assert all(inputs[k]==v for k,v in hashchecks.items())
assert inputs['accepted_proof']['acceptance_sha256']==sha(PROOF/'acceptance.json')
assert json.loads((PROOF/'acceptance.json').read_text())['pass']
assert hashchecks['proof_timing_sha256']=='6381c986972af93ddb712171b0bbe2e1fc1465dc524a549d0e9650a3e514f537'
assert hashchecks['proof_exit_sha256']=='d92cf667c73d63a92e6f7afb10fb70a42c14e7da405f852e3e00e22d8020df17'
configs={}
for c in t['configs']:
    key=(c['arm'],c['n'],c['phase'])
    assert key not in configs
    configs[key]=c
    rawrate=8/(max(w['measured_end'] for w in c['workers'])-min(w['measured_start'] for w in c['workers']))
    assert abs(rawrate-c['fixed_work_updates_per_s'])<1e-12
assert len(configs)==18
base=grid['base'];steps=base['steps'];switch=base['filler_len_schedule'][1][0]
assert (switch,steps-switch)==(1000,500)
commit=max(ex['commit_s']);evalcount=len([s for s in range(steps+1) if s%base['eval_every']==0])
generations=len(range(50,steps+1,50));slots={}
readings=0;populations=[]
for block in grid['blocks']:
    arm=block['override']['arm']
    for n in block['n_bindings']:
        a,b=configs[arm,n,1],configs[arm,n,2]
        s1,s2=2/a['fixed_work_updates_per_s'],2/b['fixed_work_updates_per_s']
        ec=a['eval_and_checkpoint']+b['eval_and_checkpoint']
        dev=max(e['dev_eval_batch_s'] for e in ec);art=max(e['artifact_eval_batch_s'] for e in ec)
        ser=max(e['checkpoint_serialize_s'] for e in ec);size=max(e['checkpoint_bytes'] for e in ec)
        batches={'learned':84,'random_fixed':84,'oracle':84,'single_cell':68,'memory_off':20}[arm]
        parts={'training_s':1000*s1+500*s2,'dev_evals_s':evalcount*4*dev,'artifact_eval_s':batches*art,
            'checkpoint_write_s':2*generations*(ser+size/50e6),'commits_s':67*commit,'startup_s':300}
        life=sum(parts.values())
        restart=300+30+51*s2+batches*art+4*dev
        reserve=1.4*life+3*restart
        key=f'{arm}-n{n}'
        slots[key]={**{k:round(v,1) for k,v in parts.items()},'life_s':round(life,1),
            'restart_allowance_s':round(restart,1),'reserve_life_s':round(reserve,1),
            'commits_per_slot':67,'artifact_batches':batches,'s_per_update_p1_p2':[s1,s2]}
        for seed in block['seeds']:
            for population_n in ([32,16] if arm=='oracle' else [n]):
                populations.append({'arm':arm,'trained_n':n,'seed':seed,'population_n':population_n})
                readings+=16*(1 if arm=='memory_off' else 3)*art
readings=readings*1.1+300+len(populations)*30
life=sum(x['life_s'] for x in slots.values());reserve=sum(x['reserve_life_s'] for x in slots.values())
hard=.000694+8*.0000131+64*.00000222
charged=.000694+2*(8*.0000131+64*.00000222)
tail=240
reaper_unit=110*(.125*.0000131+.25*.00000222)
reaper=(sum(x['reserve_life_s']+tail for x in slots.values())+readings*1.4+tail)/120*reaper_unit
res={'slot_apps_usd':(reserve+9*tail)*charged,'readings_app_usd':(readings*1.4+tail)*charged,
    'image_usd':.168384*10,'reaper_usd':reaper,'margin_usd':5}
res['total_usd']=sum(res.values())
estimate={'slot_gpu_hours':life/3600,'readings_gpu_hours':readings/3600,'usd':(life+readings)*hard,
    'wall_h_slots_parallel':max(x['life_s'] for x in slots.values())/3600,
    'wall_h_end_to_end':(max(x['life_s'] for x in slots.values())+readings)/3600}
numericchecks={
    'per_slot_arithmetic_matches':all(all(abs(v-original['slots'][key][k])<1e-10 if isinstance(v,(int,float)) else v==original['slots'][key][k] for k,v in d.items()) for key,d in slots.items()),
    'all_estimate_fields_match':all(abs(v-original['estimate'][k])<1e-10 for k,v in estimate.items()),
    'all_reserve_fields_match':all(abs(v-original['planning_reserve_per_app_envelope'][k])<1e-10 for k,v in res.items())}
changes={k:[inputs[k],rerun['inputs'][k]] for k in inputs if inputs[k]!=rerun['inputs'][k]}
o=dict(original);rr=dict(rerun)
o['inputs']=dict(o['inputs']);rr['inputs']=dict(rr['inputs'])
o['inputs'].pop('git_head');rr['inputs'].pop('git_head')
report={'read_only_inputs_free_cpu_only':True,'cli_returncode':p.returncode,'hashchecks':hashchecks,
    'cli_only_git_head_changed':o==rr and set(changes)=={'git_head'},'git_head_difference':changes,
    'git_head_note':'Published JSON was generated before f63b65c commit, so records its parent1cd0469. All actual script/source/input hashes bind exact consumed bytes.',
    'numeric_checks':numericchecks,'independent_estimate':estimate,'independent_reserve':res,
    'readings_population_count':len(populations),'readings_populations':populations,
    'checkpoint_commit_count_note':'67 is a conservative allowance: current consumer has60 generations+1 joint inheritance+4 completion+1 runner final=66 successful-start commits. Repeated-start commits remain inside the app lifetime envelope.',
    'design_is_not_implemented_or_launch_cleared':True,
    'implementation_requirements':['Nine unique slot apps with immutable app-id-bound guards/deadlines, one GPU function container per app, <=4 admitted TRAINING starts.',
        'Exactly one admitted reserved-readings start; no automatic readings retry/re-execution after a crash. Refuse further starts before touching reserved populations.',
        'Confirm active schedule capacity for10 per-app periodic reapers, or choose and reprice a bounded control-plane topology that preserves all ten app-specific stop deadlines.',
        'Recompute and bind the final package after the metadata-only source change/campaign implementation; preserve all prior proof/quote bytes and audit the source bridge.',
        'Implement and test fail-closed consumption of exact accepted proof/pricing/source/grid bindings; snapshots recording hashes alone are not validation.']}
report['arithmetic_pass']=all(numericchecks.values()) and report['cli_only_git_head_changed']
save('independent-v3-audit.json',report)
print(json.dumps({'arithmetic_pass':report['arithmetic_pass'],'numeric_checks':numericchecks,
    'readings_population_count':len(populations),'estimate':estimate,'reserve':res,
    'cli_input_difference':changes},indent=2))
assert report['arithmetic_pass']

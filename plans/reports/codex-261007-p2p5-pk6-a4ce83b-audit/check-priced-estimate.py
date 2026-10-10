"""Independent, CPU-only PK6 arithmetic and source/artifact binding audit. No shared edits."""
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parent
GROUP=ROOT/'plans/261006-1345-m4-sgm-p2p5-qwen3-0p6b-screen'
PROOF=GROUP/'p2p5-pk-proof-v1/volume-evidence/p2p5-pk-proof-v1'
SCRIPT=ROOT/'scripts/sgm-p2p5-pk6-packed-campaign-priced-estimate.py'
GRID=ROOT/'configs/m4_sgm_p2p5_grid.json'

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def calculate(grid,timing,exit,switch,primary=False,commits_per_slot=30):
    rate1=.000694+8*.0000131+64*.00000222
    rate2=.000694+2*(8*.0000131+64*.00000222)
    configs={(c['arm'],c['n'],c['phase']):c for c in timing['configs']}
    base=grid['base'];steps=base['steps'];commit=max(exit['commit_s'])
    evals=len([u for u in range(steps+1) if u%base['eval_every']==0])
    slots={}
    for block in grid['blocks']:
        arm=block['override']['arm']
        for n in block['n_bindings']:
            phases=[configs[arm,n,p] for p in [1,2]]
            s1,s2=[2/c['fixed_work_updates_per_s'] if primary else max(c['per_worker_mean_s']) for c in phases]
            fields=[e for c in phases for e in c['eval_and_checkpoint']]
            dev=max(e['dev_eval_batch_s'] for e in fields);art=max(e['artifact_eval_batch_s'] for e in fields)
            ser=max(e['checkpoint_serialize_s'] for e in fields)
            batches=20 if arm=='memory_off' else 68 if arm=='single_cell' else 84
            training=switch*s1+(steps-switch)*s2
            devs=evals*base['eval_batches']*dev;arts=batches*art
            checkpoints=30*ser+commits_per_slot*commit
            life=training+devs+arts+checkpoints+300
            restart=300+51*s2+arts+base['eval_batches']*dev
            reserve=1.4*life+3*restart
            slots[f'{arm}-n{n}']={'training_s':training,'dev_evals_s':devs,'artifact_eval_s':arts,
                'checkpoints_s':checkpoints,'startup_s':300,'life_s':round(life,1),
                'restart_allowance_s':round(restart,1),'reserve_life_s':round(reserve,1),
                'artifact_batches':batches,'s_per_update_p1_p2':[s1,s2]}
    reading=0
    for block in grid['blocks']:
        arm=block['override']['arm']
        for n in block['n_bindings']:
            art=max(e['artifact_eval_batch_s'] for p in [1,2] for e in configs[arm,n,p]['eval_and_checkpoint'])
            populations=2 if arm=='oracle' else 1
            interventions=1 if arm=='memory_off' else 3
            reading+=len(block['seeds'])*populations*interventions*16*art
    reading=reading*1.1+300
    lives=sum(s['life_s'] for s in slots.values());reserves=sum(s['reserve_life_s'] for s in slots.values())
    longest=max(s['reserve_life_s'] for s in slots.values())
    reaper=(longest+240)/120*110*(.125*.0000131+.25*.00000222)
    res={'slots_usd':reserves*rate2,'readings_usd':reading*1.4*rate2,'image_usd':.168384,
         'reaper_usd':reaper,'margin_usd':5}
    res['total_usd']=sum(res.values())
    wall=max(s['life_s'] for s in slots.values())/3600
    return {'switch_step':switch,'phase_update_counts':[switch,steps-switch],
        'dev_evaluation_count_per_cell':evals,'checkpoint_generations_per_cell':30,
        'charged_commit_calls_per_slot':commits_per_slot,'uses_primary_fixed_work_rate':primary,
        'slots':slots,'estimate':{'slot_gpu_hours':lives/3600,'readings_gpu_hours':reading/3600,
            'usd':(lives+reading)*rate1,'wall_h_parallel':wall,'end_to_end_wall_h_with_sequential_readings':wall+reading/3600},
        'planning_reserve':res,'conditional_global_lifecycle_usd':9*(longest+240)*rate2+reading*1.4*rate2+.168384+5,
        'per_slot_deadlines_plus_stop_and_reading_reaper_usd':reserves*rate2+9*240*rate2+reading*1.4*rate2+.168384+reaper+5}

cmd=[sys.executable,str(SCRIPT),'--out',str(OUT/'cli-v1-reproduced.json')]
with (OUT/'cli-v1-reproduced.log').open('x') as log:
    proc=subprocess.run(cmd,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,env=dict(os.environ,OMP_NUM_THREADS='2',MKL_NUM_THREADS='2'),timeout=60)
assert proc.returncode==0
original=json.loads((GROUP/'pk6/priced-estimate-v1.json').read_text())
rerun=json.loads((OUT/'cli-v1-reproduced.json').read_text())
grid=json.loads(GRID.read_text());timing=json.loads((PROOF/'timing/timing.json').read_text());ex=json.loads((PROOF/'timing.exit.json').read_text())
switch=grid['base']['filler_len_schedule'][1][0]
wrong=grid['base']['filler_len_schedule'][1][1]
v1=calculate(grid,timing,ex,wrong)
corrected=calculate(grid,timing,ex,switch)
fixed=calculate(grid,timing,ex,switch,primary=True)
conservative=calculate(grid,timing,ex,switch,primary=True,commits_per_slot=60)
expected={
    'timing/timing.json':'6381c986972af93ddb712171b0bbe2e1fc1465dc524a549d0e9650a3e514f537',
    'timing.exit.json':'d92cf667c73d63a92e6f7afb10fb70a42c14e7da405f852e3e00e22d8020df17'}
report={'current_head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
    'read_only_inputs_free_cpu_only':True,'cli_returncode':proc.returncode,'rerun_exactly_matches_v1':rerun==original,
    'sha256':{'script':sha(SCRIPT),'original_output':sha(GROUP/'pk6/priced-estimate-v1.json'),
              'grid':sha(GRID),**{name:sha(PROOF/name) for name in expected}},
    'checks':{'audited_T_hashes_match':all(sha(PROOF/p)==h for p,h in expected.items()),
        'registered_grid_hash_matches':sha(GRID)=='d1c045eadfb562829cab72f58ba6b293f573f2e853629d3a3dd324b740a13073',
        'reproduces_published_v1_wrong_schedule':abs(v1['estimate']['usd']-original['estimate']['usd'])<1e-9 and abs(v1['planning_reserve']['total_usd']-original['planning_reserve']['total_usd'])<1e-9,
        'v1_uses_registered_schedule':all(abs(original['slots'][k]['training_s']-round(v['training_s'],1))<1e-8 for k,v in corrected['slots'].items())},
    'actual_T_spec':timing['timing_spec'], 'v1_wrong_schedule_recomputed':v1,
    'schedule_only_correction_not_approved_quote':corrected,
    'schedule_and_primary_rate_correction_not_approved_quote':fixed,
    'schedule_primary_and_60_commit_sensitivity_not_approved_quote':conservative,
    'limitations':['Correction scenarios retain v1 unvalidated startup/readings/replay/lifecycle assumptions; they are arithmetic diagnostics, not approval-ready quotes.',
        '60 checkpoint commits is the count of per-cell supervisor publish calls for two successful workers; summing every wait is conservative because one worker can compute during a co-tenant commit.',
        'A user cap must cover the chosen implemented lifetime envelope and startup/unadmitted/teardown/readings charges. No campaign runner is implemented here.']}
with (OUT/'independent-priced-estimate-audit.json').open('x') as f:json.dump(report,f,indent=2,allow_nan=False)
print(json.dumps({'checks':report['checks'],'actual_phase_switch_step':switch,'v1_phase_switch_step':wrong,
    'v1':{k:v1[k] for k in ['estimate','planning_reserve','conditional_global_lifecycle_usd']},
    'schedule_only_correction':{k:corrected[k] for k in ['estimate','planning_reserve','conditional_global_lifecycle_usd']},
    'primary_rate_and_60_commit_sensitivity':{k:conservative[k] for k in ['estimate','planning_reserve','conditional_global_lifecycle_usd']}},indent=2))

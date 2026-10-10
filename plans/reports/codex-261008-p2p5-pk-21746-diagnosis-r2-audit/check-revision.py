"""Saved-file revision audit; no model construction, forwards, population generation or remote calls."""
from pathlib import Path
import hashlib
import json
import math
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
OWNER = ROOT/'plans/reports/claude-261008-0127-p2p5-saved-evidence-diagnosis'
COMMIT = 'd3d4999e1b4058059064af8e5e73b86906441fb5'
PRIOR = ROOT/'plans/reports/codex-261008-p2p5-pk-21744-diagnosis-audit/audit-evidence.json'
inputs, checks = {}, []

def read(p):
    p = Path(p)
    if not p.is_absolute(): p = ROOT/p
    b = p.read_bytes()
    inputs[str(p.relative_to(ROOT))] = hashlib.sha256(b).hexdigest()
    return b

def load(p): return json.loads(read(p))

def check(name, ok):
    checks.append({'name':name,'pass':bool(ok)})
    if not ok: raise AssertionError(name)

def near(a,b): return abs(a-b) < 1e-12

def blob(commit,p):
    return subprocess.check_output(['git','show',f'{commit}:{p.relative_to(ROOT)}'],cwd=ROOT)

current = load(OWNER/'p2p5-saved-evidence-diagnosis.json')
prior_owner = json.loads(blob('57b7b84',OWNER/'p2p5-saved-evidence-diagnosis.json'))
prior_audit = load(PRIOR)
for row in read(OWNER/'SHA256SUMS.txt').decode().splitlines():
    sha,name = row.split(None,1)
    b = read(OWNER/name)
    check('package sha '+name,hashlib.sha256(b).hexdigest()==sha)
    check('frozen package '+name,b==blob(COMMIT,OWNER/name))
check('frozen SHA256SUMS',read(OWNER/'SHA256SUMS.txt')==blob(COMMIT,OWNER/'SHA256SUMS.txt'))
check('68 input hashes',len(current['inputs_sha256'])==68)
check('prior 55 input bindings unchanged',all(current['inputs_sha256'].get(k)==v for k,v in prior_owner['inputs_sha256'].items()))
for rel,sha in current['inputs_sha256'].items():
    b = read(rel)
    check('input hash '+rel,hashlib.sha256(b).hexdigest()==sha)
    if rel in prior_audit['inputs_sha256']:
        check('matches independently inspected prior bytes '+rel,sha==prior_audit['inputs_sha256'][rel])
    else:
        check('new frozen extra module '+rel,b==blob(COMMIT,ROOT/rel))
check('exact 13 added bindings',len(set(current['inputs_sha256'])-set(prior_owner['inputs_sha256']))==13)

# Original statistics must remain identical; independently check the new update-count field.
for cid,cell in current['cells'].items():
    stripped = json.loads(json.dumps(cell))
    rows = [json.loads(s) for s in read(ROOT/cell['out_dir']/'routing_telemetry.jsonl').splitlines() if s.strip()]
    train = [r for r in rows if 'loss' in r]
    for group,g in stripped['curves']['grad_norm'].items():
        claimed = g.pop('update_norm_positive')
        measured = sum(isinstance(r['update_norm'].get(group),(int,float)) and r['update_norm'][group]>0 for r in train)
        check(cid+' update count '+group,claimed==measured)
    check(cid+' prior cell statistics unchanged',stripped==prior_owner['cells'][cid])
check('prior gate summary unchanged',current['gate_telemetry_readings']==prior_owner['gate_telemetry_readings'])

# Independent scalar double arithmetic on local checkpoint tensors, no model creation.
import torch
torch.set_num_threads(1)
for seed in [0,1]:
    epoch=(ROOT/current['cells'][f'learned-n32-s{seed}']['out_dir']).parents[1]
    snapshots={}
    pub=current['l20_beta_checkpoint_drift'][f's{seed}']
    for gen,step in [(1,50),(2,100),(10,500),(30,1500)]:
        p=epoch/f'gen-{gen}-step{step}.pt'
        read(p)
        state=torch.load(p,map_location='cpu',weights_only=True)
        check(f'checkpoint step s{seed}/{step}',state['step']==step)
        w=state['adapters']['20.beta_proj.weight'].flatten().tolist()
        b=state['adapters']['20.beta_proj.bias'].tolist()
        snapshots[step]=(w,b)
        check(f'weight norm s{seed}/{step}',near(math.sqrt(math.fsum(x*x for x in w)),pub['weight_norm'][str(step)]))
        check(f'bias values s{seed}/{step}',b==pub['bias'][str(step)])
    delta=pub['delta_50_to_1500']
    for idx,name in [(0,'weight'),(1,'bias')]:
        diffs=[b-a for a,b in zip(snapshots[50][idx],snapshots[1500][idx])]
        check(f'{name} L2 s{seed}',near(math.sqrt(math.fsum(x*x for x in diffs)),delta[name+'_l2']))
        check(f'{name} max s{seed}',max(abs(x) for x in diffs)==delta[name+'_max_abs'])
        check(f'{name} changed s{seed}',sum(x!=0 for x in diffs)==delta[name+'_changed_elements'])

readings=load(next(p for p in current['inputs_sha256'] if p.endswith('/readings.json')))
intermediate=[]
l20={}
total=0
for n,v in readings['n'].items():
    for cid,c in v['corners'].items():
        g=c.get('gate_telemetry_descriptive') or {}
        if g.get('status')!='measured':continue
        for h,x in g['per_head'].items():
            if cid=='learned-n32-s1' and h.startswith('L20h'):
                l20[h]={'binding':x['binding_effective_mean'],'filler':x['filler_effective_mean']}
            for cls in ['binding','filler']:
                total+=1
                m=x[cls+'_effective_mean']
                if .01<m<.99:intermediate.append([f'{cid}@N{n}',h,cls,m])
check('full gate means and exceptions',current['gate_heads_readings']=={'cutoff':[.01,.99],
      'head_class_means':total,'intermediate':intermediate,'learned_n32_s1_L20':l20,'strictly_between':len(intermediate)})
for seed in [0,1]:
    rel=next(p for p in current['inputs_sha256'] if p.endswith(f'/curriculum-learned-n32-s{seed}/metrics.json'))
    m=load(rel)
    f=m['final']['heldout_none']
    expected={'readout':m['readout'],'none':f['accuracy'],'bank_derange':m['final']['heldout_bank_derange']['accuracy'],
              'train_last_step':m['train_last']['step'],'train_last_beta_grad_norm':{k:v for k,v in m['train_last']['grad_norm'].items() if k.endswith('/beta')}}
    expected.update({k:f[k] for k in ['query_empty_read_weight','effective_cells_mean','beta_by_token_class']})
    check(f'P2C metrics s{seed}',expected==current['p2c_reference'][f's{seed}'])
check('P2C rounded development reference',current['p2c_reference']['dev_n32_pct']=={'1000':[1.56,5.08],
      '1200':[9.38,34.38],'1500':[61.33,69.53],'seeds':['s0','s1']})

replay=OUT/'owner-script-replay.json'
r=subprocess.run([sys.executable,str(OWNER/'p2p5-saved-evidence-diagnosis.py'),str(replay)],cwd=ROOT,capture_output=True,text=True)
check('reviewed owner replay exit',r.returncode==0)
check('reviewed owner replay bytes',replay.read_bytes()==(OWNER/'p2p5-saved-evidence-diagnosis.json').read_bytes())
read(Path(__file__))
result={'owner_commit':COMMIT,'scope':'saved files and local tensor inspection only; no model evaluation, generation or remote calls',
        'checks':checks,'checks_passed':len(checks),'inputs_sha256':dict(sorted(inputs.items())),
        'replay_stdout':r.stdout,'gate_means':{'total':total,'intermediate':len(intermediate)}}
(OUT/'audit-evidence.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
print(json.dumps({'checks_passed':len(checks),'inputs_bound':len(inputs),'replay_byte_equal':True}))

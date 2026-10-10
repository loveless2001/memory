"""Independent saved-file audit only; no model construction, forwards, generation or remote access."""
from collections import defaultdict
from pathlib import Path
import hashlib
import json
import math
import statistics
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
OWNER = ROOT / 'plans/reports/claude-261008-0127-p2p5-saved-evidence-diagnosis'
COMMIT = '57b7b84b4441a276202465354152e14b42fd1248'
inputs = {}
checks = []
details = {}

def consume(p):
    p = Path(p)
    if not p.is_absolute():
        p = ROOT / p
    b = p.read_bytes()
    inputs[str(p.relative_to(ROOT))] = hashlib.sha256(b).hexdigest()
    return b

def load(p):
    return json.loads(consume(p))

def lines(p):
    return [json.loads(s) for s in consume(p).splitlines() if s.strip()]

def check(name, ok):
    checks.append({'name': name, 'pass': bool(ok)})
    if not ok:
        raise AssertionError(name)

def near(a, b):
    return abs(a - b) < 1e-12

def avg(v):
    return sum(v) / len(v)

owner = load(OWNER / 'p2p5-saved-evidence-diagnosis.json')
for row in consume(OWNER / 'SHA256SUMS.txt').decode().splitlines():
    sha, name = row.split(None, 1)
    b = consume(OWNER / name)
    check('owner package hash ' + name, hashlib.sha256(b).hexdigest() == sha)
    frozen = subprocess.check_output(['git', 'show', f'{COMMIT}:{(OWNER/name).relative_to(ROOT)}'], cwd=ROOT)
    check('owner frozen bytes ' + name, b == frozen)
check('55 indexed inputs', len(owner['inputs_sha256']) == 55)
for rel, sha in owner['inputs_sha256'].items():
    b = consume(rel)
    check('indexed input ' + rel, hashlib.sha256(b).hexdigest() == sha)
    frozen = subprocess.check_output(['git', 'show', f'{COMMIT}:{rel}'], cwd=ROOT)
    check('committed input ' + rel, b == frozen)

cells = {}
for cid, c in owner['cells'].items():
    p = ROOT / c['out_dir']
    done = load(p.parent / 'done.json')
    m = load(p / 'metrics.json')
    rows = lines(p / 'per_example_results.jsonl')
    tele = lines(p / 'routing_telemetry.jsonl')
    for name in ['metrics.json', 'per_example_results.jsonl', 'routing_telemetry.jsonl']:
        check(cid + ' done hash ' + name, inputs[str((p/name).relative_to(ROOT))] == done['outputs'][name])
    by = defaultdict(dict)
    for r in rows:
        k = (r['batch'], r['episode'], r['episode_hash'], r['query'])
        check(cid + ' unique row', k not in by[r['intervention']])
        check(cid + ' correctness', r['correct'] == (r['pred'] == r['label']))
        by[r['intervention']][k] = r
    base = by['none']
    check(cid + ' full baseline', len(base) == 1024)
    ivs = {}
    for iv, v in by.items():
        check(cid + ' paired coverage ' + iv, set(v) == set(base))
        ep = defaultdict(list)
        for k, r in v.items():
            check(cid + ' matching label ' + iv, r['label'] == base[k]['label'])
            ep[k[:3]].append(int(base[k]['correct']) - int(r['correct']))
        check(cid + ' 256 four-query episodes ' + iv, len(ep) == 256 and all(len(x) == 4 for x in ep.values()))
        diffs = [avg(x) for x in ep.values()]
        mu = avg(diffs)
        hw = 1.96 * statistics.stdev(diffs) / math.sqrt(len(diffs))
        result = {'accuracy': avg([int(r['correct']) for r in v.values()]),
                  'pred_changed': sum(base[k]['pred'] != r['pred'] for k, r in v.items()),
                  'gained': sum(r['correct'] and not base[k]['correct'] for k, r in v.items()),
                  'lost': sum(base[k]['correct'] and not r['correct'] for k, r in v.items()),
                  'none_minus_iv': {'diff': mu, 'lo': mu-hw, 'hi': mu+hw, 'n': len(ep)}}
        ivs[iv] = result
        published = c['interventions'][iv]
        check(cid + ' accuracy ' + iv, near(result['accuracy'], published['accuracy']))
        if iv != 'none':
            for k in ['pred_changed', 'gained', 'lost']:
                check(cid + ' ' + iv + ' ' + k, result[k] == published[k])
            for k in ['diff', 'lo', 'hi', 'n']:
                check(cid + ' ' + iv + ' ' + k, near(result['none_minus_iv'][k], published['none_minus_iv'][k]))
    tr = [r for r in tele if 'loss' in r]
    ev = [r for r in tele if 'eval' in r]
    check(cid + ' 150 logged updates', [r['step'] for r in tr] == list(range(0, 1500, 10)))
    check(cid + ' 16 dev evals', [r['step'] for r in ev] == list(range(0, 1501, 100)))
    means = [avg([r['train_acc'] for r in tr if (r['step'] >= 1000) == phase]) for phase in [False, True]]
    check(cid + ' train phase means', all(near(a,b) for a,b in zip(means, c['curves']['train_acc_p1_p2_mean'])))
    for k, pub in c['curves']['grad_norm'].items():
        v = [r['grad_norm'].get(k, 'missing') for r in tr]
        check(cid + ' grad None ' + k, sum(x is None for x in v) == pub['none'])
        check(cid + ' grad zero ' + k, sum(isinstance(x,(int,float)) and x == 0 for x in v) == pub['zero'])
        for phase in [False, True]:
            nums = [r['grad_norm'][k] for r in tr if (r['step'] >= 1000) == phase and isinstance(r['grad_norm'].get(k),(int,float))]
            med = statistics.median(nums) if nums else None
            claimed = pub['median_p2' if phase else 'median_p1']
            check(cid + ' grad median ' + k + str(phase), med == claimed)
    cells[cid] = {'phase_means': means, 'ivs': ivs,
                  'l20_update_nonzero_logged': {g: sum(r['update_norm'].get('L20/'+g,0) > 0 for r in tr) for g in ['beta','k_proj','value']},
                  'dev': [{'step':r['step'],'accuracy':r['eval']['accuracy']} for r in ev]}
details['cells'] = cells

readings_rel = next(p for p in owner['inputs_sha256'] if p.endswith('/readings.json'))
readings = load(readings_rel)
intermediate = []
total_head_class_means = 0
for n, v in readings['n'].items():
    for cid, corner in v['corners'].items():
        g = corner.get('gate_telemetry_descriptive') or {}
        if g.get('status') != 'measured':
            continue
        for h, t in g['per_head'].items():
            for k in ['binding_effective_mean', 'filler_effective_mean']:
                total_head_class_means += 1
                if .01 < t[k] < .99:
                    intermediate.append({'n': n, 'cell': cid, 'head': h, 'class': k, 'mean': t[k]})
        pub = owner['gate_telemetry_readings'][f'{cid}@N{n}']
        check(cid + ' pooled rho', near(g['rho_pooled_effective'],pub['rho']))
        check(cid + ' mean auroc', near(g['auroc_mean_defined'],pub['auroc_mean']))
        for L, rec in pub['per_layer'].items():
            hs = [t for h,t in g['per_head'].items() if h.startswith(L+'h')]
            for k, field in [('binding','binding_effective_mean'),('filler','filler_effective_mean'),('auroc_mean','auroc_applied')]:
                check(cid + L + ' gate mean ' + k, near(avg([t[field] for t in hs]),rec[k]))
details['gate_class_means'] = {'intermediate_01_99_count':len(intermediate),'total':total_head_class_means,'examples':intermediate}
details['l20_s1_gate_means'] = {h:t for h,t in readings['n']['32']['corners']['learned-n32-s1']['gate_telemetry_descriptive']['per_head'].items() if h.startswith('L20')}

# Local tensor inspection only, including exact differences rather than rounded norms.
import torch
torch.set_num_threads(1)
weights = {}
for seed in [0,1]:
    epoch = (ROOT / owner['cells'][f'learned-n32-s{seed}']['out_dir']).parents[1]
    selected = {}
    for gen, step in [(1,50),(2,100),(10,500),(30,1500)]:
        p = epoch / f'gen-{gen}-step{step}.pt'
        consume(p)
        s = torch.load(p,map_location='cpu',weights_only=True)
        check(f'checkpoint s{seed} step{step}', s['step'] == step)
        selected[step] = {k:v for k,v in s['adapters'].items() if k.startswith('20.beta_proj.')}
    weights[str(seed)] = {}
    for step, params in selected.items():
        weights[str(seed)][str(step)] = {}
        for k,t in params.items():
            delta = t - selected[50][k]
            weights[str(seed)][str(step)][k] = {'norm':t.norm().item(),'equal_step50':torch.equal(t,selected[50][k]),
                'delta_l2':delta.norm().item(),'delta_max':delta.abs().max().item(),'changed_elements':int((delta!=0).sum()),
                'values':t.tolist() if t.ndim==1 else None}
details['l20_beta_checkpoints'] = weights

p2c = {}
for seed in [0,1]:
    p = ROOT / f'plans/261005-0210-m4-sgm-p0-p2/runs/p2c-filler-curriculum-v1/curriculum-learned-n32-s{seed}/metrics.json'
    m = load(p)
    p2c[str(seed)] = {'readout':m['readout'],'beta_gradient_last':{k:v for k,v in m['train_last']['grad_norm'].items() if k.endswith('/beta')},
        'final_none':m['final']['heldout_none']}
consume(ROOT/'plans/261006-0316-m4-sgm-p2c-filler-length-curriculum/readings-v1/RESULTS.md')
details['p2c'] = p2c
for rel in ['scripts/sgm-p2d-step2-decision-rules.py','memsub/sgm/synthetic_pilot.py','memsub/sgm/synthetic_pilot_evaluation.py',
            'memsub/sgm/layer_adapter.py','memsub/runtime/sgm_model_runtime.py','memsub/sgm/training_resume_checkpoint.py',
            'memsub/sgm/synthetic_binding_task.py']:
    consume(ROOT/rel)

# Replay only the reviewed owner's arithmetic script, with output confined to reviewer directory.
replay = OUT / 'owner-script-replay.json'
p = subprocess.run([sys.executable,str(OWNER/'p2p5-saved-evidence-diagnosis.py'),str(replay)],cwd=ROOT,capture_output=True,text=True)
check('owner arithmetic replay exit',p.returncode==0)
check('owner arithmetic replay byte equality',replay.read_bytes()==(OWNER/'p2p5-saved-evidence-diagnosis.json').read_bytes())
details['owner_replay_stdout'] = p.stdout
consume(Path(__file__))
result = {'scope':'local saved rows, summaries, source and checkpoint tensors only; no model forwards, populations or remote access',
          'owner_commit':COMMIT,'checks_passed':len(checks),'checks_all_pass':all(x['pass'] for x in checks),
          'inputs_sha256':dict(sorted(inputs.items())),'details':details}
(OUT/'audit-evidence.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
print(json.dumps({'checks_passed':len(checks),'hash_bound_inputs':len(inputs),'s1_step1500':weights['1']['1500'],
                  'intermediate_gate_means':len(intermediate),'total_gate_means':total_head_class_means},indent=2))

"""Bounded offline artifact audit: CPU tensor reads; no model forward, restore or training."""
import ast
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
import math
from pathlib import Path
import statistics
import subprocess
from types import SimpleNamespace
import torch
from safetensors.torch import load_file

torch.set_num_threads(1)
REPORT = Path(__file__).parent
ROOT = Path('/home/lenovo/projects/memory-occupied-fill-v1-worktree')
PLAN = Path('plans/261010-0256-m4-sgm-p2p5-b3-feature-shift2-fill-long-run')
FIRST = REPORT.parent/'codex-261010-gravity-22538-b3-launch-audit'
COMMIT = '2efd2b09d9371cd1861128eb7781b4ff9a433577'
V = REPORT/'volume'
checks = {}
def check(name, cond):
    checks[name] = bool(cond)
    assert cond, name
def read(p):
    return json.loads(p.read_text())
def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()
def norm(v):
    return json.loads(json.dumps(v,default=float))

inputs = read(FIRST/'input-manifest.json')
for entry in inputs:
    rel = Path(entry['path'])
    source = ROOT/rel
    data = source.read_bytes()
    check('cleared source '+str(rel), hashlib.sha256(data).hexdigest()==entry['sha256'] and data==subprocess.check_output(['git','show',f'{COMMIT}:{rel}'],cwd=ROOT))
    dest=REPORT/'inputs'/rel
    dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_bytes(data)
(REPORT/'input-manifest.json').write_text(json.dumps(inputs,indent=2)+'\n')
head = subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
(REPORT/'git-status.txt').write_text(subprocess.check_output(['git','status','--short'],cwd=ROOT,text=True))
readout=ROOT/PLAN/'b3-final-readout.md'
if readout.exists():
    (REPORT/'owner-readout-as-found.md').write_bytes(readout.read_bytes())
motivation=REPORT.parent/'codex-261010-gravity-22465-b3-proposal-review/review.md'
(REPORT/'prior-probe-scope-review.md').write_bytes(motivation.read_bytes())

live = read(REPORT/'live-snapshot.json')
prior = read(FIRST/'live-snapshot.json')
meta, d, call = live['launch'], live['dict'], live['call_result']
check('snapshot completed without errors', not live['errors'])
check('call receipt matches remote', call==read(REPORT/'owner-receipts/call_result.json'))
check('successful sole start, no commit errors', call['returncode']==0 and call['start']=='start-1' and call['volume_commit_errors']==0 and 'terminal_write_errors' not in call and 'guard_cancel_error' not in call)
check('pinned GPU versions', call['versions']=={'torch':'2.7.1+cu126','transformers':'4.55.2'})
check('no extra start admitted', set(d)=={'campaign-deadline','start-1','terminal'})
check('deadline and first start preserved', d['campaign-deadline']==prior['dict']['campaign-deadline']==meta['deadline'] and d['start-1']==prior['dict']['start-1'])
check('terminal complete before deadline', d['terminal']['reason']=='completed' and d['terminal']['start']=='start-1' and d['terminal']['t']<meta['deadline'])
check('campaign identity preserved', read(V/'campaign.json')==read(FIRST/'live-snapshot/b3-run-v1/campaign.json'))
starts=[json.loads(x) for x in (V/'B3.starts.jsonl').read_text().splitlines()]
check('fresh sole trainer start', len(starts)==1 and starts[0]['start']==1 and starts[0]['resume_step'] is None)
identity=read(V/'B3/identity.json')
check('initial identity preserved bytewise', (V/'B3/identity.json').read_bytes()==(FIRST/'live-snapshot/b3-run-v1/B3/identity.json').read_bytes())
check('source identity', identity['script_sha256']==sha(ROOT/'scripts/sgm-p2p5-b3-shift2-fill-long-run-train.py') and identity['memsub_source_sha256']=='d86639b9223d4595a53cd07f3fee4da58c413414c49ed220d7135742f444a532')
probe=ROOT/'plans/261009-0030-m4-sgm-p2p5-taskhead-read-escape-blocker-screen/inputs/probe-taskhead-learned-n32-s0-run_manifest.json'
check('bound probe source', identity['probe_manifest_sha256']==sha(probe)=='4e89b95adcff68b73fecb2f071c3fe17498c7e62fd1a97ac04f77691b5fc0bb0')
expected=read(probe)['pilot_config']|{'sgm':{'read_fallback':'occupied_softmax_fill_v1','read_fallback_tau':1.0,'read_fallback_anchor':0.1,'feature_shift':2},'device':'cuda'}
check('entire recipe derived from registered base', identity['pilot_config']==expected)

rows=[json.loads(x) for x in (V/'B3/routing_telemetry.jsonl').read_text().splitlines()]
evals=[r for r in rows if 'eval' in r]
trains=[r for r in rows if 'loss' in r]
check('16 exact registered evaluations', [r['step'] for r in evals]==list(range(0,1501,100)))
check('150 exact training log steps', [r['step'] for r in trains]==list(range(0,1500,10)))
check('166 total rows, no extra row type', len(rows)==len(evals)+len(trains)==166)
initial=[json.loads(x) for x in (FIRST/'live-snapshot/b3-run-v1/B3/routing_telemetry.jsonl').read_text().splitlines()]
check('first-start telemetry exact prefix', rows[:len(initial)]==initial)
derange=read(V/'B3/final_bank_derange_eval.json')
for i,ev in enumerate([r['eval'] for r in evals]+[derange]):
    check(f'evaluator counts/schema {i}', type(ev['correct']) is int and type(ev['total']) is int and 0<=ev['correct']<=256 and ev['total']==256 and ev['episodes']==64 and ev['chance']==1/64 and ev['accuracy']==ev['correct']/256)
    for k in ['query_empty_read_weight','query_fully_absent_fraction','query_without_occupied_fraction']:
        check(f'evaluator finite range {i} {k}', math.isfinite(ev[k]) and 0<=ev[k]<=1)
    check(f'fill support {i}', math.isfinite(ev['query_nearest_occupied_cells_mean']) and ev['query_nearest_occupied_cells_mean']>=0 and math.isfinite(ev['query_fill_support_cells_mean']) and ev['query_fill_support_cells_mean']>=1-1e-6)
for row in trains:
    for key in ['loss','read_anchor','sec_per_step']:
        check(f'training finite step {row["step"]} {key}', math.isfinite(row[key]))

# Execute only these stdlib helpers from the immutable cleared source, not the trainer imports.
tree=ast.parse((REPORT/'inputs/scripts/sgm-p2p5-b3-shift2-fill-long-run-train.py').read_text())
ns={'math':math,'ARM':'B3','DEV_TOTAL':256,'DEV_EPISODES':64,'STEPS':1500,'EVAL_EVERY':100,'MEMORY_USED_MIN_CORRECT':12,'MEMORY_USED_MIN_DERANGE_DROP':6,'CHANCE_CORRECT':4,'STAGE_A':SimpleNamespace(ESCAPED=.9,KEPT=.2),'FILL_KEYS':('query_fully_absent_fraction','query_nearest_occupied_cells_mean','query_fill_support_cells_mean')}
helpers=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in {'_num','eval_ok','summarize'}]
exec(compile(ast.Module(body=helpers,type_ignores=[]),'<cleared-readout-helpers>','exec'),ns)
result=read(V/'B3/b3_result.json')
check('registered classifier exactly recomputes', ns['summarize'](rows,derange)==result)
normal,swapped=evals[-1]['eval']['correct'],derange['correct']
used=normal>=12 and normal-swapped>=6
check('independent gate negative', result['status']=='valid' and result['memory_used']==used is False and normal==8 and swapped==8)

state=torch.load(V/'B3/resume.pt',map_location='cpu',weights_only=False)
check('checkpoint 1500 with identity/config', state['format']=='m4-sgm-train-resume-v1' and state['step']==1500 and state['pilot_config']==expected and state['b3_identity']==identity)
counts=defaultdict(int)
def finite(value,prefix):
    if isinstance(value,torch.Tensor):
        assert value.device.type=='cpu' and torch.isfinite(value).all(), prefix
        counts[prefix.split('.')[0]]+=1
    elif isinstance(value,dict):
        for k,v in value.items(): finite(v,prefix+'.'+str(k))
    elif isinstance(value,(list,tuple)):
        for i,v in enumerate(value): finite(v,prefix+'.'+str(i))
for key in ['adapters','head','optimizer','data_generator','torch_rng','cuda_rng','checkpoints']:
    finite(state[key],key)
check('checkpoint tensors finite', bool(counts))
check('RNG states retained', state['data_generator'].numel()>0 and state['torch_rng'].numel()>0 and len(state['cuda_rng'])==1)
check('checkpoint telemetry prefix before final eval', norm(state['telemetry'])==rows[:-1])
check('no unregistered fixed checkpoints', state['checkpoints']=={} and expected['checkpoint_steps']==[])
optimizer_steps=sorted({int(s['step']) for s in state['optimizer']['state'].values()})
check('all active AdamW states have 1500 updates', optimizer_steps==[1500])
manifest=read(V/'B3/run_manifest.json')
check('manifest config/seed binding', manifest['pilot_config']==expected and manifest['dev_seed']==4242 and expected['seed']==0)
check('manifest source binding', manifest['memsub_source_sha256']==identity['memsub_source_sha256'] and manifest['probe_manifest_sha256']==sha(probe))
check('manifest exact versions/TF32', manifest['versions']['torch']=='2.7.1+cu126' and manifest['versions']['transformers']=='4.55.2' and manifest['tf32']=={'matmul':False,'cudnn':False})
check('manifest shift2 resolved config', manifest['sgm_config']['feature_shift']==2 and manifest['sgm_config']['resolved']=={'hidden_size':1024,'num_hidden_layers':28,'model_type':'qwen3'})
params={**{'adapters.'+k:v for k,v in state['adapters'].items()},**{'head.'+k:v for k,v in state['head'].items()}}
trained=load_file(str(V/'B3/trained_parameters.safetensors'),device='cpu')
check('all 46 final parameter tensors bound to checkpoint', params.keys()==trained.keys() and len(params)==46 and all(torch.equal(params[k],trained[k]) for k in params))
check('safetensors hash bound to final manifest', sha(V/'B3/trained_parameters.safetensors')==manifest['trained_parameters_sha256']=='7e0b4999af3a9e961dfd2d939a68b7e0e905821a557e749818dd929a52f9d295')
check('doubled shift2 projections 2048 wide', all(v.shape[1]==2048 for k,v in params.items() if k.endswith(('q_proj.weight','k_proj.weight','value_proj.weight','beta_proj.weight'))))
check('empty trainer stderr', (V/'B3.start-1.stderr.txt').stat().st_size==0)
for item in live['files']:
    check('download hash '+item['path'], sha(V/item['path'])==item['sha256'] and (V/item['path']).stat().st_size==item['bytes']==item['listed_bytes'])
    owner=ROOT/PLAN/'b3-run-v1/volume/b3-run-v1'/item['path']
    if owner.exists(): check('owner collected match '+item['path'],sha(owner)==item['sha256'])

apps,containers=read(REPORT/'app-list.json'),read(REPORT/'container-list.json')
app_id=meta['app_id']
mine=[r for r in apps if r['app_id']==app_id]
check('independent app stopped or unlisted with zero tasks', all(r['state']=='stopped' and str(r['tasks'])=='0' for r in mine))
check('independent zero B3 containers', not any(r['app_id']==app_id for r in containers))
cleanup=read(REPORT/'owner-receipts/cleanup.json')
watch=read(REPORT/'owner-receipts/watch.json')
check('watcher cleanup receipt verified', cleanup['status']=='stopped_verified' and cleanup['stop']['returncode']==0 and cleanup['checks'][-1]['verified'] is True and watch['reason']=='call returned')
check('cleanup within allowance', cleanup['elapsed_s']<300 and watch['t']<meta['deadline'])

costs={}
hourly=defaultdict(Decimal)
resources=defaultdict(Decimal)
for resolution in ('hourly','daily'):
    billing=[r for r in read(REPORT/f'billing-{resolution}-raw.json') if r['object_id']==app_id]
    check('billing records present '+resolution,bool(billing))
    costs[resolution]=sum((Decimal(r['cost']) for r in billing),Decimal(0))
    if resolution=='hourly':
        for r in billing:
            hourly[r['interval_start']]+=Decimal(r['cost'])
            resources[r['resource']]+=Decimal(r['cost'])
check('hourly/daily agree within rounding', abs(costs['daily']-costs['hourly'])<Decimal('.000001'))
check('current reported cost below approval', costs['daily']<Decimal('17'))
check('no reported post-shutdown hour', all(h<'2026-10-10T07:00:00' for h in hourly))
beta_ranges={k:max(r['eval']['beta_by_token_class'][k] for r in evals if r['step']>=300)-min(r['eval']['beta_by_token_class'][k] for r in evals if r['step']>=300) for k in ('key','value','filler')}
alpha_ranges={k:max(r['alpha'][k] for r in trains if r['step']>=540)-min(r['alpha'][k] for r in trains if r['step']>=540) for k in trains[-1]['alpha']}
check('beta means and early-layer alpha change', all(v>0 for v in beta_ranges.values()) and all(alpha_ranges[k]>0 for k in ('6','13','20')))
check('final beta parameter updates nonzero', all(trains[-1]['update_norm'][f'L{l}/beta']>0 for l in (6,13,20,27)))
terminal={
 'verified_at':datetime.now(timezone.utc).isoformat(),'status':'VALID_NEGATIVE','cleared_package_commit':COMMIT,'owner_records_head_at_capture':head,
 'source_files_verified':len(inputs),'checks_passed':len(checks),'call':call,'starts':starts,'terminal':d['terminal'],
 'training_seed':0,'development_seed':4242,'telemetry_rows':len(rows),'registered_evals':len(evals),'training_log_rows':len(trains),
 'final_normal_correct':normal,'final_deranged_correct':swapped,'derangement_drop':normal-swapped,'total':256,'memory_used':used,
 'checkpoint':{'step':state['step'],'bytes':(V/'B3/resume.pt').stat().st_size,'sha256':sha(V/'B3/resume.pt'),'finite_tensor_counts':dict(counts),'optimizer_entries':len(state['optimizer']['state']),'optimizer_update_steps':optimizer_steps,'telemetry_exact_prefix':True,'all_46_parameters_match_safetensors':True,'trained_parameters_sha256':sha(V/'B3/trained_parameters.safetensors')},
 'routing':{'final_empty_weight':evals[-1]['eval']['query_empty_read_weight'],'band_at_end':result['band_at_end'],'kept_at_every_eval':result['kept_at_every_eval'],'beta_class_mean_ranges_after300':beta_ranges,'alpha_ranges_after540':alpha_ranges,'last_logged_alpha':trains[-1]['alpha'],'last_logged_beta_update_norms':{str(l):trains[-1]['update_norm'][f'L{l}/beta'] for l in (6,13,20,27)}},
 'training':{'last10_logged_task_ce_mean':statistics.mean(r['loss']-.1*r['read_anchor'] for r in trains[-10:]),'ln64':math.log(64),'median_short_step_s':statistics.median(r['sec_per_step'] for r in trains if r['step']<1000),'median_long_step_s':statistics.median(r['sec_per_step'] for r in trains if r['step']>=1000)},
 'shutdown':{'status':'stopped_verified','app_rows':mine,'b3_container_rows':[],'account_container_list_empty':not containers,'cleanup_elapsed_s':cleanup['elapsed_s']},
 'billing':{'reported_app_only_usd':str(costs['daily']),'hours':{k:str(v) for k,v in hourly.items()},'resources':{k:str(v) for k,v in resources.items()},'approved_cap_usd':'17','conditional_reservation_usd':meta['ledger']['reservation_usd'],'settled_invoice':False,'03_hour_looks_incomplete':True,'storage_transfer_backfill_not_certified':True},
 'scientific_boundary':'No demonstrated memory use for the shift2 fill+anchor bundle, training seed 0, reused development seed 4242. Equal counts do not establish identical predictions. Nearly steady means are not parameter freezing.',
 'cpu_tensor_reads_only_no_model_forward_restore_or_training':True,
}
(REPORT/'checks.json').write_text(json.dumps(checks,indent=2)+'\n')
(REPORT/'terminal-verification.json').write_text(json.dumps(terminal,indent=2)+'\n')
print(json.dumps(terminal,indent=2))

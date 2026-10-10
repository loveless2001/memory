"""Inspect actual retained checkpoint consumers, payloads and paired container provenance."""
import datetime
import hashlib
import json
import sys
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
GROUP = ROOT / 'plans/261006-1345-m4-sgm-p2p5-qwen3-0p6b-screen/p2p5-pk-proof-v1'
EVIDENCE = GROUP / 'volume-evidence/p2p5-pk-proof-v1'
sys.path.insert(0, str(ROOT))
from memsub.sgm import packed_slot_epoch_state as es
from memsub.sgm.pinned_pretrained_qwen3_backbone import QWEN3_0P6B_BASE

torch.set_num_threads(2)
registry = json.loads((ROOT/'configs/m4_sgm_p2p5_packed_proof_registry.json').read_text())
prov = json.loads((GROUP/'launch_provenance.json').read_text())
remote = json.loads((OUT/'independent-live-shutdown-billing.json').read_text())
rows = remote['apps']['bound_app_rows']
r = {'observed_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
     'read_only':True, 'checkpoint_consumers':[], 'scenario_epochs':{}, 'checks':{}, 'timing':[]}
r['checks']['live_shutdown_verified'] = remote['apps']['returncode']==0 and remote['containers']['returncode']==0 and (
    (not rows or all(x['state']=='stopped' and int(x['tasks'])==0 for x in rows)) and remote['containers']['bound_app_rows']==[])
r['shutdown_note'] = 'Raw CLI tasks field is string "0". The first reviewer summary compared to integer zero; normalized here. Raw stopped/zero-task/zero-container evidence is retained.'
envs, models, attempt_checks, seen = [], [], [], {}
for scen in ['A','Aprime','B','C','D','E']:
    epochs={}
    for p in sorted((EVIDENCE/scen/'cells').glob('*/epoch-*/state.json')):
        rec=json.loads(p.read_text())
        epoch=rec['epoch']
        epochs.setdefault(str(epoch),{})[rec['cell']]={
            'state':rec['state'],'recovery':rec['recovery'],'container_id':rec['provenance']['container_id'],
            'physical':rec.get('physical'), 'last_chain_step':rec['chain'][-1]['step'] if rec['chain'] else None}
        envs.append(rec['identity']['env']); models.append(rec['identity']['model'])
        for g in rec['chain']:
            cp=p.parent.parent/f"epoch-{g['epoch']}"/g['file']
            if cp in seen: continue
            payload=torch.load(cp,map_location='cpu',weights_only=False)
            arm=payload['pilot_config']['arm']
            shapes={f'adapters.{k}':list(t.shape) for k,t in payload['adapters'].items()}
            shapes.update({f'head.{k}':list(t.shape) for k,t in payload['head'].items()})
            seen[cp]={
                'format_valid':payload['format']=='m4-sgm-train-resume-v1',
                'step_matches_generation':payload['step']==g['step'],
                'saved_registry_matches':shapes==registry['by_arm'][arm]['state_names_shapes'],
                'all_trained_tensors_fp32':all(t.dtype==torch.float32 for section in ['adapters','head'] for t in payload[section].values()),
                'optimizer_state_count':len(payload['optimizer']['state']),
                'optimizer_slots_match_grad_registry':len(payload['optimizer']['state'])==len(registry['by_arm'][arm]['grad_names_shapes']),
                'cuda_rng_present':bool(payload['cuda_rng']),
                'data_generator_present':torch.is_tensor(payload['data_generator']),
                'torch_rng_present':torch.is_tensor(payload['torch_rng'])}
    r['scenario_epochs'][scen]=epochs
    for p in sorted((EVIDENCE/scen/'cells').glob('*/epoch-*/attempt-1/worker-args.json')):
        a=json.loads(p.read_text())
        physical=p.parent/'physical-updates.jsonl'
        updates=[json.loads(line)['update'] for line in physical.read_text().splitlines()] if physical.exists() else []
        entry={'scenario':scen,'cell':a['cell'],'epoch':a['epoch'],'mode':a['mode'],
             'resume_step':a['resume_step'],'physical_updates':updates,'resume_file':a['resume_file']}
        checks={'qwen_cuda':a['pilot_config']['backbone']=='qwen3-0.6b-base' and a['pilot_config']['device']=='cuda',
                'proof_seeds_only':a['pilot_config']['seed'] in [99,100] and a['eval']=={
                    'final_batches':1,'final_batch_size':16,'final_seed_base':8800011,'dev_seed':8800000,'train_eval_seed_base':8800021},
                'updates_contiguous_from_resume':updates==list(range(a['resume_step'],a['resume_step']+len(updates))),
                'eval_only_has_zero_updates':a['mode']!='eval_only' or updates==[]}
        if a['resume_file']:
            prefix='/artifacts/m4-sgm/p2p5-pk-proof-v1/'
            assert a['resume_file'].startswith(prefix)
            cp=EVIDENCE/a['resume_file'][len(prefix):]
            payload=torch.load(cp,map_location='cpu',weights_only=False)
            h=hashlib.sha256(cp.read_bytes()).hexdigest()
            checks.update(resume_file_sha_matches=h==a['resume_sha256'],
                resume_payload_step_matches=payload['step']==a['resume_step'],
                resume_payload_config_matches=payload['pilot_config']==a['pilot_config'])
            entry.update(local_checkpoint=str(cp.relative_to(GROUP)),checkpoint_sha256=h,
                         optimizer_states=len(payload['optimizer']['state']))
        entry['checks']=checks
        attempt_checks.extend(checks.values())
        r['checkpoint_consumers'].append(entry)
r['generation_payloads']={str(p.relative_to(GROUP)):v for p,v in seen.items()}
r['checks']['all_generation_payload_bindings_pass']=all(all(v[k] for k in v if k!='optimizer_state_count') for v in seen.values())
r['checks']['all_worker_consumer_checks_pass']=all(attempt_checks)
r['checks']['model_identity_pinned_qwen']=all(x==QWEN3_0P6B_BASE for x in models)
r['checks']['cuda_environment_matches']=all(x['torch']=='2.7.1+cu126' and x['cuda']=='12.6' and x['transformers']=='4.55.2' and x['tf32_matmul'] is False for x in envs)
r['checks']['pair_colocated_each_epoch']=all(len({c['container_id'] for c in cells.values()})==1 for epochs in r['scenario_epochs'].values() for cells in epochs.values())
r['checks']['fresh_container_for_each_scenario_epoch']=all(len({next(iter(cells.values()))['container_id'] for cells in epochs.values()})==len(epochs) for epochs in r['scenario_epochs'].values())
r['checks']['admission_within_approved_starts']=set(json.loads((GROUP/'admission.json').read_text()))=={
    'A-start-1','Aprime-start-1','B-start-1','B-start-2','C-start-1','C-start-2','D-start-1','D-start-2','E-start-1','timing-start-1'}
t=json.loads((EVIDENCE/'timing/timing.json').read_text())
for c in t['configs']:
    workers=c['workers']
    start=min(w['measured_start'] for w in workers); end=max(w['measured_end'] for w in workers)
    rate=8/(end-start)
    r['timing'].append({'arm':c['arm'],'n':c['n'],'phase':c['phase'],
        'fixed_work_updates_per_s_recomputed':rate,'reported_rate_matches':abs(rate-c['fixed_work_updates_per_s'])<1e-12,
        'worker_mean_s':c['per_worker_mean_s'],'slot_wall_seconds_per_update_per_cell':2/rate,
        'max_worker_allocated_bytes':max(c['peak_allocated_bytes']),
        'dev_eval_batch_s':[x['dev_eval_batch_s'] for x in c['eval_and_checkpoint']],
        'artifact_eval_batch_s':[x['artifact_eval_batch_s'] for x in c['eval_and_checkpoint']],
        'checkpoint_serialize_s':[x['checkpoint_serialize_s'] for x in c['eval_and_checkpoint']]})
r['checks']['all_timing_rates_recompute']=all(c['reported_rate_matches'] for c in r['timing'])
legacy=[]
for p in EVIDENCE.glob('*/cells/*/epoch-*/attempt-1/out/run_manifest.json'):
    m=json.loads(p.read_text())
    if m.get('pilot_config',{}).get('backbone')=='qwen3-0.6b-base' and m.get('backbone','').startswith('tiny-'):
        legacy.append(str(p.relative_to(GROUP)))
r['nonblocking_metadata_note']={'legacy_top_level_backbone_label_paths':legacy,
    'explanation':'Historical hardcoded top-level tiny label is inaccurate. Actual pilot_config, resolved geometry, source-bound loader/model SHA pins, checkpoint payloads and frozen tensor registries identify Qwen. Preserve frozen proof artifacts; report the label limitation explicitly.'}
r['pass']=all(r['checks'].values())
with (OUT/'independent-terminal-binding-trace.json').open('x') as f:json.dump(r,f,indent=2,allow_nan=False)
print(json.dumps({'pass':r['pass'],'checks':r['checks'],'generation_payload_count':len(seen),
    'actual_resume_consumers':sum(bool(c['resume_file']) for c in r['checkpoint_consumers']),
    'legacy_label_count':len(legacy)},indent=2))

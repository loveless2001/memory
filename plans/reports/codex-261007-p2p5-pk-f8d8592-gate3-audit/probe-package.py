"""Gate-3 independent evidence: immutable snapshots, local CPU/fakes, no Modal RPC or GPU."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parent
REV='f8d85929e0c3fee166671a7f96be74c3134ff00d'
FROZEN=OUT/'frozen'
FROZEN.mkdir()
names=subprocess.check_output(['git','ls-tree','-r','--name-only',REV,'scripts','modal-runners'],cwd=ROOT,text=True).splitlines()
for name in names:
    if not name.endswith('.py'):continue
    p=FROZEN/name;p.parent.mkdir(parents=True,exist_ok=True)
    p.write_bytes(subprocess.check_output(['git','show',f'{REV}:{name}'],cwd=ROOT))
for name in ('memsub','configs'):(FROZEN/name).symlink_to(ROOT/name,target_is_directory=True)
def load(rel,label):
    s=importlib.util.spec_from_file_location(label,FROZEN/rel)
    m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
rd=load('scripts/sgm-p2p5-pk-campaign-readings.py','audit_readings')
os.environ['M4_PK_SLOT']='learned-n32'
slot=load('modal-runners/modal-m4-sgm-p2p5-pk-packed-campaign-slot-runner.py','audit_slot')
reader=load('modal-runners/modal-m4-sgm-p2p5-pk-campaign-readings-runner.py','audit_reader')
shared=load('modal-runners/modal-m4-sgm-p2p5-reaper-lifetime-stop-logic.py','audit_shared')
r={'revision':REV,'local_cpu_fakes_only':True}

# Package/file/source binding verification, including the preserved ten proof manifests.
idx=ROOT/'plans/261006-1345-m4-sgm-p2p5-qwen3-0p6b-screen/pk-prep/SHA256SUMS-gate3-package.txt'
checks={}
for line in idx.read_text().splitlines():
    a,b=line.split('  ',1)
    if a=='memsub_source_tree_sha256':checks[a]=rd.source_tree_sha256(ROOT/'memsub')==b
    else:checks[b]=hashlib.sha256((ROOT/b).read_bytes()).hexdigest()==a
r['package_index']={'sha256':rd.sha(idx),'checks':checks}
assert all(checks.values())
proof=ROOT/'plans/261006-1345-m4-sgm-p2p5-qwen3-0p6b-screen/p2p5-pk-proof-v1'
proof_checks={}
for line in (proof/'SHA256SUMS-volume-evidence.txt').read_text().splitlines():
    h,p=line.split('  ',1)
    if p.endswith('/run_manifest.json'):proof_checks[p]=rd.sha(proof/p)==h
r['proof_manifests']={'count':len(proof_checks),'all_hashes_unchanged':all(proof_checks.values())}
assert len(proof_checks)==10 and all(proof_checks.values())

# Real decision rules on deterministic synthetic schema-valid rows. No model evaluation.
pilots=rd.expand_cells(json.loads(rd.GRID.read_text()))
def rows(ivs,arm,oracle_ok):
    out=[]
    for iv in ivs:
        for b in range(16):
            for e in range(16):
                ix=b*16+e
                ok=oracle_ok if arm=='oracle' else (ix%10<9 if arm=='learned' else ix%10==0)
                if iv!='none':ok=False
                for q in range(4):
                    label=(ix+q)%64
                    out.append(dict(batch=b,episode=e,episode_hash=f'h{b}-{e}',query=q,key=q,label=label,
                                    pred=label if ok else (label+1)%64,correct=ok,intervention=iv))
    return out
def scenario(name,oracle_by_n):
    calls=[]
    def reserved(cid,out,pilot,n,ivs,dest):
        calls.append([pilot['arm'],n,pilot['seed'],list(ivs)])
        rr=rows(ivs,pilot['arm'],oracle_by_n[n])
        acc=sum(rd.P2D.episode_scores(rr,'none').values())/rd.P2D.N_EPISODES
        return rr,{'rows_sha256':'synthetic','accuracy_none':acc}
    with patch.object(rd,'bind_cells',return_value=({c:OUT for c in pilots},None)), \
         patch.object(rd,'parity',return_value=None),patch.object(rd,'reserved_rows',side_effect=reserved):
        rep=rd.readings(OUT,{},rd.current_identity(),OUT/name)
    return {'calls':calls,'readings':{n:v['reading'] for n,v in rep['n'].items()},
            'interfaces':{n:v['interface'] for n,v in rep['n'].items()}}
both=scenario('synthetic-both-pass',{32:True,16:True})
first_four=both['calls'][:4]
r['readings_order']={**both,'both_oracles_before_other_arms':all(c[0]=='oracle' for c in first_four)}
assert not r['readings_order']['both_oracles_before_other_arms']
mixed=scenario('synthetic-n32-fail-n16-pass',{32:False,16:True})
reverse=scenario('synthetic-n32-pass-n16-fail',{32:True,16:False})
r['per_n_interface_gate']={'n32_fail_n16_pass':mixed,'n32_pass_n16_fail':reverse}
assert all(a=='oracle' or n==16 for a,n,_,_ in mixed['calls'])
assert all(a=='oracle' or n==32 for a,n,_,_ in reverse['calls'])

# Change only a PRIVATE dependency copy. Runtime identity remains unchanged despite changed rule semantics.
before=rd.current_identity()
dependency=FROZEN/'scripts/sgm-p2p5-decision-rules.py'
old=dependency.read_text();assert old.count('INTERFACE_MIN = 0.50')==1
dependency.write_text(old.replace('INTERFACE_MIN = 0.50','INTERFACE_MIN = 0.99')+'\n# private audit mutation\n')
rd2=load('scripts/sgm-p2p5-pk-campaign-readings.py','audit_changed_dependency')
r['unbound_analysis_dependency']={'identity_unchanged':before==rd2.current_identity(),
    'original_interface_min':rd.DR.INTERFACE_MIN,'mutated_interface_min':rd2.DR.INTERFACE_MIN,
    'dependency_sha_changed':hashlib.sha256(old.encode()).hexdigest()!=rd.sha(dependency)}
assert r['unbound_analysis_dependency']['identity_unchanged'] and rd2.DR.INTERFACE_MIN==.99

# Collector provenance containing an explicit null app ID reaches the optional-ID name-only helper.
import modal
import modal.experimental
class D(dict):
    def put(self,k,v,skip_if_exists=False):
        if skip_if_exists and k in self:return False
        self[k]=v;return True
null_results={}
for label,m,leaf in [('slot',slot,slot.SLOT),('readings',reader,'readings')]:
    m.LOCAL_OUT=str(OUT/f'null-id-{label}')
    root=Path(m.LOCAL_OUT)/m.GROUP/leaf;root.mkdir(parents=True)
    (root/'launch_provenance.json').write_text(json.dumps({'deadline_epoch':100.,'deployed_app_id':None,
                                                        'expected_identity':{'memsub':before['memsub']}}))
    (root/'call.json').write_text(json.dumps({'call_id':'fc-cpu-fake'}))
    stops,lookups=[],[]
    kw=dict(poller=lambda c:('result',{}),stopper=lambda n,i:shared.stop_bound_app(n,i),
            verifier=lambda n,i:True,fetch=lambda root:{'returncode':1},now=50.)
    if label=='slot':kw['export']=lambda root:{'guard':{},'admission':{'start-1':1}}
    with patch.object(modal.App,'lookup',side_effect=lambda *a,**k:lookups.append(a)), \
         patch.object(modal.experimental,'stop_app',side_effect=lambda n,**kw:stops.append(n)):
        report=m.collect(**kw)
    null_results[label]={'name_only_stop_calls':stops,'identity_lookups':lookups,'shutdown':report['final_shutdown']}
r['null_id_collectors']=null_results
assert all(v['name_only_stop_calls'] and not v['identity_lookups'] for v in null_results.values())

# Exercise the ACTUAL collector verifier closures with stopped-but-nonzero-task metadata.
verification={}
for label,m in [('slot',slot),('readings',reader)]:
    queries=[]
    def cli(args,**kw):
        queries.append(args)
        return SimpleNamespace(stdout=json.dumps([{'app_id':'ap-fake','state':'stopped','tasks':'7'}]),returncode=0)
    def inspect(**deps):return bool(deps['verifier']('fake','ap-fake'))
    with patch.object(m,'collect',side_effect=inspect),patch.object(m.subprocess,'run',side_effect=cli):
        accepted=m._real_collect()
    verification[label]={'stopped_with_seven_tasks_accepted':accepted,'queries':queries}
r['shutdown_verification']=verification
assert all(v['stopped_with_seven_tasks_accepted'] for v in verification.values())

# Malformed acknowledged records escape cell_report rather than being reported INVALID.
cdir=OUT/'malformed-record'/'cells'/'fake-cell';(cdir/'epoch-1').mkdir(parents=True)
(cdir/'epoch-1'/'state.json').write_text('{broken')
try:slot.cell_report(cdir,{},[1],before['memsub'],{}, {},True)
except Exception as e:r['malformed_collect_record']={'raised':type(e).__name__,'message':str(e)}
else:raise AssertionError('expected malformed-record exception')

with (OUT/'independent-package-probes.json').open('x') as f:json.dump(r,f,indent=2)
print(json.dumps(r,indent=2))

"""Read-only frozen-plan check and in-memory reaper guard examples; no Modal or model calls."""
from pathlib import Path
import hashlib
import importlib.util
import json
import subprocess

ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parent
inputs={}

def read(rel):
    p=ROOT/rel
    b=p.read_bytes()
    inputs[rel]=hashlib.sha256(b).hexdigest()
    return b

proposal='plans/261008-0144-m4-sgm-p2p5-readout-recipe-rescue-probe/proposal.md'
current=read(proposal)
assert current==subprocess.check_output(['git','show','14e2b43:'+proposal],cwd=ROOT)
assert inputs[proposal]=='f13f5a712b10b997a6ea3f0cb07b32c34a6e625ee4c7ed14ec797345dc49c9de'
price=json.loads(read('plans/261006-1345-m4-sgm-p2p5-qwen3-0p6b-screen/pk6/priced-estimate-v6.json'))
assert price['slots']['learned-n32']['reserve_life_s']==31946.2
logic='modal-runners/modal-m4-sgm-p2p5-reaper-lifetime-stop-logic.py'
read(logic)
proof='plans/261006-1345-m4-sgm-p2p5-qwen3-0p6b-screen/reaper-self-stop-proof-v1/'
prov=json.loads(read(proof+'proof_provenance.json'))
report=json.loads(read(proof+'proof_report.json'))
posthoc=json.loads(read(proof+'posthoc-verify.json'))
read('modal-runners/modal-m4-sgm-p2p5-reaper-self-stop-proof.py')
assert prov['logic_sha256']==inputs[logic]
assert report['result']=='PASS' and posthoc['verify_stopped']['verified']
spec=importlib.util.spec_from_file_location('saved_reaper',ROOT/logic)
lg=importlib.util.module_from_spec(spec)
spec.loader.exec_module(lg)

class Store(dict):
    def put(self,k,v,skip_if_exists=False):
        if skip_if_exists and k in self:return False
        self[k]=v
        return True

decisions={}
for label,deadline in [('nan',float('nan')),('positive_infinity',float('inf')),('bool_true',True)]:
    decisions[label]=lg.reap_decision(Store(first_tick=0,deadline_epoch=deadline),100000,1800)
assert decisions['nan'] is None and decisions['positive_infinity'] is None
assert decisions['bool_true']=='deadline passed'
stops=[]
lg.reap_and_stop(Store(deadline_epoch=1),100,'fake-probe-only',lambda name,bound:stops.append([name,bound]))
assert stops==[['fake-probe-only',None]]
read(str(Path(__file__).relative_to(ROOT)))
result={'proposal_commit':'14e2b43','proposal_sha256':inputs[proposal],
        'shared_helper_matches_saved_proof':True,'saved_proof_result':report['result'],
        'nominal_envelope_at_stated_rates_usd':(31946.2+240)*.00118776+.168384+.2+2,
        'in_memory_guard_examples':decisions,'missing_bound_id_fake_stopper_calls':stops,
        'scope':'static files and in-memory stores only; no model, population, GPU or Modal access',
        'inputs_sha256':dict(sorted(inputs.items()))}
(OUT/'evidence.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
print(json.dumps({k:v for k,v in result.items() if k!='inputs_sha256'}))

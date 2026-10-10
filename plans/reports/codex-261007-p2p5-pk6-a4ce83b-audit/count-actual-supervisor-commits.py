"""CPU call-count probe of the real checkpoint service, with tiny scratch generation bytes."""
import hashlib
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from memsub.sgm.packed_slot_supervisor import SlotSupervisor

scratch=OUT/'commit-count-scratch'
scratch.mkdir(exist_ok=False)
calls=[]
def commit():calls.append({'call':len(calls)+1})
cells={f'cell-{s}':{'steps':1500} for s in [0,1]}
sup=SlotSupervisor(root=scratch,cells=cells,epoch=1,admitted=[1],identity={'audit':'commit-count-only'},
    checkpoint_every=50,eval_cfg={},commit=commit,reload=lambda:None)
sup.acknowledge()
initial=len(calls)
for cell in cells:
    sup.acked[cell]=set()
    att=sup.attempt_dir(cell)
    req=att/'requests'
    req.mkdir(parents=True)
    for generation,step in enumerate(range(50,1501,50),1):
        filename=f'gen-{generation}-step{step}.pt'
        # No training or payload parsing: serve_requests verifies bytes/hash and publishes metadata.
        blob=f'audit-only-{cell}-{step}'.encode()
        (att.parent/filename).write_bytes(blob)
        (req/f'req-{generation}.json').write_text(json.dumps({'g':generation,'step':step,
            'file':filename,'sha256':hashlib.sha256(blob).hexdigest()}))
    sup.serve_requests(cell)
report={'cpu_only':True,'scratch_only':True,'initial_ack_commit_calls':initial,
    'checkpoint_generation_commit_calls':len(calls)-initial,
    'acknowledged_generations':{c:len(sup.acked[c]) for c in cells},
    'states':{c:r['state'] for c,r in sup.records.items()},
    'limitations':'Counts actual publish/commit calls for two cells; does not measure latency or claim all waits are additive on the slot critical path. Output-completion and runner-final commits are outside this probe.'}
with (OUT/'actual-supervisor-commit-count.json').open('x') as f:json.dump(report,f,indent=2)
print(json.dumps(report,indent=2))
assert report['checkpoint_generation_commit_calls']==60

"""Independent e423450 review: local CPU fakes only; immutable source snapshots."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
REV = 'e4234507f2bcab7bf0c134b9776223ff00190741'

def snapshot(rel, name):
    blob = subprocess.check_output(['git', 'show', f'{REV}:{rel}'], cwd=ROOT)
    p = OUT / name
    with p.open('xb') as f:
        f.write(blob)
    return p

def load(p, name):
    spec = importlib.util.spec_from_file_location(name, p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m

logic = snapshot('modal-runners/modal-m4-sgm-p2p5-pk-control-plane-reaper-logic.py', 'frozen-control-logic.py')
controller = snapshot('modal-runners/modal-m4-sgm-p2p5-pk-campaign-control-plane-reaper.py', 'frozen-control-app.py')
slot = snapshot('modal-runners/modal-m4-sgm-p2p5-pk-packed-campaign-slot-runner.py', 'frozen-slot-runner.py')
price = json.loads(subprocess.check_output(['git', 'show', f'{REV}:plans/261006-1345-m4-sgm-p2p5-qwen3-0p6b-screen/pk6/priced-estimate-v5.json'], cwd=ROOT))
cp = load(logic, 'audit_cp')
ctl = load(controller, 'audit_ctl')
os.environ['M4_PK_SLOT'] = 'learned-n32'
runner = load(slot, 'audit_slot')
class FakeDict(dict):
    def put(self, key, value, skip_if_exists=False):
        if skip_if_exists and key in self:
            return False
        self[key] = value
        return True

r = {'revision': REV, 'scope': 'targeted early progress review; not Gate-3 clearance',
     'cpu_fakes_only_no_remote_calls': True,
     'snapshot_sha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (logic, controller, slot)}}

# Independently verify corrected ordinary behavior.
bad = [float('nan'), float('inf'), True, -1, 0]
rejected = []
for x in bad:
    try:
        cp.register(FakeDict(), 'slot', 'ap-slot', x)
    except ValueError:
        rejected.append(str(x))
    assert runner.admit(FakeDict(), FakeDict(deadline_epoch=x), 1)[0] is None
calls = []
out = cp.control_tick({'bad': {'deadline_epoch': 1}, 'good': {'app_id': 'ap-g', 'deadline_epoch': 1}}, 2,
                      lambda n, i: calls.append((n, i)), lambda n, i: True)
v = ctl.control_view(FakeDict(), 10, lambda: 'ap-self')
assert calls == [('good', 'ap-g')] and not cp.due(v, 10) and cp.due(v, 1811)
r['corrected_validation_binding_abandonment'] = {'rejected_deadlines': rejected, 'quarantine_output': out,
    'bound_stop_calls': calls, 'unarmed_view': v, 'first_tick_not_due': True}

# Threads survive the reported timeout and accumulate across ticks.
release = threading.Event()
started = []
baseline = {t.ident for t in threading.enumerate()}
def hanging(n, i):
    started.append((n, i))
    release.wait(3)
reg = {'slot': {'app_id': 'ap-slot', 'deadline_epoch': 1}}
t0 = time.monotonic()
outs = [cp.control_tick(reg, 2, hanging, lambda n, i: True, request_timeout_s=.05) for _ in range(2)]
left = [t.name for t in threading.enumerate() if t.ident not in baseline and t.is_alive()]
r['timed_out_requests_survive'] = {'outputs': outs, 'tick_pair_elapsed_s': time.monotonic() - t0,
    'started_stop_calls': started, 'surviving_workers_after_two_timeouts': left,
    'request_work_cancelled': not left}
release.set()
for t in threading.enumerate():
    if t.ident not in baseline:
        t.join(2)

# Stopping the controller may terminate its process before control() reaches the evidence write.
# Fake every Modal access; a self-stop uses os._exit. An independent file receives each fake Dict.put.
evidence = OUT / 'self-stop-order-events.jsonl'
child = r'''
import importlib.util,json,os,sys
from types import SimpleNamespace
from pathlib import Path
p,log=sys.argv[1:]
s=importlib.util.spec_from_file_location('ctl',p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
def emit(e):
 with open(log,'a') as f:f.write(json.dumps(e)+'\n')
class D(dict):
 def put(self,k,v,skip_if_exists=False):
  emit({'event':'dict_put','key':k,'value':v})
  if skip_if_exists and k in self:return False
  self[k]=v;return True
registry=D(slot={'app_id':'ap-slot','deadline_epoch':1})
guard=D(app_id='ap-self',deadline_epoch=1)
ticks=D()
def from_name(name,**kw):
 return registry if name==m.REGISTRY_DICT else guard if name==m.CONTROL_GUARD else ticks
m.modal.Dict.from_name=staticmethod(from_name)
m.modal.App.lookup=staticmethod(lambda *a,**kw:SimpleNamespace(app_id='ap-self'))
cp_s=importlib.util.spec_from_file_location('cp',Path(p).with_name('frozen-control-logic.py'))
cp=importlib.util.module_from_spec(cp_s);cp_s.loader.exec_module(cp)
def stop(name,aid,env):
 emit({'event':'stop','name':name,'app_id':aid})
 if name==m.APP_NAME:os._exit(0)
m._load=lambda name: cp if name==m.LOGIC else SimpleNamespace(stop_bound_app=stop)
m.verify_stopped=lambda n,i:False
m.time.time=lambda:2000.0
m.control.get_raw_f()()
'''
proc = subprocess.run([sys.executable, '-c', child, str(controller), str(evidence)], capture_output=True, text=True, timeout=5)
events = [json.loads(line) for line in evidence.read_text().splitlines()]
r['evidence_after_self_stop'] = {'probe_exit_code': proc.returncode, 'stderr': proc.stderr, 'events': events,
    'tick_evidence_persisted': any(e.get('event') == 'dict_put' and e.get('key') == '2000' for e in events)}
assert proc.returncode == 0

# A valid future target is not treated as unresolved at controller expiry.
longest = max(v['reserve_life_s'] for v in price['slots'].values())
deadline = ctl.SPAWN_OFFSET_S + longest + ctl.VALIDATION_SETUP_S + price['readings']['reserve_life_s'] + ctl.SLACK_S
late = deadline + ctl.FALLBACK_S + 100
selfs = []
admission = runner.admit(FakeDict(), FakeDict(deadline_epoch=late + longest), late)
out = cp.control_tick({'late-slot': {'app_id': 'ap-late', 'deadline_epoch': late + longest}}, late,
    lambda n, i: None, lambda n, i: True, {'app_name': 'control', 'app_id': 'ap-self', 'deadline_epoch': deadline},
    lambda n, i: selfs.append(n))
r['horizon_arithmetic_and_remaining_enforcement'] = {'control_deadline_relative_s': deadline,
    'fallback_end_relative_s': deadline + ctl.FALLBACK_S,
    'priced_control_life_s': price['control_plane']['life_s'], 'late_valid_slot_admitted': admission[0] is not None,
    'terminal_tick': out, 'self_stop_calls': selfs,
    'note': 'slot spawn/admit currently do not consult controller state/horizon; final orchestration must enforce offsets and admission windows'}

with (OUT / 'independent-revised-control-probes.json').open('x') as f:
    json.dump(r, f, indent=2, allow_nan=False)
print(json.dumps(r, indent=2, allow_nan=False))

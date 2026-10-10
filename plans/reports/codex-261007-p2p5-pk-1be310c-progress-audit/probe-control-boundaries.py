"""Targeted early review at1be310c. CPU/fakes only, immutable source snapshots, no live Modal actions."""
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parent
REV='1be310c05fb65b5fb875c85e825a643e6beba72b'

def snapshot(rel,name):
    blob=subprocess.check_output(['git','show',f'{REV}:{rel}'],cwd=ROOT)
    p=OUT/name
    with p.open('xb') as f:f.write(blob)
    return p

logic=snapshot('modal-runners/modal-m4-sgm-p2p5-pk-control-plane-reaper-logic.py','frozen-control-logic.py')
controller=snapshot('modal-runners/modal-m4-sgm-p2p5-pk-campaign-control-plane-reaper.py','frozen-control-app.py')
shared=snapshot('modal-runners/modal-m4-sgm-p2p5-reaper-lifetime-stop-logic.py','frozen-shared-stop-logic.py')
slot=snapshot('modal-runners/modal-m4-sgm-p2p5-pk-packed-campaign-slot-runner.py','frozen-slot-runner.py')
price=json.loads(subprocess.check_output(['git','show',f'{REV}:plans/261006-1345-m4-sgm-p2p5-qwen3-0p6b-screen/pk6/priced-estimate-v4.json'],cwd=ROOT,text=True))
def load(p,name):
    spec=importlib.util.spec_from_file_location(name,p)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    return m

class FakeDict(dict):
    def put(self,key,value,skip_if_exists=False):
        if skip_if_exists and key in self:return False
        self[key]=value;return True

cp=load(logic,'review_frozen_cp')
ctl=load(controller,'review_frozen_ctl')
bound=load(shared,'review_frozen_bound')
sys.path.insert(0,str(ROOT));os.environ['M4_PK_SLOT']='learned-n32'
run=load(slot,'review_frozen_slot')
r={'scope':'early progress review, not complete Gate-3 audit','revision':REV,
   'cpu_fakes_only_no_remote_calls':True,'source_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [logic,controller,shared,slot]}}

# A sequential workflow can start readings at the last training deadline.
longest=max(v['reserve_life_s'] for v in price['slots'].values())
reading_life=price['readings']['reserve_life_s']
control_deadline=longest+ctl.SLACK_S
reading_deadline=longest+reading_life
stops=[]
late=cp.control_tick({'readings':{'app_id':'ap-read','deadline_epoch':reading_deadline}},control_deadline+1,
    lambda n,i:stops.append([n,i]),{'app_name':'controller','app_id':'ap-controller','deadline_epoch':control_deadline},
    lambda n,i:stops.append([n,i]))
r['late_readings']={'longest_training_life_s':longest,'control_self_deadline_s':control_deadline,
    'latest_readings_deadline_without_validation_setup_s':reading_deadline,
    'uncovered_interval_s':reading_deadline-control_deadline,'tick_output':late,'stop_calls':stops,
    'controller_stops_while_readings_not_due':late.get('readings')=='not due' and ['controller','ap-controller'] in stops}

# The integration of control_view and due does not honor the advertised unarmed grace period.
guard=FakeDict();view=ctl.control_view(guard,100.0);stops=[]
out=cp.control_tick({},100.0,lambda n,i:None,view,lambda n,i:stops.append([n,i]))
r['unarmed_first_tick']={'view':view,'tick_output':out,'self_stop_calls':stops,
    'stops_before_abandonment_deadline':bool(stops) and 100<view['deadline_epoch']}

# Terminal control tick still self-stops after unresolved target errors.
stops=[]
def failing(name,aid):raise RuntimeError('controlled stop failure')
out=cp.control_tick({'slot':{'app_id':'ap-target','deadline_epoch':1.0}},100.0,failing,
    {'app_name':'controller','app_id':'ap-controller','deadline_epoch':2.0},lambda n,i:stops.append([n,i]))
r['failed_cleanup_at_self_deadline']={'tick_output':out,'self_stop_calls':stops,
    'self_stops_with_unresolved_target':bool(stops) and out['slot'].startswith('stop error')}

# Nonfinite deadlines pass type checks and are not considered due.
r['nonfinite_deadline']={}
for label,value in [('nan',float('nan')),('infinity',float('inf'))]:
    store=FakeDict();registered=cp.register(store,'slot','ap-target',value)
    admitted=run.admit(FakeDict(),FakeDict(deadline_epoch=value),100.0)
    r['nonfinite_deadline'][label]={'registration_accepted':registered,
        'classified_due':cp.due(store['slot'],100.0),'slot_admission_result':list(admitted)}

# Missing IDs reach the shared helper with None, which skips binding and stops by name.
lookup_calls=[];name_stops=[]
import modal
import modal.experimental
with patch.object(modal.App,'lookup',side_effect=lambda *a,**k:lookup_calls.append(a)), \
     patch.object(modal.experimental,'stop_app',side_effect=lambda name,**k:name_stops.append(name)):
    out=cp.control_tick({'unbound-name':{'deadline_epoch':1.0}},100.0,
                       lambda name,aid:bound.stop_bound_app(name,aid))
r['missing_id_stop']={'tick_output':out,'lookup_calls':lookup_calls,'stop_app_names':name_stops,
    'unbound_name_stop_issued':name_stops==['unbound-name'] and not lookup_calls}

# A blocked first request starves the following app within a bounded tick budget.
child="""import importlib.util,sys,time
s=importlib.util.spec_from_file_location('cp',sys.argv[1]);cp=importlib.util.module_from_spec(s);s.loader.exec_module(cp)
def stop(n,i):
 print('attempt '+n,flush=True)
 if n=='a':time.sleep(10)
cp.control_tick({'a':{'app_id':'ap-a','deadline_epoch':1},'b':{'app_id':'ap-b','deadline_epoch':1}},2,stop)
"""
try:
    p=subprocess.run([sys.executable,'-c',child,str(logic)],capture_output=True,text=True,timeout=.5)
    r['blocked_first_request']={'unexpected_completion':True,'stdout':p.stdout}
except subprocess.TimeoutExpired as e:
    output=e.stdout.decode() if isinstance(e.stdout,bytes) else e.stdout
    r['blocked_first_request']={'tick_budget_s':.5,'outer_probe_timeout':True,'stdout':output,
        'second_app_not_attempted':'attempt b' not in (output or '')}

with (OUT/'independent-control-boundary-probes.json').open('x') as f:json.dump(r,f,indent=2,allow_nan=False)
print(json.dumps({k:v for k,v in r.items() if k not in ['source_sha256']},indent=2,allow_nan=False))

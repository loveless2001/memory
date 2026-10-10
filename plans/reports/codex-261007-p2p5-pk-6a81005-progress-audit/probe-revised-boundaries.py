"""Local independent review of 6a81005. Modal APIs are mocked; no remote work."""
import ctypes
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
REV = '6a81005820d4424401d1c99892093fc7ec6d6ae9'
NAMES = ['modal-m4-sgm-p2p5-pk-control-plane-reaper-logic.py',
         'modal-m4-sgm-p2p5-pk-campaign-control-plane-reaper.py',
         'modal-m4-sgm-p2p5-pk-packed-campaign-slot-runner.py']
for name in NAMES:
    blob = subprocess.check_output(['git', 'show', f'{REV}:modal-runners/{name}'], cwd=ROOT)
    if (OUT/name).exists():
        assert (OUT/name).read_bytes() == blob
    else:
        with (OUT/name).open('xb') as f:
            f.write(blob)
def load(name, label):
    s = importlib.util.spec_from_file_location(label, OUT/name)
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m
cp, ctl = load(NAMES[0], 'audit_cp'), load(NAMES[1], 'audit_ctl')
os.environ['M4_PK_SLOT'] = 'learned-n32'
runner = load(NAMES[2], 'audit_runner')
r = {'revision': REV, 'cpu_fakes_only_no_remote_calls': True,
     'source_sha256': {n: hashlib.sha256((OUT/n).read_bytes()).hexdigest() for n in NAMES}}

# Contained writer failure now still attempts a self-stop in the normal returning case.
def bad_writer(o):
    raise OSError('controlled writer launch failure')
calls = []
status = ctl.finish_tick(cp, {'__unresolved__': ['slot']}, True, bad_writer,
    lambda: (calls.append('self'), subprocess.Popen([sys.executable, '-c', 'pass'], start_new_session=True))[1])
r['ordinary_writer_failure_contained'] = {'status': status, 'self_stop_attempted': calls == ['self']}
assert r['ordinary_writer_failure_contained']['self_stop_attempted']

# Full guard validation is improved.
price_sha = hashlib.sha256((ROOT/runner.PRICE_FILE).read_bytes()).hexdigest()
full = {'app_id': 'ap-control', 'deadline_epoch': 100000., 'price_sha256': price_sha}
live = {'live_id': lambda: 'ap-control', 'live_state': lambda i: 'deployed'}
missing = runner.controller_preflight(cp, {'deadline_epoch':100000.}, 1000., **live)
assert missing and runner.controller_preflight(cp, full, 1000., **live) is None
r['partial_binding_refused'] = {'partial_guard_problem': missing, 'full_guard_accepted': True}

# Returning fallback_evidence is insufficient if self-stop terminates before finish_tick returns.
child = '''import importlib.util,os,sys
from pathlib import Path
s=importlib.util.spec_from_file_location('ctl',sys.argv[1]);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
cs=importlib.util.spec_from_file_location('cp',Path(sys.argv[1]).with_name('modal-m4-sgm-p2p5-pk-control-plane-reaper-logic.py'))
cp=importlib.util.module_from_spec(cs);cs.loader.exec_module(cp)
def writer(o):raise OSError('controlled unavailable evidence writer')
m.finish_tick(cp,{'__unresolved__':['slot'],'__control__':'fallback due'},True,writer,lambda:os._exit(0))
print('returned fallback evidence',flush=True)
'''
p = subprocess.run([sys.executable, '-c', child, str(OUT/NAMES[1])], capture_output=True, text=True, timeout=3)
r['fallback_lost_on_immediate_self_stop'] = {'exit_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr,
    'fallback_emitted_before_stop':bool(p.stdout)}
assert p.returncode == 0 and not p.stdout and not p.stderr

# Exercise production CHILD with a fake nested CLI; adopt descendants for precise local cleanup.
libc = ctypes.CDLL(None, use_errno=True)
assert libc.prctl(36,1,0,0,0) == 0  # process-local Linux child subreaper
fake = OUT/'fake-cli-package'/'modal'
fake.mkdir(parents=True)
(fake/'__init__.py').write_text('')
(fake/'__main__.py').write_text('import os,json,time\nfrom pathlib import Path\n'
 'Path(os.environ["PK_REVIEW_PIDFILE"]).write_text(json.dumps({"pid":os.getpid(),"ppid":os.getppid()}))\n'
 'time.sleep(10)\nprint("[]")\n')
(OUT/'fake-stop.py').write_text('def stop_bound_app(name,app_id,environment):\n return None\n')
ctl.SHARED='fake-stop.py'
for mode in ('normal_timeout','worker_crash'):
    pidfile=OUT/f'{mode}-descendant.json'
    parent=None;desc=None
    with patch.dict(os.environ,{'PYTHONPATH':str(fake.parent),'PK_REVIEW_PIDFILE':str(pidfile)}):
        try:
            parent=ctl.launch_stop('cpu-fake-slot','ap-cpu-fake')
            until=time.monotonic()+3
            while not pidfile.exists() and time.monotonic()<until:time.sleep(.01)
            assert pidfile.exists()
            desc=json.loads(pidfile.read_text())['pid']
            if mode=='worker_crash':
                parent.kill()  # controlled worker failure before supervisor observes it
                parent.wait()
            out=cp.run_owned({'slot':parent},.05)
            stat=(Path('/proc')/str(desc)/'stat').read_text()
            state=stat[stat.rfind(')')+2:].split()[0]
            r[mode]={'outcome':out,'parent_reaped':parent.poll() is not None,
                     'descendant_state':state,'descendant_still_running':state!='Z'}
        finally:
            if parent is not None:
                try:os.killpg(parent.pid,signal.SIGKILL)
                except ProcessLookupError:pass
                if parent.poll() is None:parent.wait()
            if desc is not None:
                os.waitpid(desc,0)
                r.setdefault(mode,{})['probe_cleanup_reaped_descendant']=True
assert not r['normal_timeout']['descendant_still_running']
assert r['worker_crash']['descendant_still_running']

# The preflight checks an earlier deadline than the one later written by spawn.
class D(dict):
    def put(self,k,v,skip_if_exists=False):
        if skip_if_exists and k in self:return False
        self[k]=v;return True
price=json.loads((ROOT/runner.PRICE_FILE).read_text())
slot_life=price['slots'][runner.SLOT]['reserve_life_s']
allowance=runner.VALIDATION_SETUP_S+price['readings']['reserve_life_s']+runner.CONTROL_SLACK_S
control=D(app_id='ap-control',deadline_epoch=1000.+slot_life+allowance,price_sha256=price_sha)
guard,registry=D(),D()
spawned=[]
def from_name(n,**kw):
    return {runner.CONTROL_GUARD_DICT:control,runner.GUARD_DICT:guard,runner.CONTROL_REGISTRY_DICT:registry}[n]
def lookup(n,**kw):
    return SimpleNamespace(app_id='ap-control' if n==runner.CONTROL_APP_NAME else 'ap-slot')
def git_run(args,**kw):
    assert args[:2] in (['git','status'],['git','rev-parse'])
    return SimpleNamespace(stdout='' if args[1]=='status' else REV,returncode=0)
runner.LOCAL_OUT=str(OUT/'fake-spawn-artifacts')
runner.PRICE_FILE=str(ROOT/runner.PRICE_FILE)
runner.expected_identity=lambda:{'cpu_fake':True}
runner.app_state=lambda i:'deployed'
clock=iter([1000.,1001.])
fn=SimpleNamespace(spawn=lambda e:(spawned.append(e),SimpleNamespace(object_id='fc-cpu-fake'))[1])
with patch.object(runner.modal.Dict,'from_name',side_effect=from_name), \
     patch.object(runner.modal.App,'lookup',side_effect=lookup), \
     patch.object(runner.modal.Function,'from_name',return_value=fn), \
     patch.object(runner.subprocess,'run',side_effect=git_run), \
     patch.object(runner.time,'time',side_effect=lambda:next(clock)):
    runner.spawn()
latest=control['deadline_epoch']-allowance
r['checked_vs_written_deadline']={'preflight_deadline':1000.+slot_life,'latest_allowed_deadline':latest,
    'written_deadline':guard['deadline_epoch'],'excess_s':guard['deadline_epoch']-latest,
    'fake_spawn_called':bool(spawned)}
assert guard['deadline_epoch']>latest and spawned

with (OUT/'independent-boundary-probes.json').open('x') as f:json.dump(r,f,indent=2)
print(json.dumps(r,indent=2))

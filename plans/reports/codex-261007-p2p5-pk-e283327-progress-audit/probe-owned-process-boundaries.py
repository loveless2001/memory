"""Independent e283327 CPU/fake audit; no Modal RPC, deploy, GPU, or shared edits."""
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
REV = 'e2833270692a49a5d0bdc023d8d4660a64017984'
FILES = ['modal-m4-sgm-p2p5-pk-control-plane-reaper-logic.py',
         'modal-m4-sgm-p2p5-pk-campaign-control-plane-reaper.py',
         'modal-m4-sgm-p2p5-pk-packed-campaign-slot-runner.py']
for name in FILES:
    blob = subprocess.check_output(['git', 'show', f'{REV}:modal-runners/{name}'], cwd=ROOT)
    with (OUT / name).open('xb') as f:
        f.write(blob)
def load(name, label):
    s = importlib.util.spec_from_file_location(label, OUT / name)
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m
cp = load(FILES[0], 'audit_cp')
ctl = load(FILES[1], 'audit_ctl')
os.environ['M4_PK_SLOT'] = 'learned-n32'
runner = load(FILES[2], 'audit_runner')
r = {'revision': REV, 'cpu_fakes_only_no_remote_calls': True,
     'snapshot_sha256': {n: hashlib.sha256((OUT/n).read_bytes()).hexdigest() for n in FILES}}

# Ordinary direct children are killed and reaped; no running thread leak.
direct = {n: subprocess.Popen([sys.executable, '-c', 'import time;time.sleep(10)']) for n in ['a', 'b', 'c']}
direct['ok'] = subprocess.Popen([sys.executable, '-c', 'pass'])
out = cp.run_owned(direct, .2)
r['direct_children'] = {'outcomes': out, 'all_reaped': all(p.poll() is not None for p in direct.values())}
assert r['direct_children']['all_reaped'] and out['ok'] == 'stopped_verified'

# A writer can fail while being created, before run_owned can contain it.
self_calls = []
def failing_writer(out):
    raise OSError('controlled evidence child launch failure')
try:
    ctl.finish_tick(cp, {'__unresolved__': ['slot']}, True, failing_writer,
                    lambda: self_calls.append('self-stop'))
except OSError as e:
    r['writer_launch_failure'] = {'raised': repr(e), 'self_stop_attempts': self_calls}
else:
    raise AssertionError('expected evidence-launch failure did not propagate')

# Exercise the exact production CHILD and launch_stop. Its nested CLI is a local fake module,
# so no Modal RPC occurs. The fake CLI hangs and records its own PID for precise cleanup.
fake_root = OUT / 'fake-cli-package'
fake_modal = fake_root / 'modal'
fake_modal.mkdir(parents=True)
(fake_modal / '__init__.py').write_text('')
pidfile = OUT / 'fake-cli-grandchild.json'
(fake_modal / '__main__.py').write_text(
    'import json,os,time\nfrom pathlib import Path\n'
    'Path(os.environ["PK_AUDIT_PIDFILE"]).write_text(json.dumps({"pid":os.getpid(),"ppid":os.getppid()}))\n'
    'time.sleep(10)\nprint("[]")\n')
fake_shared = OUT / 'fake-shared-stop.py'
fake_shared.write_text('def stop_bound_app(name, app_id, environment):\n    return None\n')
ctl.SHARED = fake_shared.name
# Adopt the probe's orphaned grandchild so cleanup can reap it instead of leaving a zombie.
libc = ctypes.CDLL(None, use_errno=True)
assert libc.prctl(36, 1, 0, 0, 0) == 0  # Linux PR_SET_CHILD_SUBREAPER; scoped to this probe process
parent = None
grandchild = None
with patch.dict(os.environ, {'PYTHONPATH': str(fake_root), 'PK_AUDIT_PIDFILE': str(pidfile)}):
    try:
        parent = ctl.launch_stop('cpu-fake-slot', 'ap-cpu-fake')
        wait_until = time.monotonic() + 3
        while not pidfile.exists() and time.monotonic() < wait_until:
            time.sleep(.01)
        assert pidfile.exists(), 'fake nested CLI did not start'
        recorded = json.loads(pidfile.read_text())
        grandchild = recorded['pid']
        result = cp.run_owned({'slot': parent}, .05)
        os.kill(grandchild, 0)
        r['nested_cli_survives'] = {'production_child_pid': parent.pid, 'nested_cli': recorded,
            'run_owned_outcome': result, 'direct_child_reaped': parent.poll() is not None,
            'nested_cli_still_alive_after_tick': True}
    finally:
        if parent is not None and parent.poll() is None:
            parent.kill()
            parent.wait()
        if grandchild is not None:
            try:
                os.kill(grandchild, signal.SIGKILL)
            except ProcessLookupError:
                pass
            os.waitpid(grandchild, 0)
            r.setdefault('nested_cli_survives', {})['probe_cleanup_killed_and_reaped_nested_cli'] = True

# A deadline-only partial controller guard is accepted by the concrete slot spawn path.
class FakeDict(dict):
    def put(self, k, v, skip_if_exists=False):
        if skip_if_exists and k in self:
            return False
        self[k] = v
        return True
guard = FakeDict()
control_guard = FakeDict(deadline_epoch=100_000.0)
registry = FakeDict()
dict_reads, lookups, spawned = [], [], []
def get_dict(name, **kw):
    dict_reads.append(name)
    return {runner.GUARD_DICT: guard, runner.CONTROL_GUARD_DICT: control_guard,
            runner.CONTROL_REGISTRY_DICT: registry}[name]
def lookup(name, **kw):
    lookups.append(name)
    return SimpleNamespace(app_id='ap-cpu-slot')
def git_run(args, **kw):
    assert args[:2] in (['git', 'status'], ['git', 'rev-parse'])
    return SimpleNamespace(stdout='' if args[1] == 'status' else REV, returncode=0)
runner.LOCAL_OUT = str(OUT / 'fake-spawn-artifacts')
runner.PRICE_FILE = str(ROOT / runner.PRICE_FILE)
runner.expected_identity = lambda: {'cpu_fake': True}
fake_fn = SimpleNamespace(spawn=lambda expected: (spawned.append(expected), SimpleNamespace(object_id='fc-cpu-fake'))[1])
with patch.object(runner.modal.Dict, 'from_name', side_effect=get_dict), \
     patch.object(runner.modal.App, 'lookup', side_effect=lookup), \
     patch.object(runner.modal.Function, 'from_name', return_value=fake_fn), \
     patch.object(runner.subprocess, 'run', side_effect=git_run), \
     patch.object(runner.time, 'time', return_value=1000.0):
    runner.spawn()
r['partial_controller_guard'] = {'controller_guard': control_guard, 'dicts_accessed': dict_reads,
    'app_lookups': lookups, 'slot_spawn_called': bool(spawned),
    'note': 'finite deadline is present, but controller app_id is absent; no controller identity/state lookup occurs'}

with (OUT / 'independent-boundary-probes.json').open('x') as f:
    json.dump(r, f, indent=2)
print(json.dumps(r, indent=2))

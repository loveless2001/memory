"""Clarify timed-out worker lifetime without relying on potentially reused thread IDs."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import threading

OUT = Path(__file__).resolve().parent
LOGIC = OUT / 'frozen-control-logic.py'
s = importlib.util.spec_from_file_location('cp_lifetime', LOGIC)
cp = importlib.util.module_from_spec(s)
s.loader.exec_module(cp)
release, workers = threading.Event(), []
def stop(n, i):
    workers.append(threading.current_thread())
    release.wait(3)
reg = {'slot': {'app_id': 'ap-slot', 'deadline_epoch': 1}}
outputs = [cp.control_tick(reg, 2, stop, lambda n, i: True, request_timeout_s=.05) for _ in range(2)]
r = {'outputs': outputs, 'live_workers_after_two_returned_ticks': [t.name for t in workers if t.is_alive()]}
release.set()
for t in workers:
    t.join(2)
child = '''import importlib.util,sys,threading
s=importlib.util.spec_from_file_location('cp',sys.argv[1]);cp=importlib.util.module_from_spec(s);s.loader.exec_module(cp)
cp.control_tick({'slot':{'app_id':'ap-slot','deadline_epoch':1}},2,lambda n,i:threading.Event().wait(10),lambda n,i:True,request_timeout_s=.05)
print('tick returned; main completed',flush=True)
'''
try:
    p = subprocess.run([sys.executable, '-c', child, str(LOGIC)], capture_output=True, text=True, timeout=.5)
    r['interpreter_exit'] = {'exited': True, 'output': p.stdout}
except subprocess.TimeoutExpired as e:
    stdout = e.stdout.decode() if isinstance(e.stdout, bytes) else e.stdout
    r['interpreter_exit'] = {'outer_timeout_s': .5, 'exited': False, 'output': stdout}
assert len(r['live_workers_after_two_returned_ticks']) == 2
assert not r['interpreter_exit']['exited'] and 'main completed' in r['interpreter_exit']['output']
with (OUT / 'independent-request-lifetime.json').open('x') as f:
    json.dump(r, f, indent=2)
print(json.dumps(r, indent=2))

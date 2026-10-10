"""One read-only launch snapshot; never starts, stops or retries model work."""
import datetime
import hashlib
import json
import os
import subprocess
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
BASE = ROOT / 'plans/reports/claude-261008-2350-p2p5-taskhead-dead-start-address-diagnosis'
run = json.loads((BASE / 'run-v1/run.json').read_text())
argv = Path('/proc/2778184/cmdline').read_bytes().split(b'\0')
argv = [x.decode() for x in argv if x]
assert argv[:3] == ['timeout', '--signal=KILL', '3600']
assert argv[3] == '.venv-gpu/bin/python'
assert argv[4:] == run['argv']
assert run['pid'] == 2778185
assert os.getpgid(2778184) == os.getpgid(2778185) == 2778184
assert os.getsid(2778184) == os.getsid(2778185) == 2778183
previous = json.loads((ROOT / 'plans/reports/codex-261008-p2p5-pk-21944-diagnosis-r2-audit/verdict.json').read_text())
for name, wanted in previous['bindings'].items():
    assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == wanted
assert run['script_sha256'] == previous['bindings'][run['argv'][0]]
assert run['index_sha256'] == previous['bindings'][run['index']]
assert run['identity'] == previous['run_identity_preflight']['identity']
snapshot = subprocess.check_output(['ps', '-o', 'pid,ppid,pgid,sid,etime,stat,args', '--pid',
                                   '2778183,2778184,2778185'], text=True)
record = {'observed_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
          'guard_pid': 2778184, 'worker_pid': 2778185, 'process_group': 2778184,
          'session': 2778183, 'argv_verified': argv, 'identity_and_hashes_match_review': True,
          'completed_entries_at_snapshot': run['done'], 'finished_at_snapshot': 'finished_utc' in run,
          'exit_file_present_at_snapshot': (BASE / 'run-v1.exit.txt').exists(),
          'error_file_present_at_snapshot': (BASE / 'run-v1/ERROR.txt').exists()}
(OUT / 'snapshot.json').write_text(json.dumps(record, indent=2) + '\n')
(OUT / 'processes.txt').write_text(snapshot)
(OUT / 'launch-record.txt').write_bytes((BASE / 'run-v1.launch.txt').read_bytes())
(OUT / 'run-at-snapshot.json').write_text(json.dumps(run, indent=2) + '\n')
(OUT / 'review.txt').write_text('''Launch provenance matches the cleared one-invocation scope.
The live timeout guard and Python worker share process group 2778184,
under session 2778183. Actual argv contains timeout --signal=KILL 3600;
script, index, source/environment and pinned Qwen identities match the review.
The initial snapshot-write failure is disclosed; the retained t+12s snapshot
and independent /proc/process snapshot support the launched process group.
No intervention or repeat execution is needed. Completion, outputs and cleanup
remain pending. GPU memory observed early does not prove complete-run fit.
Existing completion wait #18 remains the next trigger; no polling planned.
''')
files = sorted(p for p in OUT.iterdir() if p.is_file() and p.name != 'SHA256SUMS.txt')
(OUT / 'SHA256SUMS.txt').write_text(''.join(f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n' for p in files))
print(json.dumps(record))

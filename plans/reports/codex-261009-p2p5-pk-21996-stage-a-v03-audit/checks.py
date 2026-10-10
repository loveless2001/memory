"""Offline v0.3 package audit and stale-deadline counterexample. No Qwen/Modal calls."""
import hashlib
import importlib.util
import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
BASE = ROOT / 'plans/261009-0030-m4-sgm-p2p5-taskhead-read-escape-blocker-screen'
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
package = []
for line in (BASE / 'SHA256SUMS-stage-a-package-v0.3.txt').read_text().splitlines():
    wanted, name = line.split('  ', 1)
    path = ROOT / name
    assert sha(path) == wanted
    assert path.read_bytes() == subprocess.check_output(['git', 'show', '111901c:' + name], cwd=ROOT)
    package.append({'file': name, 'sha256': wanted})
assert len(package) == 9
name = 'modal-runners/modal-m4-sgm-p2p5-stage-a-read-escape-blocker-runner.py'
spec = importlib.util.spec_from_file_location('audit_stage_a_v03_runner', ROOT / name)
R = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R)

class Store:
    def __init__(self): self.d = {'deadline': 1000.0}
    def put(self, key, value, skip_if_exists=False):
        if skip_if_exists and key in self.d: return False
        self.d[key] = value
        return True
    def get(self, key): return self.d.get(key)

store, clock, calls = Store(), [0.0], []
def slow_versions():
    clock[0] = 1001.0
    return {'ok': True, 'got': R.EXPECT_VERSIONS}
def child(cmd, **kw):
    calls.append({'clock_at_child_launch': clock[0], 'child_timeout': kw['timeout']})
    return subprocess.CompletedProcess(cmd, 0, '', '')
with tempfile.TemporaryDirectory() as tmp:
    with patch.object(R.modal.Dict, 'from_name', lambda *a, **kw: store), \
         patch.object(R.time, 'time', lambda: clock[0]), patch.object(R, '_versions_ok', slow_versions), \
         patch.object(R.tempfile, 'mkdtemp', lambda **kw: tmp), patch.object(R.subprocess, 'run', child):
        result = R.run_arm_remote.get_raw_f()('A0', 1000.0)
assert calls == [{'clock_at_child_launch': 1001.0, 'child_timeout': 910.0}]
assert result['returncode'] == 0

log = ROOT / 'plans/261006-1345-m4-sgm-p2p5-qwen3-0p6b-screen/dev-gpu/hotspot-l40s-v1.console.log'
lines = log.read_text().splitlines()
assert R.BASE_IMAGE_ID in '\n'.join(lines[140:155])
image_evidence = '\n'.join(lines[140:155]) + '\n'
(OUT / 'image-provenance-excerpt.txt').write_text(image_evidence)
for source, dest in [(ROOT / name, 'runner-at-111901c.py'),
                     (ROOT / R.SCRIPT, 'train-at-111901c.py'),
                     (BASE / 'proposal.md', 'proposal-at-111901c.md'),
                     (BASE / 'SHA256SUMS-stage-a-package-v0.3.txt', 'package-at-111901c.txt')]:
    shutil.copyfile(source, OUT / dest)
evidence = {'commit': '111901c', 'package': package, 'ledger': R.ledger(),
            'deadline_counterexample': {'deadline': 1000.0, 'calls': calls,
               'explanation': 'Version check consumes time after remaining was sampled; an expired child is still launched.'},
            'image_history_sha256': sha(log), 'image_id_from_history': R.BASE_IMAGE_ID,
            'image_availability_live_verified': False, 'new_qwen_work': False, 'modal_calls': 0}
(OUT / 'checks.json').write_text(json.dumps(evidence, indent=2) + '\n')
print(json.dumps({'package_files': len(package), 'deadline_counterexample': evidence['deadline_counterexample'],
                  'ledger': R.ledger(), 'modal_calls': 0}, indent=2))

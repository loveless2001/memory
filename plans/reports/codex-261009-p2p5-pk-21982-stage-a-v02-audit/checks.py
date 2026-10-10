"""Offline v0.2 audit: package binding, CPU counterexamples, and local Modal SDK semantics.
Does not call Modal or construct a backbone.
"""
import hashlib
import importlib.util
import inspect
import json
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
BASE = ROOT / 'plans/261009-0030-m4-sgm-p2p5-taskhead-read-escape-blocker-screen'
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
package = []
for line in (BASE / 'SHA256SUMS-stage-a-package-v0.2.txt').read_text().splitlines():
    wanted, name = line.split('  ', 1)
    path = ROOT / name
    assert sha(path) == wanted
    assert path.read_bytes() == subprocess.check_output(['git', 'show', '4ee2a52:' + name], cwd=ROOT)
    package.append({'path': name, 'sha256': wanted})
assert len(package) == 8

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m

T = load('audit_stage_a_train', 'scripts/sgm-p2p5-taskhead-read-escape-stage-a-train.py')
R = load('audit_stage_a_runner', 'modal-runners/modal-m4-sgm-p2p5-stage-a-read-escape-blocker-runner.py')

class FakeDict:
    def __init__(self): self.values = {}
    def put(self, key, value, skip_if_exists=False):
        if skip_if_exists and key in self.values: return False
        self.values[key] = value
        return True
    def get(self, key): return self.values.get(key)

fake, calls = FakeDict(), []
with tempfile.TemporaryDirectory() as tmp:
    mapped = lambda p: Path(tmp) / Path(p).name if str(p).startswith('/tmp') else Path(p)
    def fake_run(cmd, **kw):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, '', '')
    with patch.object(R.modal.Dict, 'from_name', lambda *a, **kw: fake), \
         patch.object(R.subprocess, 'run', fake_run), patch.object(R, 'Path', mapped):
        first = R.run_arm_remote.get_raw_f()('A0')
        assert first['returncode'] == 0
        try:
            R.run_arm_remote.get_raw_f()('A1')
        except FileExistsError as error:
            warm = {'first_arm_returncode': first['returncode'], 'second_arm_exception': type(error).__name__,
                    'error': str(error), 'children_started': len(calls), 'start_keys': list(fake.values)}
        else: raise AssertionError('Expected fixed-directory warm-container failure')
assert warm['children_started'] == 1

classifier = {}
for name, val in [('negative', -.1), ('over_one', 1.1), ('bool', True)]:
    rows = [{'step': s, 'eval': {'query_empty_read_weight': val}} for s in T.EVAL_STEPS]
    classifier[name] = T.classify(rows)
assert classifier['negative']['band_at_100'] == 'kept'
assert classifier['over_one']['band_at_100'] == 'escaped'
assert classifier['bool']['status'] == 'valid'

from modal.dict import _Dict
sdk = {'modal_version': R.modal.__version__, 'dict_put_source': inspect.getsource(_Dict.put),
       'image_run_function_signature': str(inspect.signature(R.modal.Image.run_function))}
result = {'reviewed_commit': '4ee2a52', 'package': package, 'warm_container_counterexample': warm,
          'classifier_counterexamples': classifier, 'ledger': R.ledger(), 'sdk': sdk,
          'new_model_work': False, 'modal_calls': 0}
(OUT / 'checks.json').write_text(json.dumps(result, indent=2) + '\n')
for name, path in [('train-at-4ee2a52.py', ROOT / R.SCRIPT),
                   ('runner-at-4ee2a52.py', ROOT / 'modal-runners/modal-m4-sgm-p2p5-stage-a-read-escape-blocker-runner.py'),
                   ('proposal-at-4ee2a52.md', BASE / 'proposal.md'),
                   ('package-at-4ee2a52.txt', BASE / 'SHA256SUMS-stage-a-package-v0.2.txt')]:
    (OUT / name).write_bytes(path.read_bytes())
print(json.dumps({'package_files': len(package), 'warm_container_failure': warm,
                  'classifier': classifier, 'ledger': R.ledger(), 'modal_calls': 0}, indent=2))

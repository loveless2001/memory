"""Verify current test helper preserves real guards; mutate only private copies."""
import hashlib
import importlib.util
import json
from pathlib import Path
import types
import pytest

REPO = Path('/home/lenovo/projects/memory')
OUT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('audited_conftest', REPO / 'tests/conftest.py')
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)
production = REPO / helper.PK_ANALYSIS_MANIFEST
before = production.read_bytes()
private = OUT / 'private-manifest-probe.json'
checks = {}
old = json.loads(before)
helper.pk_current_memsub_manifest(private)
new = json.loads(private.read_text())
checks['only private source fingerprint changes'] = {k for k in old.keys() | new.keys() if old.get(k) != new.get(k)} == {'memsub_source_sha256'}


def load_cp():
    spec = importlib.util.spec_from_file_location('audit_control_plane', REPO / 'modal-runners/modal-m4-sgm-p2p5-pk-control-plane-reaper-logic.py')
    cp = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cp)
    return cp


runner = types.SimpleNamespace(load_cp=load_cp)
monkeypatch = pytest.MonkeyPatch()
try:
    helper.pk_runner_uses_current_memsub_manifest(monkeypatch, runner, private)
    cp = runner.load_cp()
    checks['runner helper selects actual private manifest'] = cp.MANIFEST_FILE == str(private)
    checks['actual launch check accepts current private fixture'] = cp.launch_manifest_problem(REPO) is None
    data = json.loads(private.read_text())
    data['memsub_source_sha256'] = '0' * 64
    private.write_text(json.dumps(data))
    checks['actual launch check refuses source mismatch'] = cp.launch_manifest_problem(REPO) == 'dependency manifest: memsub source differs'
    helper.pk_current_memsub_manifest(private)
    data = json.loads(private.read_text())
    target = sorted(data['launch'])[0]
    data['launch'][target] = '0' * 64
    private.write_text(json.dumps(data))
    checks['actual launch check refuses file hash mismatch'] = cp.launch_manifest_problem(REPO) == f'dependency manifest: launch file {target} missing or changed'
    helper.pk_current_memsub_manifest(private)
finally:
    monkeypatch.undo()
checks['production manifest bytes remain unchanged'] = production.read_bytes() == before
checks['runner monkeypatch fully restored'] = runner.load_cp is load_cp
result = {'checks': checks, 'all_pass': all(checks.values()), 'production_manifest_sha256': hashlib.sha256(before).hexdigest(),
          'helper_sha256': hashlib.sha256((REPO / 'tests/conftest.py').read_bytes()).hexdigest(),
          'production_mutations': 0, 'model_calls': 0, 'cloud_calls': 0}
(OUT / 'independent-helper-results.json').write_text(json.dumps(result, indent=2))
print(json.dumps(result, indent=2))
assert result['all_pass']

"""Read-only package/input verification; no model construction or forward."""
import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
BASE = ROOT / 'plans/reports/claude-261008-2350-p2p5-taskhead-dead-start-address-diagnosis'
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
read = lambda p: json.loads(Path(p).read_text())
package = []
for line in (BASE / 'SHA256SUMS-package-r2.txt').read_text().splitlines():
    expected, name = line.split('  ', 1)
    path = (BASE / name).resolve()
    assert sha(path) == expected, name
    package.append({'file': str(path.relative_to(ROOT)), 'sha256': expected})
index = read(BASE / 'inputs-index.json')
assert len(index['entries']) == 14
assert len({e['name'] for e in index['entries']}) == 14
assert sum(e['kind'] == 'geometry' for e in index['entries']) == 12
assert [e['name'] for e in index['entries'][-2:]] == [
    'toy-p2c-curriculum-taskhead-s0-grad-at-init', 'qwen-probe-taskhead-s0-grad-at-init']
checks = []
for e in index['entries']:
    r = {'name': e['name'], 'device': e['device'], 'kind': e['kind']}
    for key in ('manifest', 'telemetry'):
        assert sha(ROOT / e[key]) == e[key + '_sha256'], (e['name'], key)
    man = read(ROOT / e['manifest'])
    cfg = man['pilot_config']
    assert (cfg['n_bindings'], cfg['n_queries'], cfg['filler_len'], cfg['batch'], cfg['eval_batches']) == (32, 4, 40, 16, 4)
    # Original toy manifests predate the explicit backbone field; PilotConfig
    # defaults to tiny, as the runtime also does when reading these manifests.
    assert e['device'] == ('cpu' if cfg.get('backbone', 'tiny') == 'tiny' else 'cuda')
    step = 0
    if e['params'] != 'init':
        assert sha(ROOT / e['params']) == e['params_sha256']
        if e['params'].endswith('.pt'):
            assert e['expected_step'] == 100
            step = 100
            state = read((ROOT / e['params']).parent / 'state.json')
            link = next(x for x in state['chain'] if x['file'] == Path(e['params']).name)
            assert link['sha256'] == e['params_sha256'] and link['step'] == 100
        else:
            step = cfg['steps']
            assert man['trained_parameters_sha256'] == e['params_sha256']
    if e['kind'] == 'geometry':
        evals = [json.loads(line) for line in (ROOT / e['telemetry']).read_text().splitlines() if line.strip()]
        matching = [x['eval'] for x in evals if x.get('step') == step and isinstance(x.get('eval'), dict)]
        assert len(matching) == 1
        r['expected_telemetry_step'] = step
    checks.append(r)
toy = read(BASE / 'toy-only-script-test-r2/run.json')
script = ROOT / 'scripts/sgm-p2p5-taskhead-dead-start-address-diagnosis.py'
assert toy['script_sha256'] == sha(script)
assert toy['identity']['memsub_source_sha256'] == index['run']['memsub_source_sha256']
assert len(toy['done']) == 5 and toy['finished_utc']
for e in toy['done']:
    rep = read(BASE / 'toy-only-script-test-r2' / (e['name'] + '.json'))
    if rep['kind'] == 'geometry':
        assert rep['training_dev_eval_check']['status'] == 'reproduced'
for path, name in ((script, 'script-at-167f3c3.py'), (BASE / 'inputs-index.json', 'index-at-167f3c3.json'),
                   (BASE / 'SHA256SUMS-package-r2.txt', 'SHA256SUMS-reviewed-package.txt')):
    shutil.copyfile(path, OUT / name)
report = {'package_files_checked': package, 'input_checks': checks,
          'toy_retained_evidence_consistent': True, 'model_forward': False,
          'script_sha256': sha(script), 'index_sha256': sha(BASE / 'inputs-index.json')}
(OUT / 'package-checks.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps({'package_files': len(package), 'inputs': len(checks), 'toy_retained_evidence_consistent': True}))

"""Independent local CPU audit of terminal collection and the frozen reading."""
import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import torch
from safetensors.torch import load_file
from memsub.sgm import packed_slot_epoch_state as es
from memsub.sgm.synthetic_pilot_run import source_tree_sha256

def load(rel, name):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m

def read(path):
    return json.loads(Path(path).read_text())

def rows(path):
    return [json.loads(x) for x in Path(path).read_text().splitlines() if x.strip()]

L = load('modal-runners/modal-m4-sgm-p2p5-readout-probe-slot-logic.py', 'audit_logic')
PV = load(L.VALIDATOR_FILE, 'audit_validator')
local = ROOT / L.LOCAL_OUT / L.GROUP / L.SLOT
status = read(local / 'collect_status.json')
assert status['final_shutdown']['status'] == 'stopped_verified'
assert status['final_shutdown']['verification']['verified'] is True
assert status['evidence']['returncode'] == 0
assert status['poll'] == 'result'
assert status['result']['status'] == 'done'
assert status['final_shutdown']['verification']['container_rows'] == []
assert all(r['state'] == 'stopped' and int(r['tasks']) == 0 for r in status['final_shutdown']['verification']['app_rows'])
for f in ('collect_status.json', 'launch_provenance.json', 'call.json', 'guard.json', 'admission.json'):
    shutil.copyfile(local / f, OUT / f'collected-{f}')
prov = read(local / 'launch_provenance.json')
expected = prov['expected_identity']
assert source_tree_sha256(ROOT / 'memsub') == expected['memsub']
source_hashes = dict(expected['files'])
source_hashes['modal-runners/modal-m4-sgm-p2p5-readout-probe-slot-runner.py'] = expected['runner']
source_hashes[L.SLOT_LOGIC_FILE] = expected['slot_logic']
source_hashes[L.LIFETIME_LOGIC_FILE] = expected['lifetime_logic']
for path, sha in source_hashes.items():
    assert es.file_sha256(ROOT / path) == sha, path
snap = read(OUT / 'live-snapshot.json')
assert snap['remote_mutations'] is False
assert snap['dicts']['admission'] == read(local / 'admission.json')
assert sorted(snap['dicts']['admission']) == ['start-1']
guard = read(local / 'guard.json')
assert guard['app_id'] == guard['self_app_id'] == prov['deployed_app_id']
assert guard['deadline_epoch'] == prov['deadline_epoch']
assert abs(prov['deadline_epoch'] - prov['spawn_epoch'] - L.deadline_s(read(ROOT / L.LEDGER_FILE))) < 1e-5
assert guard['reaper_fired']['bound'] == prov['deployed_app_id']
assert guard['reaper_fired']['reason'] == 'deadline passed'
assert snap['inventory']['app']['rc'] == snap['inventory']['container']['rc'] == 0
assert snap['inventory']['container']['probe_rows'] == []
assert all(r['state'] == 'stopped' and int(r['tasks']) == 0 for r in snap['inventory']['app']['probe_rows'])
grid = L.probe_cells(read(ROOT / L.GRID_FILE))
registry = read(ROOT / L.REGISTRY_FILE)['learned']
schema = read(ROOT / L.SCHEMA_FILE)['learned']
ev = ROOT / status['evidence_dir'] / L.SLOT
report = {'at_utc': datetime.now(timezone.utc).isoformat(), 'source_bindings_checked': source_hashes,
          'memsub_sha256': expected['memsub'], 'only_start_1': True,
          'independent_live_stopped_zero_tasks_zero_containers': True, 'cells': {}}
for cell, pilot in grid.items():
    cd = ev / 'cells' / cell
    rec = es.read_record(cd, 1)
    assert rec['state'] == 'COMPLETE' and rec['recovery'] == 'fresh'
    assert rec['identity']['runner_expected'] == expected
    assert {k: rec['identity'][k] for k in expected} == expected
    assert es.file_sha256(cd / 'epoch-1/state.json') == es.file_sha256(OUT / 'remote-metadata' / cell / 'state.json')
    assert es.canonical_walk(rec, 1) == [rec]
    assert [g['step'] for g in rec['chain']] == list(range(50, 1501, 50))
    assert es.verify_chain(cd, rec['chain']) is None
    att = ev / rec['outputs']['attempt']
    assert read(att / 'done.json')['outputs'] == rec['outputs']['files']
    assert PV.validate_probe_outputs(att / 'out', rec['outputs']['files'], pilot, L.EVAL,
                                     expected['memsub'], registry, schema) is None
    cell_report = L.cell_report(cd, pilot, [1], expected['memsub'], registry, schema,
                                terminal=True, validate=PV.validate_probe_outputs)
    assert cell_report['state'] == 'COMPLETE' and cell_report['validation'] == 'valid'
    assert status['cells'][cell] == cell_report
    phys = rows(att / 'physical-updates.jsonl')
    assert [r['update'] for r in phys] == list(range(1500))
    assert es.file_sha256(att / 'physical-updates.jsonl') == es.file_sha256(OUT / 'remote-metadata' / cell / 'attempt-1/physical-updates.jsonl')
    assert rec['physical'] == {'last_observed_update': 1499, 'observed_updates': 1500, 'resume_step': 0}
    ck = torch.load(cd / 'epoch-1' / rec['chain'][-1]['file'], map_location='cpu', weights_only=True)
    trained = load_file(str(att / 'out/trained_parameters.safetensors'))
    tensors = {f'adapters.{n}': v for n, v in ck['adapters'].items()}
    tensors.update({f'head.{n}': v for n, v in ck['head'].items()})
    assert set(trained) == set(tensors)
    assert all(torch.equal(v, tensors[n]) for n, v in trained.items())
    assert ck['cuda_rng']
    data = rows(att / 'out/per_example_results.jsonl')
    key = lambda r: (r['batch'], r['episode'], r['episode_hash'], r['query'])
    base = {key(r): r['pred'] for r in data if r['intervention'] == 'none'}
    prediction_changes = {iv: sum(r['pred'] != base[key(r)] for r in data if r['intervention'] == iv)
                          for iv in ('bank_derange', 'coord_shuffle', 'read_offset', 'query_off')}
    metrics = read(att / 'out/metrics.json')
    report['cells'][cell] = {'validation': 'valid', 'state': 'COMPLETE', 'physical_updates': len(phys),
                            'checkpoint_hashes_checked': len(rec['chain']),
                            'output_hashes_checked': len(rec['outputs']['files']),
                            'terminal_checkpoint_equals_trained_tensors': True,
                            'cuda_rng_devices': len(ck['cuda_rng']),
                            'physical_last_update_utc': datetime.fromtimestamp(phys[-1]['t_end'], timezone.utc).isoformat(),
                            'wall_seconds': metrics['wall_seconds'],
                            'heldout_none': {k: metrics['final']['heldout_none'][k] for k in ('accuracy', 'correct', 'total')},
                            'prediction_changes_vs_none': prediction_changes}
reading_path = OUT / 'reading-independent.json'
p = subprocess.run([sys.executable, 'scripts/sgm-p2p5-readout-probe-reading.py', '--out', str(reading_path)],
                   cwd=ROOT, capture_output=True, text=True, timeout=60)
(OUT / 'reading-independent.log').write_text(p.stdout + p.stderr)
assert p.returncode == 0, (p.returncode, p.stdout, p.stderr)
reading = read(reading_path)
report['reading'] = reading['reading']
report['contrast'] = reading.get('contrast')
report['bank_dependence'] = reading.get('bank_dependence')
report['accuracy'] = reading.get('accuracy')
report['billing'] = 'actual charges not audited; cap remains 40.75 USD'
report['remote_mutations_by_audit'] = False
(OUT / 'review-evidence.json').write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
print(json.dumps(report, indent=2, sort_keys=True))

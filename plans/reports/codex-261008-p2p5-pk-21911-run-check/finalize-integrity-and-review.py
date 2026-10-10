"""Close the saved-output audit with explicit, preserved local-copy discrepancies."""
import hashlib
import json
import zipfile
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
BASE = ROOT / 'plans/261008-0144-m4-sgm-p2p5-readout-recipe-rescue-probe'
local = BASE / 'p2p5-readout-probe-v1/taskhead-learned-n32'
ev = local / 'volume-evidence/collect-1/taskhead-learned-n32/cells'
read = lambda p: json.loads(Path(p).read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
remote = read(OUT / 'remote-checkpoint-verification.json')
assert remote['all_match_recorded_hashes'] is True and len(remote['files']) == 3
supplements = {}
crc = []
for f in remote['files']:
    cell = f['remote'].split('/')[-3]
    name = Path(f['remote']).name
    fresh = OUT / f['audit_path']
    initial = ev / cell / 'epoch-1' / name
    assert sha(fresh) == f['expected_sha256']
    assert sha(initial) == f['collect_1_sha256'] != f['expected_sha256']
    with zipfile.ZipFile(initial) as z:
        bad = z.testzip()
    with zipfile.ZipFile(fresh) as z:
        new_bad = z.testzip()
    assert bad is not None and new_bad is None
    crc.append({'cell': cell, 'file': name, 'collect_1_bad_zip_member': bad, 'supplemental_crc': 'PASS'})
    supplements[(cell, name)] = fresh
generations = []
constants = {}
for cell_dir in sorted(ev.iterdir()):
    rec = read(cell_dir / 'epoch-1/state.json')
    for link in rec['chain']:
        key = (cell_dir.name, link['file'])
        path = supplements.get(key, cell_dir / f"epoch-{link['epoch']}" / link['file'])
        assert sha(path) == link['sha256']
        generations.append({'cell': cell_dir.name, 'file': link['file'], 'verified_sha256': link['sha256'],
                            'verified_path': str(path.relative_to(ROOT)), 'supplemental': key in supplements})
    data = [json.loads(x) for x in (cell_dir / 'epoch-1/attempt-1/out/per_example_results.jsonl').read_text().splitlines()]
    predictions = sorted({r['pred'] for r in data})
    constants[cell_dir.name] = {'row_count': len(data), 'unique_predictions': predictions}
assert len(generations) == 60
independent = read(OUT / 'reading-independent.json')
peer = read(BASE / 'reading-v1/probe-reading.json')
assert independent == peer
manifest_counts = {}
for name in ('SHA256SUMS-terminal.txt', 'SHA256SUMS-volume-evidence-binaries-not-in-git.txt'):
    lines = (BASE / 'terminal' / name).read_text().splitlines()
    for line in lines:
        expected, path = line.split('  ', 1)
        assert sha(ROOT / path) == expected, path
    manifest_counts[name] = len(lines)
billing_file = BASE / 'terminal/billing-hourly-prelim-20261008T1635Z.json'
app_id = read(local / 'launch_provenance.json')['deployed_app_id']
app_rows = [r for r in read(billing_file) if r['object_id'] == app_id]
assert len(app_rows) == 10
total = sum((Decimal(r['cost']) for r in app_rows), Decimal(0))
report = {'output_validation': 'PASS for both cells using unchanged frozen validator',
          'reading_matches_peer_exactly': True, 'reading': independent['reading'],
          'collect_1_checkpoint_integrity': 'FAIL: 3 local files have SHA mismatch and ZIP CRC failure; preserved unchanged',
          'supplemental_remote_reads': 'PASS: all 3 match original acknowledged hashes and pass ZIP CRC',
          'verified_generation_count_including_supplements': len(generations),
          'verified_generations': generations, 'crc_checks': crc, 'constant_predictions': constants,
          'peer_manifest_file_counts_verified': manifest_counts,
          'billing': {'source': str(billing_file.relative_to(ROOT)), 'sha256': sha(billing_file),
                      'app_id': app_id, 'app_rows': len(app_rows), 'saved_hourly_app_total_usd': str(total),
                      'status': 'PRELIMINARY app-hourly subtotal; not settled cap reconciliation and excludes separately attributed builds'},
          'remaining': ['settled billing including build attribution and backfill'],
          'remote_mutations_by_audit': False}
(OUT / 'final-review-evidence.json').write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
print(json.dumps({k:v for k,v in report.items() if k != 'verified_generations'}, indent=2, sort_keys=True))

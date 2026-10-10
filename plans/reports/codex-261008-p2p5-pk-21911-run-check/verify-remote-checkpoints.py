"""Read only the three discrepant remote checkpoints into separate audit files."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import modal

OUT = Path(__file__).resolve().parent
bad = json.loads((OUT / 'checkpoint-hash-checks.json').read_text())
vol = modal.Volume.from_name('memsub-artifacts', create_if_missing=False)
report = {'started_utc': datetime.now(timezone.utc).isoformat(), 'remote_mutations': False, 'files': []}
for cell, result in bad.items():
    remote_dir = f'm4-sgm/p2p5-readout-probe-v1/taskhead-learned-n32/cells/{cell}/epoch-1'
    entries = {Path(e.path).name: e.size for e in vol.listdir(remote_dir)}
    for row in result['mismatches']:
        remote = remote_dir + '/' + row['file']
        data = b''.join(vol.read_file(remote))
        path = OUT / 'supplemental-remote-checkpoints' / cell / row['file']
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as f:
            f.write(data)
        item = {'remote': remote, 'audit_path': str(path.relative_to(OUT)),
                'remote_listed_size': entries[row['file']], 'downloaded_size': len(data),
                'expected_sha256': row['expected'], 'sha256': hashlib.sha256(data).hexdigest(),
                'collect_1_sha256': row['actual'], 'collect_1_bytes': row['bytes']}
        item['matches_recorded_hash'] = item['sha256'] == item['expected_sha256']
        report['files'].append(item)
        (OUT / 'remote-checkpoint-verification.json').write_text(json.dumps(report, indent=2) + '\n')
        print(json.dumps(item), flush=True)
report['ended_utc'] = datetime.now(timezone.utc).isoformat()
report['all_match_recorded_hashes'] = all(x['matches_recorded_hash'] for x in report['files'])
(OUT / 'remote-checkpoint-verification.json').write_text(json.dumps(report, indent=2) + '\n')

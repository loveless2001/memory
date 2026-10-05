"""Archive exactly the consumed treatment, baseline, and group inputs.

No evaluation or input mutation. Paths are indexed by the separate launch
group, preserving top-up provenance. All parameter inputs are small adapters.
"""
import gzip
import hashlib
import io
import json
import sys
import tarfile
from pathlib import Path

out = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parents[1]
plan = out.parent.parent
report = json.loads((out / 'step2-readings.json').read_text())
inputs = {}
for group, record in report['groups'].items():
    for filename in ('launch_provenance.json', 'grid.json'):
        inputs[f'{group}/{filename}'] = Path(record['runs']) / filename
for rid, index in report['index'].items():
    for filename, digest in index['input_sha256'].items():
        path = Path(index['mirror']) / rid / filename
        assert hashlib.sha256(path.read_bytes()).hexdigest() == digest
        inputs[f"{index['group']}/{rid}/{filename}"] = path
for name, baseline in report['baselines'].items():
    n, seed = map(int, name[1:].split('-s'))
    rid = f'main-learned-n{n}-s{seed}'
    for filename in ('run_manifest.json', 'trained_parameters.safetensors'):
        inputs[f'p2-load-sweep-v2/{rid}/{filename}'] = plan / 'runs/p2-load-sweep-v2-volume-mirror' / rid / filename
archive = out / 'input-evidence.tar.gz'
manifest = {}
with archive.open('xb') as target, gzip.GzipFile(filename='', fileobj=target, mode='wb', mtime=0) as compressed:
    with tarfile.open(fileobj=compressed, mode='w') as tar:
        for name, path in sorted(inputs.items()):
            data = path.read_bytes()
            item = tarfile.TarInfo(name)
            item.size, item.mode = len(data), 0o644
            tar.addfile(item, io.BytesIO(data))
            manifest[name] = {'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data)}
record = {'archive': archive.name, 'archive_sha256': hashlib.sha256(archive.read_bytes()).hexdigest(),
          'archive_bytes': archive.stat().st_size, 'members': manifest}
(out / 'input-evidence-manifest.json').write_text(json.dumps(record, indent=2) + '\n')
print(json.dumps({k: v for k, v in record.items() if k != 'members'}, indent=2))

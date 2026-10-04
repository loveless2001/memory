"""Read-only verification of the final paired-repair artifact bundle."""
import hashlib
import json
import runpy
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def read(path): return json.loads(path.read_text())


def check(files):
    for name, expected in files.items():
        path = ROOT / name
        assert path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == expected, name


def main():
    manifest = read(HERE / 'result-manifest.json')
    check(manifest['files']); check(read(HERE / 'preflight/freeze.json')['files'])
    protected = read(HERE / 'preflight/protected.json'); check(protected)
    check(read(HERE / 'continuation-preflight/freeze.json')['files'])
    check(read(HERE / 'continuation-preflight/protected.json'))
    summary = runpy.run_path(str(HERE / 'summarize.py'))['summarize']()
    assert summary == read(HERE / 'summary.json')
    assert summary['captures'] == 144 and not summary['training_admission']
    for run in ('run', 'continuation-run'):
        app = read(HERE / run / 'app-status.json')['app']
        assert app['state'] == 'stopped' and int(app['tasks']) == 0
        assert app['app_id'] == read(HERE / run / 'billing.json')['app_id']
    print(json.dumps({'status': 'PASS', 'result_files': len(manifest['files']),
        'protected_files_unchanged': len(protected), 'reviewed_captures': 144,
        'gates': summary['gates'], 'training_labels': 0}))


if __name__ == '__main__': main()

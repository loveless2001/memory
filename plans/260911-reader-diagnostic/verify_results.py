"""Read-only validation of the frozen diagnostic report and its evidence."""
import hashlib
import json
import runpy
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def read(path):
    return json.loads(path.read_text())


def check_files(files):
    for name, expected in files.items():
        path = ROOT / name
        assert path.is_file(), name
        assert hashlib.sha256(path.read_bytes()).hexdigest() == expected, name


def main():
    manifest = read(HERE / 'result-manifest.json')
    check_files(manifest['files'])
    check_files(read(HERE / 'preflight/freeze.json')['files'])
    protected = read(HERE / 'preflight/protected.json')
    check_files(protected)
    summary = runpy.run_path(str(HERE / 'summarize.py'))['summarize']()
    assert summary == read(HERE / 'summary.json')
    assert summary['captures'] == 96 and not summary['training_admission']
    assert sum(c.get('pass', 0) for c in summary['counts_by_arm'].values()) == 58
    assert not summary['primary_json_chronological_24_of_24']
    app = read(HERE / 'run/app-status.json')['app']
    assert app['state'] == 'stopped' and int(app['tasks']) == 0
    assert app['app_id'] == read(HERE / 'run/billing.json')['app_id']
    print(json.dumps({'status': 'PASS', 'result_files': len(manifest['files']),
                      'protected_files_unchanged': len(protected),
                      'reviewed_captures': 96, 'strict_pass': 58,
                      'primary_gate': 'FAIL', 'training_labels': 0}))


if __name__ == '__main__':
    main()

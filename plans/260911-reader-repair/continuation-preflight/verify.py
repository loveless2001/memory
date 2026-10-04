"""Read-only verification of the original schedule and frozen missing suffix."""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from prepare import read, sha, ROOT, PARENT, RUN


def main():
    freeze = read(HERE / 'freeze.json')
    for n, h in freeze['files'].items(): assert sha(ROOT / n) == h, n
    protected = read(HERE / 'protected.json')
    for n, h in protected.items(): assert sha(ROOT / n) == h, n
    assert freeze['parent_freeze_sha256'] == sha(PARENT / 'freeze.json')
    for name in ('inputs.json', 'gate-indices.json'): assert (HERE / name).read_bytes() == (PARENT / name).read_bytes()
    config = read(HERE / 'runtime-config.json'); expected = read(PARENT / 'runtime-config.json')
    start = len(read(RUN / 'captures.json')); expected['capture_start_index'] = start
    assert config == expected and 0 < start < 144
    assert read(HERE / 'cpu-checks.json')['parent_captures_sha256'] == sha(RUN / 'captures.json')
    print(json.dumps({'status': 'PASS', 'saved_prefix': start, 'missing_suffix': 144-start,
        'protected_files': len(protected), 'training_labels': 0}))


if __name__ == '__main__': main()

"""Freeze the uncollected suffix only after the first run is terminal."""
import ast
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PARENT = HERE.parent / 'preflight'
RUN = HERE.parent / 'run'


def read(p): return json.loads(p.read_text())
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def write(name, value): (HERE / name).write_text(json.dumps(value, indent=2) + '\n')


def main():
    assert not (HERE / 'freeze.json').exists()
    status = read(RUN / 'status.json'); captures = read(RUN / 'captures.json')
    assert status['status'] == 'failed' and 'time ceiling' in status['error']
    assert read(RUN / 'cache-verdict.json')['pass']
    app = read(RUN / 'app-status.json')['app']
    assert app['state'] == 'stopped' and int(app['tasks']) == 0
    start = len(captures); assert 0 < start < 144
    assert [c['input_index'] for c in captures] == list(range(start))
    inputs = read(PARENT / 'inputs.json')
    for i, c in enumerate(captures):
        assert c['messages'] == inputs[i]['messages'] and (c['id'], c['arm']) == (inputs[i]['id'], inputs[i]['arm'])
    for name, expected in read(RUN / 'artifact-hashes.json').items(): assert sha(RUN / name) == expected
    protected = read(PARENT / 'protected.json')
    for directory in (PARENT, RUN):
        for p in directory.rglob('*'):
            if p.is_file() and '__pycache__' not in p.parts: protected[str(p.relative_to(ROOT))] = sha(p)
    for n, h in read(PARENT / 'freeze.json')['files'].items(): protected[n] = h
    for n, h in protected.items(): assert sha(ROOT / n) == h, n
    # Prove that only the suffix skip was added to the frozen runtime AST.
    old = ast.parse((ROOT / 'experiments/context_policy/reader_repair.py').read_text())
    new = ast.parse((ROOT / 'experiments/context_policy/reader_repair_continuation.py').read_text())
    removed = 0
    for node in ast.walk(new):
        if isinstance(node, ast.For) and isinstance(node.target, ast.Tuple) and isinstance(node.iter, ast.Call) and isinstance(node.iter.func, ast.Name) and node.iter.func.id == 'enumerate':
            assert isinstance(node.body[0], ast.If) and isinstance(node.body[0].body[0], ast.Continue)
            assert ast.unparse(node.body[0].test) == "index < config['capture_start_index']"
            node.body.pop(0); removed += 1
    assert removed == 1 and ast.dump(old) == ast.dump(new)
    for name in ('inputs.json', 'gate-indices.json'): (HERE / name).write_bytes((PARENT / name).read_bytes())
    config = read(PARENT / 'runtime-config.json'); config['capture_start_index'] = start
    write('runtime-config.json', config)
    sources = read(PARENT / 'runtime-sources.json')
    sources['experiments/context_policy/reader_repair_continuation.py'] = sha(ROOT / 'experiments/context_policy/reader_repair_continuation.py')
    write('runtime-sources.json', sources); write('protected.json', protected)
    write('cpu-checks.json', {'status': 'PASS', 'saved_prefix': start, 'missing_suffix': 144-start,
        'identical_inputs': True, 'runtime_ast_diff_only_suffix_skip': True,
        'parent_captures_sha256': sha(RUN / 'captures.json'), 'protected_files': len(protected)})
    paths = [p for p in HERE.iterdir() if p.is_file()] + [ROOT / n for n in ('experiments/context_policy/reader_repair_continuation.py', 'modal-runners/modal-reader-repair-continuation.py')]
    write('freeze.json', {'files': {str(p.relative_to(ROOT)): sha(p) for p in paths},
        'parent_freeze_sha256': sha(PARENT / 'freeze.json'), 'references_mounted': False})
    print((HERE / 'cpu-checks.json').read_text())


if __name__ == '__main__': main()

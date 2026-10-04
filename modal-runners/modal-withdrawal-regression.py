"""One bounded frozen-note development probe. No retries or training."""
import json
import re
from pathlib import Path
import modal

app = modal.App('memsub-context-policy-withdrawal-regression')
image = (modal.Image.debian_slim(python_version='3.12')
    .pip_install('torch==2.7.1', 'transformers==4.55.2', 'safetensors==0.5.3',
                 'peft==0.17.0', 'accelerate==1.10.1', 'numpy==2.2.6')
    .env({'HF_HUB_OFFLINE': '1', 'TRANSFORMERS_OFFLINE': '1', 'TOKENIZERS_PARALLELISM': 'false'})
    .add_local_dir('experiments/context_policy', '/root/repo/experiments/context_policy', ignore=['**/__pycache__/**', '**/*.pyc'])
    .add_local_file('CONTEXT-POLICY.md', '/root/repo/CONTEXT-POLICY.md')
    .add_local_file('pyproject.toml', '/root/repo/pyproject.toml')
    .add_local_file('modal-runners/modal-context-policy.py', '/root/repo/modal-context-policy.py')
    .add_local_file('modal-runners/modal-withdrawal-regression.py', '/root/repo/modal-withdrawal-regression.py')
    .add_local_file('plans/260910-context-policy/20260910-v2-withdrawal-regression-data/reader-input.json', '/root/reader-input.json')
    .add_local_file('plans/260910-context-policy/20260910-v2-withdrawal-regression-data/notes.json', '/root/notes.json')
    .add_local_file('plans/260910-context-policy/20260910-v2-withdrawal-regression-data/topics.json', '/root/topics.json')
    .add_local_file('plans/260910-context-policy/20260910-v2-withdrawal-regression-data/schedule.json', '/root/schedule.json'))
artifacts = modal.Volume.from_name('memsub-artifacts')
hf_cache = modal.Volume.from_name('memsub-hf-cache')


def run_path(run_id):
    if re.fullmatch(r'[a-z0-9][a-z0-9-]{0,79}', run_id) is None:
        raise ValueError('invalid run ID')
    return Path('/artifacts/context-policy-v2') / run_id


def manifest(root, remote=False):
    import hashlib
    from experiments.context_policy.preflight import source_manifest
    result = source_manifest(root, remote)
    path = root / ('modal-withdrawal-regression.py' if remote else 'modal-runners/modal-withdrawal-regression.py')
    result['modal-runners/modal-withdrawal-regression.py'] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


@app.function(image=image, gpu='H100!', cpu=4, memory=32768,
              volumes={'/artifacts': artifacts, '/root/.cache/huggingface': hf_cache},
              timeout=900, retries=0, max_containers=1, scaledown_window=2)
def probe(run_id: str, source_sha: str, input_hashes: dict):
    import hashlib
    import sys
    import time
    import traceback
    sys.path.insert(0, '/root/repo')
    from experiments.context_policy.preflight import canonical, digest
    from experiments.context_policy.withdrawal_probe import run
    started = time.monotonic(); root = run_path(run_id)
    if root.exists():
        raise FileExistsError('run exists; no automatic retry')
    source = manifest(Path('/root/repo'), remote=True)
    if digest(source) != source_sha:
        raise ValueError('source binding mismatch')
    payloads = {}
    for name, expected in input_hashes.items():
        raw = (Path('/root') / name).read_bytes()
        if hashlib.sha256(raw).hexdigest() != expected:
            raise ValueError('input bytes changed: ' + name)
        payloads[name] = json.loads(raw)
    previous = json.loads((run_path('20260910-v2-numerics') / 'status.json').read_text())
    if previous['verdict'].get('selected_runtime') != 'fp32_math' or not previous['verdict']['pass']:
        raise ValueError('numerical preflight has not passed')
    config = json.loads(Path('/root/repo/experiments/context_policy/design.json').read_text())
    root.mkdir(parents=True)
    (root / 'manifest.json').write_bytes(canonical(dict(source_files=source, source_sha256=source_sha,
        input_hashes=input_hashes,
        config=config, no_references_mounted=True, stage='withdrawal_regression_v1_42_captures')))
    def deadline():
        if time.monotonic() - started >= 850:
            raise TimeoutError('15-minute reader probe ceiling; reserving artifact save time')
    result = {'run_id': run_id, 'status': 'starting'}
    try:
        result = run(config, payloads['reader-input.json'], payloads['notes.json'], payloads['topics.json'], payloads['schedule.json'], root, artifacts.commit, deadline)
        result.update(run_id=run_id, elapsed_seconds=time.monotonic()-started)
        return result
    except BaseException as exc:
        (root / 'error.txt').write_text(traceback.format_exc())
        result = dict(run_id=run_id, status='failed', error=str(exc), elapsed_seconds=time.monotonic()-started)
        raise
    finally:
        hashes = {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*')
                  if p.is_file() and p.name not in ('artifact-hashes.json', 'status.json')}
        (root / 'artifact-hashes.json').write_bytes(canonical(hashes))
        (root / 'status.json').write_bytes(canonical(result)); artifacts.commit()


@app.local_entrypoint()
def main(run_id: str = '20260910-v2-withdrawal-regression'):
    import hashlib
    import sys
    sys.path.insert(0, str(Path.cwd()))
    from experiments.context_policy.preflight import canonical, digest
    run_path(run_id)
    local = Path('plans/260910-context-policy') / run_id
    local.mkdir(parents=True, exist_ok=False)
    source = manifest(Path.cwd())
    frozen = json.loads(Path('plans/260910-context-policy/20260910-v2-withdrawal-regression-plan/freeze.json').read_text())
    for name, sha in frozen['files'].items():
        if hashlib.sha256(Path(name).read_bytes()).hexdigest() != sha:
            raise ValueError('prelaunch freeze changed: ' + name)
    data = Path('plans/260910-context-policy/20260910-v2-withdrawal-regression-data')
    input_hashes = {name: hashlib.sha256((data / name).read_bytes()).hexdigest()
                    for name in ('reader-input.json', 'notes.json', 'topics.json', 'schedule.json')}
    assert source == frozen['source_files']
    for name in source:
        target = local / 'source-snapshot' / name
        target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(Path(name).read_bytes())
    launch = dict(run_id=run_id, app_id=app.app_id, source_files=source, source_sha256=digest(source),
                  input_hashes=input_hashes, stage='withdrawal_regression_v1_42_captures')
    (local / 'launch.json').write_bytes(canonical(launch))
    call = probe.spawn(run_id, digest(source), input_hashes)
    launch['function_call_id'] = call.object_id
    (local / 'launch.json').write_bytes(canonical(launch))
    print('LAUNCHED ' + json.dumps(launch), flush=True)
    result = call.get()
    (local / 'remote-status.json').write_bytes(canonical(result))
    print('RESULT ' + json.dumps(result), flush=True)

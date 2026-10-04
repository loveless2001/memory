"""Prepared broader evaluation; execution requires the explicit --execute flag."""
import hashlib
import json
import re
from pathlib import Path

import modal

PREP = Path('plans/260910-context-policy/20260911-v2-broader-reader-preflight')
INPUTS = ('reader-input.json', 'reader-views.json', 'note-worklist.json', 'schedule.json', 'runtime-config.json')
SOURCES = json.loads((PREP / 'runtime-sources.json').read_text()) if (PREP / 'runtime-sources.json').is_file() else {}
app = modal.App('memsub-context-policy-broader-reader')
image = (modal.Image.debian_slim(python_version='3.12')
    .pip_install('torch==2.7.1', 'transformers==4.55.2', 'safetensors==0.5.3',
                 'peft==0.17.0', 'accelerate==1.10.1', 'numpy==2.2.6')
    .env({'HF_HUB_OFFLINE':'1', 'TRANSFORMERS_OFFLINE':'1', 'TOKENIZERS_PARALLELISM':'false'}))
for name in SOURCES:
    image = image.add_local_file(name, '/root/repo/' + name)
for name in INPUTS:
    image = image.add_local_file(str(PREP / name), '/root/inputs/' + name)
image = image.add_local_file('modal-runners/modal-broader-reader.py', '/root/runner-source.py')
artifacts = modal.Volume.from_name('memsub-artifacts')
hf_cache = modal.Volume.from_name('memsub-hf-cache')


@app.function(image=image, gpu='H100!', cpu=4, memory=32768,
    volumes={'/artifacts':artifacts, '/root/.cache/huggingface':hf_cache},
    timeout=2400, retries=0, max_containers=1, scaledown_window=2)
def collect(run_id: str, source_hashes: dict, input_hashes: dict, runner_sha: str, preflight_sha: str):
    import sys
    import time
    import traceback
    sys.path.insert(0, '/root/repo')
    from experiments.context_policy.preflight import canonical
    from experiments.context_policy.broader_reader import run
    if re.fullmatch(r'[a-z0-9][a-z0-9-]{0,79}', run_id) is None:
        raise ValueError('invalid run ID')
    root = Path('/artifacts/context-policy-v2') / run_id
    if root.exists():
        raise FileExistsError('run exists; no automatic retries')
    started = time.monotonic()
    for name, expected in source_hashes.items():
        if hashlib.sha256((Path('/root/repo') / name).read_bytes()).hexdigest() != expected:
            raise ValueError('runtime source changed: ' + name)
    if hashlib.sha256(Path('/root/runner-source.py').read_bytes()).hexdigest() != runner_sha:
        raise ValueError('runner source changed')
    payloads = {}
    if set(input_hashes) != set(INPUTS):
        raise ValueError('input allowlist mismatch')
    for name, expected in input_hashes.items():
        raw = (Path('/root/inputs') / name).read_bytes()
        if hashlib.sha256(raw).hexdigest() != expected:
            raise ValueError('reader input changed: ' + name)
        payloads[name] = json.loads(raw)
    root.mkdir(parents=True)
    (root / 'manifest.json').write_bytes(canonical({'source_hashes':source_hashes, 'input_hashes':input_hashes,
        'runner_sha256':runner_sha, 'preflight_sha256':preflight_sha, 'references_mounted':False,
        'planned_captures':360, 'hard_timeout_seconds':2400, 'automatic_retries':0}))
    result = {'run_id':run_id, 'status':'starting'}
    def deadline():
        if time.monotonic()-started >= 2350:
            raise TimeoutError('forty-minute ceiling; reserving artifact-save time')
    try:
        result = run(payloads['runtime-config.json'], payloads['reader-input.json'], payloads['note-worklist.json'],
                     payloads['reader-views.json'], payloads['schedule.json'], root, artifacts.commit, deadline)
        result.update(run_id=run_id, elapsed_seconds=time.monotonic()-started)
        return result
    except BaseException as exc:
        (root / 'error.txt').write_text(traceback.format_exc())
        result = {'run_id':run_id, 'status':'failed', 'error':str(exc), 'elapsed_seconds':time.monotonic()-started}
        raise
    finally:
        hashes = {str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*')
                  if p.is_file() and p.name not in ('artifact-hashes.json', 'status.json')}
        (root / 'artifact-hashes.json').write_bytes(canonical(hashes))
        (root / 'status.json').write_bytes(canonical(result)); artifacts.commit()


@app.local_entrypoint()
def main(run_id: str = '20260911-v2-broader-reader', execute: bool = False):
    import subprocess
    import sys
    subprocess.run([sys.executable, str(PREP / 'verify.py')], check=True)
    if not execute:
        print('Preflight only. Proposed run: one H100, at most 40 minutes, no retries, 360 potential captures.')
        return
    if re.fullmatch(r'[a-z0-9][a-z0-9-]{0,79}', run_id) is None:
        raise ValueError('invalid run ID')
    local = PREP.parent / run_id
    local.mkdir(exist_ok=False)
    input_hashes = {name:hashlib.sha256((PREP / name).read_bytes()).hexdigest() for name in INPUTS}
    runner_sha = hashlib.sha256(Path('modal-runners/modal-broader-reader.py').read_bytes()).hexdigest()
    freeze_sha = hashlib.sha256((PREP / 'freeze.json').read_bytes()).hexdigest()
    launch = {'run_id':run_id, 'app_id':app.app_id, 'source_hashes':SOURCES, 'input_hashes':input_hashes,
              'runner_sha256':runner_sha, 'preflight_sha256':freeze_sha}
    for name in [*SOURCES, 'modal-runners/modal-broader-reader.py']:
        target = local / 'source-snapshot' / name
        target.parent.mkdir(parents=True,exist_ok=True); target.write_bytes(Path(name).read_bytes())
    (local / 'launch.json').write_text(json.dumps(launch,indent=2)+'\n')
    call = collect.spawn(run_id, SOURCES, input_hashes, runner_sha, freeze_sha)
    launch['function_call_id'] = call.object_id
    (local / 'launch.json').write_text(json.dumps(launch,indent=2)+'\n')
    print('LAUNCHED ' + json.dumps(launch), flush=True)
    result = call.get()
    (local / 'remote-status.json').write_text(json.dumps(result,indent=2)+'\n')
    print('RESULT ' + json.dumps(result), flush=True)

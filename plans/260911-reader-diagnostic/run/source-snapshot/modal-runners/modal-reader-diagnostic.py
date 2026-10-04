"""Run the user-authorized, bounded reader diagnostic."""
import hashlib
import json
from pathlib import Path
import modal

PREP=Path('plans/260911-reader-diagnostic/preflight')
SOURCES=json.loads((PREP/'runtime-sources.json').read_text()) if (PREP/'runtime-sources.json').exists() else {}
INPUT_NAMES=('runtime-config.json','inputs.json','gate-indices.json')
app=modal.App('memsub-reader-presentation-diagnostic')
image=(modal.Image.debian_slim(python_version='3.12').pip_install('torch==2.7.1','transformers==4.55.2',
    'safetensors==0.5.3','peft==0.17.0','accelerate==1.10.1','numpy==2.2.6')
    .env({'HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1','TOKENIZERS_PARALLELISM':'false'}))
for name in SOURCES:image=image.add_local_file(name,'/root/repo/'+name)
for name in INPUT_NAMES:image=image.add_local_file(str(PREP/name),'/root/inputs/'+name)
image=image.add_local_file('modal-runners/modal-reader-diagnostic.py','/root/runner-source.py')
artifacts=modal.Volume.from_name('memsub-artifacts');cache=modal.Volume.from_name('memsub-hf-cache')


@app.function(image=image,gpu='H100!',cpu=4,memory=32768,volumes={'/artifacts':artifacts,'/root/.cache/huggingface':cache},
    timeout=1200,retries=0,max_containers=1,scaledown_window=2)
def collect(source_hashes:dict,input_hashes:dict,runner_sha:str,freeze_sha:str):
    import sys,time,traceback
    sys.path.insert(0,'/root/repo')
    from experiments.context_policy.reader_diagnostic import run
    from experiments.context_policy.preflight import canonical
    started=time.monotonic();root=Path('/artifacts/reader-diagnostic/20260911-presentation')
    if root.exists():raise FileExistsError('Run exists; never overwrite or automatically retry')
    for n,h in source_hashes.items():
        if hashlib.sha256((Path('/root/repo')/n).read_bytes()).hexdigest()!=h:raise ValueError('source changed: '+n)
    if hashlib.sha256(Path('/root/runner-source.py').read_bytes()).hexdigest()!=runner_sha:raise ValueError('runner changed')
    payloads={}
    if set(input_hashes)!=set(INPUT_NAMES):raise ValueError('unexpected mounted input')
    for n,h in input_hashes.items():
        raw=(Path('/root/inputs')/n).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=h:raise ValueError('input changed: '+n)
        payloads[n]=json.loads(raw)
    root.mkdir(parents=True)
    (root/'manifest.json').write_bytes(canonical({'source_hashes':source_hashes,'input_hashes':input_hashes,
        'runner_sha256':runner_sha,'freeze_sha256':freeze_sha,'references_mounted':False,'planned_captures':96,
        'hard_timeout_seconds':1200,'retries':0}))
    def deadline():
        if time.monotonic()-started>=1150:raise TimeoutError('diagnostic time ceiling; saving partial artifacts')
    result={'status':'starting'}
    try:
        result=run(payloads['runtime-config.json'],payloads['inputs.json'],payloads['gate-indices.json'],root,artifacts.commit,deadline)
        result['elapsed_seconds']=time.monotonic()-started
        return result
    except BaseException as exc:
        (root/'error.txt').write_text(traceback.format_exc());result={'status':'failed','error':str(exc),'elapsed_seconds':time.monotonic()-started}
        raise
    finally:
        hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in root.iterdir() if p.is_file() and p.name not in ('status.json','artifact-hashes.json')}
        (root/'artifact-hashes.json').write_bytes(canonical(hashes));(root/'status.json').write_bytes(canonical(result));artifacts.commit()


@app.local_entrypoint()
def main():
    import subprocess,sys
    subprocess.run([sys.executable,str(PREP/'verify.py')],check=True)
    local=PREP.parent/'run';local.mkdir(exist_ok=False)
    ih={n:hashlib.sha256((PREP/n).read_bytes()).hexdigest() for n in INPUT_NAMES}
    runner_sha=hashlib.sha256(Path('modal-runners/modal-reader-diagnostic.py').read_bytes()).hexdigest()
    freeze_sha=hashlib.sha256((PREP/'freeze.json').read_bytes()).hexdigest()
    launch={'app_id':app.app_id,'source_hashes':SOURCES,'input_hashes':ih,'runner_sha256':runner_sha,'freeze_sha256':freeze_sha}
    for name in [*SOURCES,'modal-runners/modal-reader-diagnostic.py']:
        dest=local/'source-snapshot'/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(Path(name).read_bytes())
    (local/'launch.json').write_text(json.dumps(launch,indent=2)+'\n')
    call=collect.spawn(SOURCES,ih,runner_sha,freeze_sha);launch['function_call_id']=call.object_id
    (local/'launch.json').write_text(json.dumps(launch,indent=2)+'\n');print('LAUNCHED '+json.dumps(launch),flush=True)
    result=call.get();print('RESULT '+json.dumps(result),flush=True)

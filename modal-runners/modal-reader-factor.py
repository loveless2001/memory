"""Run the user-authorized, bounded reader diagnostic."""
import hashlib
import json
from pathlib import Path
import modal

PREP=Path('plans/260911-reader-factor/preflight')
SOURCES=json.loads((PREP/'runtime-sources.json').read_text()) if (PREP/'runtime-sources.json').exists() else {}
INPUT_NAMES=('runtime-config.json','static-inputs.json','extraction-inputs.json','questions.json','gate-ids.json')
app=modal.App('memsub-reader-factor')
image=(modal.Image.debian_slim(python_version='3.12').pip_install('torch==2.7.1','transformers==4.55.2',
    'safetensors==0.5.3','peft==0.17.0','accelerate==1.10.1','numpy==2.2.6')
    .env({'HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1','TOKENIZERS_PARALLELISM':'false'}))
for name in SOURCES:image=image.add_local_file(name,'/root/repo/'+name)
for name in INPUT_NAMES:image=image.add_local_file(str(PREP/name),'/root/inputs/'+name)
image=image.add_local_file('modal-runners/modal-reader-factor.py','/root/runner-source.py')
for name in ('adapter_model.safetensors','adapter_config.json'):
    image=image.add_local_file('plans/260911-reader-sft-v2/run/adapter/'+name,'/root/adapter/'+name)
artifacts=modal.Volume.from_name('memsub-reader-factor-artifacts',create_if_missing=True);cache=modal.Volume.from_name('memsub-hf-cache')


@app.function(image=image,gpu='H100!',cpu=4,memory=32768,volumes={'/artifacts':artifacts,'/root/.cache/huggingface':cache},
    timeout=1200,retries=0,max_containers=1,scaledown_window=2)
def collect(source_hashes:dict,input_hashes:dict,runner_sha:str,freeze_sha:str):
    import sys,time,traceback
    sys.path.insert(0,'/root/repo')
    from experiments.context_policy.reader_factor import run
    from experiments.context_policy.preflight import canonical
    started=time.monotonic();root=Path('/artifacts/reader-factor/20260911-v1')
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
        'runner_sha256':runner_sha,'freeze_sha256':freeze_sha,'gold_records_for_oracle_arms':True,
        'gold_query_interpretations_for_oracle_query':True,'final_answer_references_mounted':False,
        'prior_model_outputs_mounted':False,'dedicated_output_volume':True,'planned_answers':256,
        'planned_extractions':16,'hard_timeout_seconds':1200,'retries':0,'training':False}))
    def deadline():
        if time.monotonic()-started>=1100:raise TimeoutError('diagnostic time ceiling; saving partial artifacts')
    result={'status':'starting'}
    checkpoint_calls=0;actual_commits=0;commit_seconds=0.0
    def checkpoint():
        nonlocal checkpoint_calls,actual_commits,commit_seconds
        checkpoint_calls+=1
        if checkpoint_calls%20==0:
            t=time.monotonic();artifacts.commit();commit_seconds+=time.monotonic()-t;actual_commits+=1
    try:
        result=run(payloads['runtime-config.json'],payloads,root,checkpoint,deadline)
        result['elapsed_seconds']=time.monotonic()-started
        result['checkpointing']={'requests':checkpoint_calls,'batched_commits_before_final':actual_commits,'commit_seconds_before_final':commit_seconds,'final_commit_always':True}
        return result
    except BaseException as exc:
        (root/'error.txt').write_text(traceback.format_exc());result={'status':'failed','error':str(exc),'elapsed_seconds':time.monotonic()-started}
        raise
    finally:
        hashes={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file() and p.name not in ('status.json','artifact-hashes.json')}
        (root/'artifact-hashes.json').write_bytes(canonical(hashes));(root/'status.json').write_bytes(canonical(result));artifacts.commit()


@app.local_entrypoint()
def main():
    import subprocess,sys
    subprocess.run([sys.executable,str(PREP/'verify.py')],check=True)
    local=PREP.parent/'run';local.mkdir(exist_ok=False)
    ih={n:hashlib.sha256((PREP/n).read_bytes()).hexdigest() for n in INPUT_NAMES}
    runner_sha=hashlib.sha256(Path('modal-runners/modal-reader-factor.py').read_bytes()).hexdigest()
    freeze_sha=hashlib.sha256((PREP/'freeze.json').read_bytes()).hexdigest()
    launch={'app_id':app.app_id,'source_hashes':SOURCES,'input_hashes':ih,'runner_sha256':runner_sha,'freeze_sha256':freeze_sha}
    for name in [*SOURCES,'modal-runners/modal-reader-factor.py']:
        dest=local/'source-snapshot'/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(Path(name).read_bytes())
    (local/'launch.json').write_text(json.dumps(launch,indent=2)+'\n')
    call=collect.spawn(SOURCES,ih,runner_sha,freeze_sha);launch['function_call_id']=call.object_id
    (local/'launch.json').write_text(json.dumps(launch,indent=2)+'\n');print('LAUNCHED '+json.dumps(launch),flush=True)
    result=call.get();print('RESULT '+json.dumps(result),flush=True)

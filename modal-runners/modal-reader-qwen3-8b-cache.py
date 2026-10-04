"""CPU-only acquisition of the pinned reader; no inference or training."""
import hashlib,json
from pathlib import Path
import modal

ROOT=Path('plans/260911-reader-qwen3-8b/model')
app=modal.App('memsub-reader-qwen3-8b-cache')
image=modal.Image.debian_slim(python_version='3.12').pip_install('huggingface_hub==0.34.4')
cache=modal.Volume.from_name('memsub-hf-cache')


@app.function(image=image,cpu=4,memory=8192,volumes={'/root/.cache/huggingface':cache},timeout=1800,retries=0,max_containers=1,scaledown_window=2)
def acquire(info:dict,small_hashes:dict):
    from huggingface_hub import snapshot_download
    import time
    start=time.monotonic()
    names=[x['name'] for x in info['files'] if x['name']!='.gitattributes']
    path=Path(snapshot_download(info['model_id'],revision=info['revision'],allow_patterns=names,max_workers=4))
    records={}
    for item in info['files']:
        name=item['name']
        if name not in names:continue
        f=path/name;assert f.stat().st_size==item['size'],name
        h=hashlib.sha256()
        with f.open('rb') as stream:
            for block in iter(lambda:stream.read(8*1024*1024),b''):h.update(block)
        digest=h.hexdigest()
        if item['lfs_sha256']:assert digest==item['lfs_sha256'],name
        if name in small_hashes:assert digest==small_hashes[name],name
        records[name]={'size':f.stat().st_size,'sha256':digest}
    cache.commit()
    return {'status':'PASS','model_id':info['model_id'],'revision':info['revision'],
            'files':records,'cpu_only':True,'elapsed_seconds':time.monotonic()-start}


@app.local_entrypoint()
def main():
    info=json.loads((ROOT/'hub-info.json').read_text())
    output=ROOT/'cache-acquisition.json'
    if output.exists():raise FileExistsError('Acquisition already recorded')
    result=acquire.remote(info,json.loads((ROOT/'local-file-hashes.json').read_text()))
    result['app_id']=app.app_id
    result['runner_sha256']=hashlib.sha256(Path('modal-runners/modal-reader-qwen3-8b-cache.py').read_bytes()).hexdigest()
    output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))

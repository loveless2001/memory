"""Download only the frozen public histories, with pinned remote object checks."""
import json,hashlib,datetime,urllib.request
from pathlib import Path
from huggingface_hub import HfApi
from experiments.context_policy.preflight import canonical
from experiments.context_policy.personamem import reader_history
PLAN=Path(__file__).resolve().parent
ROOT=PLAN.parents[2]
OUT=PLAN.parent/'20260910-v2-broader-eval-data'
def main():
    selection=json.loads((PLAN/'selection.json').read_text())
    for name,sha in selection['files'].items():assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==sha,name
    assert not OUT.exists();OUT.mkdir()
    api=HfApi(token=False)
    infos=api.get_paths_info(repo_id=selection['source_dataset'],paths=[r['path'] for r in selection['selected']],revision=selection['revision'],repo_type='dataset',token=False)
    info={x.path:x for x in infos}
    meta=[]
    for row in selection['selected']:
        x=info[row['path']]
        assert x.lfs is None,'unexpected large-file object; explicit handling required'
        meta.append(dict(persona_id=row['persona_id'],path=x.path,oid=x.blob_id,size=x.size))
    (OUT/'remote-metadata.json').write_bytes(canonical(meta))
    downloaded=[];histories={}
    for row in meta:
        url='https://huggingface.co/datasets/'+selection['source_dataset']+'/resolve/'+selection['revision']+'/'+row['path']
        with urllib.request.urlopen(url,timeout=60) as response:raw=response.read()
        assert len(raw)==row['size']
        assert hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()==row['oid']
        payload=json.loads(raw);assert str(payload['metadata']['persona_id'])==row['persona_id']
        target=OUT/'raw'/Path(row['path']).name;target.parent.mkdir(exist_ok=True);target.write_bytes(raw)
        sanitized=reader_history(payload);histories[row['persona_id']]=sanitized
        downloaded.append(dict(row,local_path=str(target.relative_to(ROOT)),sha256=hashlib.sha256(raw).hexdigest(),visible_history_sha256=hashlib.sha256(canonical(sanitized)).hexdigest(),turns=len(sanitized),profile_system_removed=True))
        (OUT/'source-manifest.json').write_bytes(canonical(dict(revision=selection['revision'],files=downloaded)))
        print(json.dumps(dict(downloaded=len(downloaded),persona=row['persona_id'],bytes=len(raw))),flush=True)
    (OUT/'histories.json').write_bytes(canonical(histories))
    (OUT/'acquisition.json').write_bytes(canonical(dict(completed_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),histories=len(histories),bytes=sum(r['size'] for r in meta),source_sha256=hashlib.sha256((PLAN/'selection.json').read_bytes()).hexdigest(),authoring_fields='sanitized role/content only',private_source_labels_read=False)))
if __name__=='__main__':main()

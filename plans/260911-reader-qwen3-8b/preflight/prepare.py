"""Freeze unchanged paired messages under the official larger reader."""
import hashlib,json,sys
from pathlib import Path
from collections import Counter
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
PARENT=ROOT/'plans/260911-reader-repair'
MODEL=HERE.parent/'model'
sys.path.insert(0,str(ROOT))
from transformers import AutoTokenizer
from experiments.context_policy.reader_qwen3_8b import answer_prefix_ids,SYSTEMS
from experiments.context_policy.preflight import digest

def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(name,x):(HERE/name).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')

def main():
    assert not (HERE/'freeze.json').exists()
    info=read(MODEL/'hub-info.json');acquired=read(MODEL/'cache-acquisition.json')
    assert acquired['status']=='PASS' and acquired['cpu_only'] and acquired['revision']==info['revision']
    for n,h in read(MODEL/'local-file-hashes.json').items():
        assert sha(MODEL/'tokenizer'/n)==h and acquired['files'][n]['sha256']==h
    for f in info['files']:
        if f['lfs_sha256']:assert acquired['files'][f['name']]['sha256']==f['lfs_sha256']
    config=read(PARENT/'preflight/runtime-config.json')
    config.update(model_id=info['model_id'],model_revision=info['revision'],enable_thinking=False)
    tok=AutoTokenizer.from_pretrained(MODEL/'tokenizer',local_files_only=True)
    cases=read(PARENT/'preflight/cases.json');inputs=read(PARENT/'preflight/inputs.json')
    for r in inputs:
        assert r['messages'][0]['content']==SYSTEMS[r['arm']]
        ids=answer_prefix_ids(tok,r['messages']);r['input_tokens']=len(ids)
        assert len(ids)+192<=8192
        assert tok.decode(ids,skip_special_tokens=False).endswith('<think>\n\n</think>\n\nANSWER\n')
    for n in ('cases.json','gate-indices.json'):(HERE/n).write_bytes((PARENT/'preflight'/n).read_bytes())
    sources=read(PARENT/'preflight/runtime-sources.json')
    sources['experiments/context_policy/reader_qwen3_8b.py']=sha(ROOT/'experiments/context_policy/reader_qwen3_8b.py')
    for n,h in sources.items():assert sha(ROOT/n)==h,n
    protected={}
    for directory in ('plans/260910-context-policy','plans/260911-reader-diagnostic','plans/260911-reader-repair','experiments/context_policy','modal-runners'):
        for p in (ROOT/directory).rglob('*'):
            if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc' and 'qwen3_8b' not in p.name and 'qwen3-8b' not in p.name:
                protected[str(p.relative_to(ROOT))]=sha(p)
    for n,x in [('runtime-config.json',config),('inputs.json',inputs),('runtime-sources.json',sources),('protected.json',protected)]:write(n,x)
    write('cpu-checks.json',{'status':'PASS','cases':len(cases),'conditions':len(inputs),
        'splits':dict(Counter(c['split'] for c in cases)),'max_input_tokens':max(r['input_tokens'] for r in inputs),
        'unchanged_messages':144,'unchanged_references':72,'closed_native_thinking_prefix':True,
        'template_sha256':digest(tok.chat_template),'gate_per_arm':20,'protected_files':len(protected)})
    paths=[p for p in HERE.iterdir() if p.is_file()]+[p for p in MODEL.iterdir() if p.is_file()]+[p for p in (MODEL/'tokenizer').iterdir() if p.is_file()]
    paths += [ROOT/n for n in ('experiments/context_policy/reader_qwen3_8b.py','modal-runners/modal-reader-qwen3-8b.py','modal-runners/modal-reader-qwen3-8b-cache.py')]
    write('freeze.json',{'files':{str(p.relative_to(ROOT)):sha(p) for p in paths},'reference_fields_mounted':False,
                        'parent_result_manifest_sha256':sha(PARENT/'result-manifest.json')})
    print((HERE/'cpu-checks.json').read_text())

if __name__=='__main__':main()

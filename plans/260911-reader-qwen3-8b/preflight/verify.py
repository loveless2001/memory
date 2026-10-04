"""Replay the frozen larger-model comparison without inference or mutation."""
import json,sys
from collections import Counter
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from prepare import ROOT,PARENT,MODEL,read,sha
from transformers import AutoTokenizer
from experiments.context_policy.reader_qwen3_8b import answer_prefix_ids,SYSTEMS

def main():
    freeze=read(HERE/'freeze.json')
    for n,h in freeze['files'].items():assert sha(ROOT/n)==h,n
    protected=read(HERE/'protected.json')
    for n,h in protected.items():assert sha(ROOT/n)==h,n
    assert freeze['parent_result_manifest_sha256']==sha(PARENT/'result-manifest.json')
    for n in ('cases.json','gate-indices.json'):assert (HERE/n).read_bytes()==(PARENT/'preflight'/n).read_bytes()
    inputs=read(HERE/'inputs.json');old=read(PARENT/'preflight/inputs.json')
    assert len(inputs)==len(old)==144
    tok=AutoTokenizer.from_pretrained(MODEL/'tokenizer',local_files_only=True)
    for r,p in zip(inputs,old):
        assert {k:v for k,v in r.items() if k!='input_tokens'}=={k:v for k,v in p.items() if k!='input_tokens'}
        ids=answer_prefix_ids(tok,r['messages']);assert r['input_tokens']==len(ids) and len(ids)+192<=8192
        assert r['messages'][0]['content']==SYSTEMS[r['arm']]
        assert tok.decode(ids,skip_special_tokens=False).endswith('<think>\n\n</think>\n\nANSWER\n')
    gate=read(HERE/'gate-indices.json');assert len(gate)==len(set(gate))==40
    assert Counter(inputs[i]['arm'] for i in gate)=={'baseline':20,'repair':20}
    config=read(HERE/'runtime-config.json');expected=read(PARENT/'preflight/runtime-config.json')
    expected.update(model_id='Qwen/Qwen3-8B',model_revision=read(MODEL/'hub-info.json')['revision'],enable_thinking=False)
    assert config==expected
    print(json.dumps({'status':'PASS','cases':72,'conditions':144,'unchanged_messages':144,
                      'non_thinking_prefix_verified':True,'protected_files':len(protected)}))

if __name__=='__main__':main()

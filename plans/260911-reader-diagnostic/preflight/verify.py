"""Offline preflight validation; no inference or data mutation."""
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(HERE))
from prepare import render, ARMS
from transformers import AutoTokenizer
from experiments.context_policy.broader_protocol import answer_prefix_ids


def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    for n,h in read(HERE/'freeze.json')['files'].items():assert sha(ROOT/n)==h,n
    protected=read(HERE/'protected.json')
    for n,h in protected.items():assert sha(ROOT/n)==h,n
    inputs=read(HERE/'inputs.json');cases={c['id']:c for c in read(HERE/'cases.json')}
    config=read(HERE/'runtime-config.json');tok=AutoTokenizer.from_pretrained(config['model_id'],revision=config['model_revision'],local_files_only=True)
    assert len(cases)==24 and len(inputs)==96
    assert Counter(r['arm'] for r in inputs)=={a:24 for a in ARMS}
    assert Counter(c['kind'] for c in cases.values())=={k:4 for k in ('baseline','withdrawal','different','same','historical','ownership')}
    seen=set()
    for row in inputs:
        assert set(row)=={'id','arm','messages','input_tokens'}
        assert (row['id'],row['arm']) not in seen;seen.add((row['id'],row['arm']))
        case=cases[row['id']];messages,spans=render(case['history'],case['query'],row['arm'])
        assert row['messages']==messages
        assert row['input_tokens']==len(answer_prefix_ids(tok,messages))
        assert row['input_tokens']+192<=8192
        assert sorted(s['turn'] for s in spans)==list(range(len(case['history'])))
    gate=read(HERE/'gate-indices.json');assert len(gate)==len(set(gate))==40
    assert Counter(inputs[i]['arm'] for i in gate)=={a:10 for a in ARMS}
    print(json.dumps({'status':'PASS','cases':24,'conditions':96,'cache_fixtures':40,'protected_files':len(protected),
                      'reference_fields_in_runtime_inputs':False,'training_labels':0},indent=2))


if __name__=='__main__':main()

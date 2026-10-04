"""Verify all captured inputs/tokens and the frozen diagnostic provenance."""
import hashlib
import json
import sys
from pathlib import Path
from collections import Counter

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
PREP=HERE.parent/'preflight'
sys.path.insert(0,str(ROOT))
from transformers import AutoTokenizer
from experiments.context_policy.broader_protocol import answer_prefix_ids,strict_body_capture
from experiments.context_policy.preflight import digest


def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    launch=read(HERE/'launch.json');manifest=read(HERE/'manifest.json');status=read(HERE/'status.json')
    hashes=read(HERE/'artifact-hashes.json')
    for n,h in hashes.items():
        assert Path(n).name==n
        assert sha(HERE/n)==h,n
    for k in ('source_hashes','input_hashes','runner_sha256','freeze_sha256'):assert launch[k]==manifest[k],k
    assert sha(PREP/'freeze.json')==launch['freeze_sha256']
    for n,h in read(PREP/'freeze.json')['files'].items():assert sha(ROOT/n)==h,n
    protected=read(PREP/'protected.json')
    for n,h in protected.items():assert sha(ROOT/n)==h,n
    for n,h in launch['source_hashes'].items():assert sha(HERE/'source-snapshot'/n)==h,n
    assert sha(HERE/'source-snapshot/modal-runners/modal-reader-diagnostic.py')==launch['runner_sha256']
    for n,h in launch['input_hashes'].items():assert sha(PREP/n)==h,n
    config=read(PREP/'runtime-config.json');inputs=read(PREP/'inputs.json')
    tok=AutoTokenizer.from_pretrained(config['model_id'],revision=config['model_revision'],local_files_only=True)
    runtime=read(HERE/'runtime.json')
    assert runtime['model_revision']==config['model_revision'] and runtime['template_sha256']==digest(tok.chat_template)
    assert runtime['torch'].split('+')[0]=='2.7.1' and runtime['transformers']=='4.55.2'
    assert runtime['dtype']=='float32' and runtime['attention']=='math' and not runtime['tf32'] and runtime['trainable_parameters']==0
    checks=read(HERE/'cache-checks.json');gate=read(HERE/'cache-verdict.json');indices=read(PREP/'gate-indices.json')
    assert [c['input_index'] for c in checks]==indices[:len(checks)]
    for c in checks:
        r=inputs[c['input_index']]
        assert (c['id'],c['arm'])==(r['id'],r['arm'])
        assert c['pass']==(c['initial_argmax_equal'] and c['cached_tokens']==c['fresh_tokens'])
        assert 0<len(c['cached_tokens'])<=16 and 0<len(c['fresh_tokens'])<=16
    assert gate['pass']==(len(checks)==40 and all(c['pass'] for c in checks))
    captures=read(HERE/'captures.json') if (HERE/'captures.json').exists() else []
    assert not captures or gate['pass']
    for i,c in enumerate(captures):
        r=inputs[i];assert c['input_index']==i and (c['id'],c['arm'])==(r['id'],r['arm'])
        assert c['messages']==r['messages'] and c['input_tokens']==r['input_tokens']==len(answer_prefix_ids(tok,c['messages']))
        assert 0<len(c['token_ids'])<=192 and tok.eos_token_id not in c['token_ids'][:-1]
        body=strict_body_capture(tok,c['token_ids'],tok.eos_token_id)
        for k,v in body.items():assert c[k]==v,(i,k)
        assert c['fresh_prefill'] is True and c['actual_forwarded_tokens']==c['input_tokens']+len(c['token_ids'])-int(c['ended_at_eos'])
    complete=status['status']=='collection_complete'
    if complete:assert len(captures)==96
    lookup={(c['id'],c['arm']):c for c in captures};pairs=[]
    for cid in sorted({r['id'] for r in captures}):
        if cid.split('-')[1] not in ('baseline','ownership'):continue
        for wrapper in ('plain','json'):
            keys=[(cid,wrapper+'_'+s) for s in ('chronological','withdrawals_last')]
            if not all(k in lookup for k in keys):continue
            a,b=[lookup[k] for k in keys]
            assert a['messages']==b['messages']
            pairs.append({'id':cid,'wrapper':wrapper,'tokens_equal':a['token_ids']==b['token_ids']})
    assert all(p['tokens_equal'] for p in pairs),'determinism failed on identical inputs'
    result={'status':'PASS','remote_status':status['status'],'complete':complete,'captures':len(captures),
        'cache_checks':len(checks),'cache_pass':gate['pass'],'cache_per_arm':dict(Counter(c['arm'] for c in checks)),
        'body_valid':sum(c['body_structurally_valid'] for c in captures),'within_90_words':sum(c['within_90_words'] for c in captures),
        'max_words':max((c['word_count_whitespace'] for c in captures),default=0),'identical_input_pairs':len(pairs),
        'identical_input_outputs_equal':all(p['tokens_equal'] for p in pairs),'protected_files_unchanged':len(protected),
        'semantic_score':None,'training_labels':0}
    (HERE/'artifact-verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))


if __name__=='__main__':main()

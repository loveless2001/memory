"""Verify both terminal runs and bind their unchanged prefix and suffix."""
import hashlib,json,sys
from collections import Counter
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT))
from transformers import AutoTokenizer
from experiments.context_policy.broader_protocol import answer_prefix_ids,strict_body_capture
from experiments.context_policy.preflight import digest
from experiments.context_policy.reader_repair import SYSTEMS

def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def verify_run(run_name,prep_name,offset,tok,inputs):
    run=HERE/run_name;prep=HERE/prep_name
    launch=read(run/'launch.json');manifest=read(run/'manifest.json');status=read(run/'status.json')
    for n,h in read(run/'artifact-hashes.json').items():assert Path(n).name==n and sha(run/n)==h,n
    for k in ('source_hashes','input_hashes','runner_sha256','freeze_sha256'):assert launch[k]==manifest[k]
    assert manifest['source_hashes']==read(prep/'runtime-sources.json')
    assert manifest['references_mounted'] is False and manifest['retries']==0 and manifest['hard_timeout_seconds']==1200
    assert manifest['planned_captures']==144-offset and sha(prep/'freeze.json')==manifest['freeze_sha256']
    for n,h in read(prep/'freeze.json')['files'].items():assert sha(ROOT/n)==h,n
    for n,h in read(prep/'protected.json').items():assert sha(ROOT/n)==h,n
    for n,h in manifest['source_hashes'].items():assert sha(run/'source-snapshot'/n)==h
    runner='modal-reader-repair.py' if offset==0 else 'modal-reader-repair-continuation.py'
    assert sha(run/'source-snapshot/modal-runners'/runner)==manifest['runner_sha256']
    assert set(manifest['input_hashes'])=={'runtime-config.json','inputs.json','gate-indices.json'}
    for n,h in manifest['input_hashes'].items():assert sha(prep/n)==h
    assert read(prep/'inputs.json')==inputs
    config=read(prep/'runtime-config.json');runtime=read(run/'runtime.json')
    assert runtime['model_revision']==config['model_revision'] and runtime['template_sha256']==digest(tok.chat_template)
    assert runtime['torch'].split('+')[0]=='2.7.1' and runtime['transformers']=='4.55.2'
    assert runtime['dtype']=='float32' and runtime['attention']=='math' and runtime['tf32'] is False and runtime['trainable_parameters']==0
    assert runtime['system_hashes']=={a:digest(s) for a,s in SYSTEMS.items()}
    checks=read(run/'cache-checks.json');gate=read(run/'cache-verdict.json')
    assert [c['input_index'] for c in checks]==read(prep/'gate-indices.json')
    assert len(checks)==40 and gate['pass'] and gate['checked']==40
    assert Counter(c['arm'] for c in checks)=={'baseline':20,'repair':20}
    for c in checks:
        r=inputs[c['input_index']]
        assert (c['id'],c['arm'])==(r['id'],r['arm'])
        assert c['pass'] and c['initial_argmax_equal'] and c['cached_tokens']==c['fresh_tokens']
        assert 0<len(c['cached_tokens'])<=16
    captures=read(run/'captures.json')
    for local,c in enumerate(captures):
        index=offset+local;r=inputs[index]
        assert c['input_index']==index and (c['id'],c['arm'])==(r['id'],r['arm'])
        assert c['messages']==r['messages'] and c['input_tokens']==r['input_tokens']==len(answer_prefix_ids(tok,c['messages']))
        assert c['input_tokens']+192<=8192
        assert 0<len(c['token_ids'])<=192 and tok.eos_token_id not in c['token_ids'][:-1]
        for k,v in strict_body_capture(tok,c['token_ids'],tok.eos_token_id).items():assert c[k]==v,(index,k)
        assert c['fresh_prefill'] and c['actual_forwarded_tokens']==c['input_tokens']+len(c['token_ids'])-int(c['ended_at_eos'])
    if offset==0:assert status['status']=='failed' and 'time ceiling' in status['error'] and 0<len(captures)<144
    else:
        assert status['status']=='collection_complete' and status['captures']==len(captures)==144-offset
        assert config['capture_start_index']==manifest['capture_start_index']==offset
        assert status['gate']==gate and status['training_labels']==0
        assert status['body_valid']==sum(c['body_structurally_valid'] for c in captures)
        assert status['within_90_words']==sum(c['within_90_words'] for c in captures)
    app=read(run/'app-status.json')['app']
    assert app['app_id']==launch['app_id'] and app['state']=='stopped' and int(app['tasks'])==0
    return captures,{'run':run_name,'status':status['status'],'captures':len(captures),'capture_start_index':offset,'captures_sha256':sha(run/'captures.json'),'cache_checks':40}

def main():
    config=read(HERE/'preflight/runtime-config.json');inputs=read(HERE/'preflight/inputs.json')
    tok=AutoTokenizer.from_pretrained(config['model_id'],revision=config['model_revision'],local_files_only=True)
    prefix,first=verify_run('run','preflight',0,tok,inputs)
    suffix,second=verify_run('continuation-run','continuation-preflight',len(prefix),tok,inputs)
    captures=prefix+suffix;assert len(captures)==144 and [c['input_index'] for c in captures]==list(range(144))
    old={c['id']:c for c in read(ROOT/'plans/260911-reader-diagnostic/run/captures.json') if c['arm']=='json_chronological'}
    compared=[c for c in captures if c['arm']=='baseline' and c['id'] in old]
    assert len(compared)==24 and all(c['messages']==old[c['id']]['messages'] for c in compared)
    result={'status':'PASS','complete':True,'captures':144,'runs':[first,second],'cache_checks':80,'cache_pass':True,
        'execution_plan_amended_for_checkpoint_overhead':True,
        'body_valid':sum(c['body_structurally_valid'] for c in captures),'within_90_words':sum(c['within_90_words'] for c in captures),
        'max_words':max(c['word_count_whitespace'] for c in captures),'previous_baseline_input_pairs':24,
        'previous_baseline_matches':sum(c['token_ids']==old[c['id']]['token_ids'] for c in compared),
        'protected_files_unchanged':len(read(HERE/'preflight/protected.json')),
        'continuation_protected_files_unchanged':len(read(HERE/'continuation-preflight/protected.json')),'semantic_score':None,'training_labels':0}
    combined=HERE/'combined';combined.mkdir(exist_ok=True)
    for name,value in [('captures.json',captures),('artifact-verification.json',result)]:
        if (HERE/'result-manifest.json').exists():assert read(combined/name)==value
        else:(combined/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()

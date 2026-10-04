"""Verify immutable inputs, training provenance, checkpoint and paired outputs."""
import hashlib,json,sys,math
from pathlib import Path
from collections import Counter,defaultdict
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];PREP=HERE/'preflight';RUN=HERE/'run'
sys.path.insert(0,str(ROOT))
from experiments.context_policy.preflight import digest
from experiments.context_policy.broader_protocol import answer_prefix_ids,strict_body_capture
from experiments.context_policy.reader_sft_protocol import learning_rate,encode_answer
from transformers import AutoTokenizer

def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def verify():
    launch=read(RUN/'launch.json');manifest=read(RUN/'manifest.json');status=read(RUN/'status.json')
    for n,h in read(RUN/'artifact-hashes.json').items():
        p=Path(n);assert not p.is_absolute() and '..' not in p.parts
        assert sha(RUN/n)==h,n
    for k in ('source_hashes','input_hashes','runner_sha256','freeze_sha256'):assert launch[k]==manifest[k],k
    assert manifest['source_hashes']==read(PREP/'runtime-sources.json')
    assert manifest['training_answers_mounted'] and not manifest['evaluation_references_mounted'] and not manifest['prior_model_outputs_mounted']
    assert manifest['planned_captures']==288 and manifest['planned_training_examples']==384
    assert manifest['hard_timeout_seconds']==2400 and manifest['retries']==0
    assert set(manifest['input_hashes'])=={'runtime-config.json','train-inputs.json','eval-inputs.json','gate-ids.json','training-order.json'}
    assert sha(PREP/'freeze.json')==launch['freeze_sha256']
    for n,h in read(PREP/'freeze.json')['files'].items():assert sha(ROOT/n)==h,n
    protected=read(PREP/'protected.json')
    for n,h in protected.items():assert sha(ROOT/n)==h,n
    for n,h in launch['source_hashes'].items():assert sha(RUN/'source-snapshot'/n)==h,n
    assert sha(RUN/'source-snapshot/modal-runners/modal-reader-sft.py')==launch['runner_sha256']
    for n,h in launch['input_hashes'].items():assert sha(PREP/n)==h,n
    config=read(PREP/'runtime-config.json');tok=AutoTokenizer.from_pretrained(config['model_id'],revision=config['model_revision'],local_files_only=True)
    runtime=read(RUN/'runtime.json')
    assert runtime['model_revision']==config['model_revision'] and runtime['template_sha256']==digest(tok.chat_template)
    assert runtime['torch'].split('+')[0]=='2.7.1' and runtime['transformers']=='4.55.2' and runtime['peft']=='0.17.0'
    assert runtime['inference_dtype']=='float32' and runtime['attention']=='math' and not runtime['tf32'] and runtime['base_trainable_parameters']==0
    train=read(PREP/'train-inputs.json');orders=read(PREP/'training-order.json');inputs=read(PREP/'eval-inputs.json')
    for r in train:
        encoded=encode_answer(tok,r['messages'],r['answer']);assert all(r[k]==v for k,v in encoded.items())
    answers=read(RUN/'captures.json') if (RUN/'captures.json').exists() else []
    expected=[(arm,r) for arm in ('base','adapted') for r in inputs]
    assert len(answers)<=288
    account=defaultdict(Counter);old={c['id']:c for c in read(ROOT/'plans/260911-reader-state/run/captures.json') if c['arm']=='baseline'};reproduced=[]
    for c,(arm,r) in zip(answers,expected):
        assert (c['id'],c['arm'],c['messages'])==(r['id'],arm,r['messages'])
        assert c['input_tokens']==r['input_tokens']==len(answer_prefix_ids(tok,c['messages']))
        assert 0<len(c['token_ids'])<=192 and tok.eos_token_id not in c['token_ids'][:-1]
        for k,v in strict_body_capture(tok,c['token_ids'],tok.eos_token_id).items():assert c[k]==v,(c['id'],arm,k)
        assert c['fresh_prefill'] and c['actual_forwarded_tokens']==c['input_tokens']+len(c['token_ids'])-int(c['ended_at_eos'])
        assert c['input_tokens']+192<=8192
        if arm=='base':assert c['adapter_sha256']=='base-no-adapter'
        else:assert c['adapter_sha256']==sha(RUN/'adapter/adapter_model.safetensors')
        a=account[arm];a['calls']+=1;a['input_tokens']+=c['input_tokens'];a['generated_tokens']+=len(c['token_ids']);a['forwarded_tokens']+=c['actual_forwarded_tokens'];a['generation_seconds']+=c['elapsed_seconds']
        if arm=='base' and c['id'] in old:
            assert c['messages']==old[c['id']]['messages'];reproduced.append({'id':c['id'],'tokens_equal':c['token_ids']==old[c['id']]['token_ids']})
    checks=read(RUN/'cache-checks.json');gate_account=defaultdict(Counter);input_map={r['id']:r for r in inputs};gates=read(PREP/'gate-ids.json');expected_gate=[(a,cid) for a in ('base','adapted') for cid in gates]
    assert [(c['arm'],c['id']) for c in checks]==expected_gate[:len(checks)]
    for c in checks:
        assert c['pass']==(c['initial_argmax_equal'] and c['cached_tokens']==c['fresh_tokens'])
        assert 0<len(c['cached_tokens'])<=16 and 0<len(c['fresh_tokens'])<=16
        n=input_map[c['id']]['input_tokens'];a=gate_account[c['arm']];a['fixtures']+=1
        for path in ('cached','fresh'):
            ts=c[path+'_tokens'];steps=len(ts)-int(ts[-1]==tok.eos_token_id)
            a[path+'_generated_tokens']+=len(ts)
            a[path+'_forwarded_tokens']+=n+steps if path=='cached' else sum(n+i for i in range(steps+1))
    steps=read(RUN/'training-steps.json') if (RUN/'training-steps.json').exists() else []
    seen=[]
    for i,s in enumerate(steps):
        assert s['step']==i+1 and s['epoch']==i//24+1
        assert s['example_ids']==orders[i//24][(i%24)*16:(i%24+1)*16]
        assert s['learning_rate']==learning_rate(i+1,48)
        assert s['all_gradients_finite'] and s['only_adapter_gradients']
        assert all(math.isfinite(s[k]) and s[k]>=0 for k in ('mean_answer_loss','min_answer_loss','max_answer_loss','gradient_norm_before_clip','elapsed_seconds'))
        seen+=s['example_ids']
    trained=None
    if (RUN/'training.json').exists():
        trained=read(RUN/'training.json');assert len(steps)==trained['optimizer_steps']==48 and seen==orders[0]+orders[1]
        assert trained['examples_seen']==768 and trained['unique_examples']==384 and trained['epochs']==2
        assert trained['exposure_order_sha256']==digest(seen)
        assert trained['answer_target_tokens']==2*sum(r['supervised_tokens'] for r in train)
        assert trained['masked_prefix_tokens']==2*sum(r['prefix_tokens'] for r in train)
        assert trained['action_tokens_supervised']==0 and not trained['evaluation_references_mounted']
        assert not trained['base_parameter_training'] and not trained['base_buffer_training']
        assert trained['checkpoint_selection']=='fixed_final_after_two_epochs'
        assert trained['base_tensors_before']==trained['base_tensors_after']==runtime['base_tensors_initial']
        assert trained['trained_adapter_tensors']!=trained['initial_adapter_tensors']
        assert trained['adapter_sha256']==sha(RUN/'adapter/adapter_model.safetensors')
        assert len(trained['trainable_names'])==36*2*2 and all('lora_' in n and ('q_proj' in n or 'v_proj' in n) for n in trained['trainable_names'])
        from safetensors import safe_open
        with safe_open(RUN/'adapter/adapter_model.safetensors',framework='pt',device='cpu') as f:
            assert set(f.keys())=={n.replace('.default.','.') for n in trained['trainable_names']}
            assert sum(f.get_tensor(n).numel() for n in f.keys())==trained['trainable_parameters']
        ac=read(RUN/'adapter/adapter_config.json')
        for k,v in config['lora'].items():assert (set(ac[k])==set(v) if isinstance(v,list) else ac[k]==v),k
    reload=None
    if (RUN/'reload-verification.json').exists():
        reload=read(RUN/'reload-verification.json')
        assert reload['status']=='PASS' and reload['saved_tensor_equality'] and reload['trainable_parameters']==0
        assert reload['base_tensors']==runtime['base_tensors_initial'] and reload['adapter_tensors']==trained['trained_adapter_tensors']
        assert reload['adapter_sha256']==trained['adapter_sha256']
    complete=status['status']=='collection_complete'
    if complete:
        assert len(answers)==288 and len(checks)==40 and all(c['pass'] for c in checks) and trained and reload
        assert status['optimizer_steps']==48 and status['training_exposures']==768 and status['answer_supervision_examples']==384
        assert status['gate']==read(RUN/'cache-verdict.json') and status['gate']['pass']
        assert status['body_valid']==sum(c['body_structurally_valid'] for c in answers) and status['within_90_words']==sum(c['within_90_words'] for c in answers)
        assert len(reproduced)==96 and all(r['tokens_equal'] for r in reproduced)
    return {'status':'PASS','remote_status':status['status'],'complete':complete,'answers':len(answers),
        'cache_checks':len(checks),'passed_cache_checks':sum(c['pass'] for c in checks),'optimizer_steps':len(steps),
        'training_exposures':len(seen),'training_answer_target_tokens':trained['answer_target_tokens'] if trained else None,
        'training_masked_prefix_tokens':trained['masked_prefix_tokens'] if trained else None,
        'saved_adapter_reload_verified':reload is not None,'base_parameters_and_buffers_unchanged':trained is not None,
        'protected_files_unchanged':len(protected),'prior_baseline_reproduction':reproduced,
        'identical_prior_baseline_sequences':sum(r['tokens_equal'] for r in reproduced),'accounting_by_arm':dict(account),'cache_gate_accounting_by_arm':dict(gate_account),
        'body_valid_answers':sum(c['body_structurally_valid'] for c in answers),'answers_within_90_words':sum(c['within_90_words'] for c in answers)}

if __name__=='__main__':
    r=verify()
    if (HERE/'result-manifest.json').exists():assert read(RUN/'artifact-verification.json')==r
    else:(RUN/'artifact-verification.json').write_text(json.dumps(r,indent=2)+'\n')
    print(json.dumps(r,indent=2))

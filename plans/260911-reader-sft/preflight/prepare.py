"""Build reviewed train/test inputs and freeze one supervised reader pilot."""
import argparse,copy,hashlib,json,random,sys
from pathlib import Path
from collections import Counter
from datetime import datetime,timezone

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2];PARENT=ROOT/'plans/260911-reader-state'
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(HERE))
from author_train import make_training_cases,FAMILIES,KINDS
from author_test import make_test_cases
from audit_references import audit
from transformers import AutoTokenizer
from experiments.context_policy.reader_state_protocol import archive_messages
from experiments.context_policy.broader_protocol import answer_prefix_ids
from experiments.context_policy.reader_sft_protocol import encode_answer


def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def digest(x):return hashlib.sha256(json.dumps(x,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
def write(n,x):(HERE/n).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')


def construct(tok):
    assert audit()['status']=='PASS'
    train=make_training_cases();test=make_test_cases();regression=copy.deepcopy(read(PARENT/'preflight/cases.json'))
    for c in regression:c['sft_prior_split']=c['split'];c['split']='regression'
    cases=regression+test
    encoded=[]
    for c in train:
        messages=archive_messages(c['history'],c['query']);target=c['reference']['answer']
        encoded.append({'id':c['id'],'family':c['family'],'messages':messages,'answer':target,
                        **encode_answer(tok,messages,target)})
        if c['reference']['mode']=='unknown':
            assert not any(v in target for v in c['reference']['forbidden_old_values'])
        assert len(target.split())<=90
    old={c['id']:c for c in read(PARENT/'run/captures.json') if c['arm']=='baseline'}
    inputs=[]
    for c in cases:
        messages=archive_messages(c['history'],c['query'])
        if c['split']=='regression':assert messages==old[c['id']]['messages']
        inputs.append({'id':c['id'],'split':c['split'],'messages':messages,'input_tokens':len(answer_prefix_ids(tok,messages))})
    assert len(train)==384 and len(test)==48 and len(regression)==96 and len(inputs)==144
    assert {c['property'] for c in train}.isdisjoint({c['property'] for c in test})
    assert {c['family'] for c in train}.isdisjoint({c['family'] for c in cases})
    for field in ('history','query'):
        assert {digest(c[field]) for c in train}.isdisjoint({digest(c[field]) for c in cases}),field
    gate=[]
    for split in ('regression','test'):
        gate += sorted([c['id'] for c in cases if c['split']==split],key=lambda cid:digest(['gate',cid]))[:10]
    orders=[]
    for epoch in range(2):
        ids=[c['id'] for c in train];random.Random(1701+epoch).shuffle(ids);orders.append(ids)
    return train,cases,encoded,inputs,gate,orders


def main(freeze=False):
    assert not (HERE/'freeze.json').exists(),'Preflight is frozen'
    config={'model_id':'Qwen/Qwen3-4B-Instruct-2507','model_revision':'cdbee75f17c01a7cc42f958dc650907174af0554',
        'active_context_max_tokens':8192,'max_message_output_tokens':192,'seed':0,
        'max_gpu_seconds':2400,'internal_deadline_seconds':2300,'retries':0,
        'planned_captures':288,'planned_training_examples':384,'epochs':2,'optimizer_steps':48,
        'microbatch_size':1,'gradient_accumulation':16,'learning_rate':1e-4,'weight_decay':0.01,
        'warmup_steps':3,'lr_schedule':'linear_warmup_then_linear_decay','gradient_clip_norm':1.0,
        'gradient_checkpointing':True,'use_reentrant':False,'train_precision':'bf16_base_fp32_adapter_fp32_buffers',
        'inference_precision':'fp32_math_tf32_off','checkpoint_selection':'fixed_final_after_two_epochs',
        'lora':{'r':16,'lora_alpha':32,'lora_dropout':0.05,'target_modules':['q_proj','v_proj'],'bias':'none'}}
    tok=AutoTokenizer.from_pretrained(config['model_id'],revision=config['model_revision'],local_files_only=True)
    train,cases,encoded,inputs,gates,orders=construct(tok)
    sources=read(PARENT/'preflight/runtime-sources.json')
    sources.pop('experiments/context_policy/reader_state.py')
    for n in ('experiments/context_policy/reader_sft.py','experiments/context_policy/reader_sft_protocol.py'):sources[n]=sha(ROOT/n)
    for n,h in sources.items():assert sha(ROOT/n)==h,n
    excluded={'reader_sft.py','reader_sft_protocol.py','modal-reader-sft.py','test_context_policy_reader_sft.py'}
    protected={}
    for directory in ('plans/260910-context-policy','plans/260911-reader-diagnostic','plans/260911-reader-repair',
                      'plans/260911-reader-qwen3-8b','plans/260911-reader-state','experiments/context_policy','modal-runners','tests'):
        for p in (ROOT/directory).rglob('*'):
            if p.is_file() and not {'__pycache__','.cache'}.intersection(p.parts) and p.suffix!='.pyc' and p.name not in excluded:
                protected[str(p.relative_to(ROOT))]=sha(p)
    for n,x in [('train-cases.json',train),('eval-cases.json',cases),('train-inputs.json',encoded),('eval-inputs.json',inputs),
                ('gate-ids.json',gates),('training-order.json',orders),('runtime-config.json',config),
                ('runtime-sources.json',sources),('protected.json',protected)]:write(n,x)
    checks={'status':'PASS','training_examples':384,'training_families':16,'training_histories':len({digest(c['history']) for c in train}),
        'heldout_questions':48,'heldout_families':24,'regression_questions':96,'planned_answers':288,
        'epochs':2,'optimizer_steps':48,'training_exposures':768,
        'max_training_tokens':max(len(x['input_ids']) for x in encoded),'max_eval_input_tokens':max(x['input_tokens'] for x in inputs),
        'target_tokens_per_epoch':sum(x['supervised_tokens'] for x in encoded),
        'source_prefix_tokens_per_epoch':sum(x['prefix_tokens'] for x in encoded),
        'action_tokens_supervised':0,'unchanged_prior_regression_messages':96,
        'exact_train_eval_history_overlap':0,'exact_train_eval_query_overlap':0,'train_test_property_overlap':0,
        'protected_files':len(protected),'template_sha256':hashlib.sha256(tok.chat_template.encode()).hexdigest()}
    write('cpu-checks.json',checks)
    if freeze:
        assert (HERE/'REFERENCE-REVIEW.md').exists() and read(HERE/'test-results.json')['passed']
        paths=[p for p in HERE.iterdir() if p.is_file()]
        paths += [ROOT/n for n in (*sources,'modal-runners/modal-reader-sft.py','tests/test_context_policy_reader_sft.py')]
        paths += [HERE.parent/'authorization.json']
        write('freeze.json',{'frozen_at':datetime.now(timezone.utc).isoformat(),
            'files':{str(p.relative_to(ROOT)):sha(p) for p in paths},'training_answers_mounted':True,
            'eval_references_mounted':False,'prior_model_outputs_mounted':False,
            'parent_result_manifest_sha256':sha(PARENT/'result-manifest.json')})
    print(json.dumps(checks,indent=2))


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--freeze',action='store_true');args=ap.parse_args();main(args.freeze)

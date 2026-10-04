"""Freeze revised supervision and genuinely new test before one GPU run."""
import argparse,copy,hashlib,json,random,sys
from pathlib import Path
from datetime import datetime,timezone
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2];PARENT=ROOT/'plans/260911-reader-sft'
sys.path.insert(0,str(ROOT))
from author_extra import make_extra
from author_test import make_test_cases
from transformers import AutoTokenizer
from experiments.context_policy.reader_state_protocol import archive_messages
from experiments.context_policy.broader_protocol import answer_prefix_ids
from experiments.context_policy.reader_sft_protocol import encode_answer

def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def digest(x):return hashlib.sha256(json.dumps(x,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
def write(n,x):(HERE/n).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')

def audit(rows):
    assert len({c['id'] for c in rows})==len(rows)
    for c in rows:
        r=c['reference'];a=r['answer']
        assert a.strip() and len(a.split())<=90
        assert all(type(i)==int and 0<=i<len(c['history']) and c['history'][i]['role']=='user' for i in r['evidence_turns'])
        if r['binary_truth'] is not None:assert a.startswith('Yes.' if r['binary_truth'] else 'No.'),c['id']
        if r['mode']=='unknown':
            assert r['current_value'] is None and r['polarity'] is None and r['binary_truth'] is None
            assert 'unknown' in a.lower() and all(v.lower() not in a.lower() for v in r['forbidden_old_values'])
        elif r['mode']=='historical':assert c['scope']=='historical' and 'first message' in a
        else:
            assert r['mode']=='known'
            if r['polarity']=='none':assert r['current_value'] is None and 'no preferred' in a
            elif r['polarity']=='negative':assert 'not prefer' in a
            else:assert r['current_value'] in a

def construct(tok):
    extra=make_extra();test=make_test_cases();audit(extra);audit(test)
    train=copy.deepcopy(read(PARENT/'preflight/train-cases.json'))+extra
    regression=copy.deepcopy(read(PARENT/'preflight/eval-cases.json'))
    for c in regression:c['v1_split']=c['split'];c['split']='regression'
    cases=regression+test
    assert len(train)==512 and len(regression)==144 and len(test)==64
    assert {c['id'] for c in train}.isdisjoint({c['id'] for c in cases})
    assert {c['family'] for c in train}.isdisjoint({c['family'] for c in cases})
    for field in ('history','query'):
        assert {digest(c[field]) for c in train}.isdisjoint({digest(c[field]) for c in cases})
    assert {c['property'] for c in test}.isdisjoint({c['property'] for c in train})
    assert {c['property'] for c in test}.isdisjoint({c['property'] for c in regression})
    encoded=[]
    for c in train:
        m=archive_messages(c['history'],c['query']);a=c['reference']['answer']
        encoded.append({'id':c['id'],'family':c['family'],'messages':m,'answer':a,**encode_answer(tok,m,a)})
    old={c['id']:c for c in read(PARENT/'run/captures.json') if c['arm']=='adapted'}
    inputs=[]
    for c in cases:
        m=archive_messages(c['history'],c['query'])
        if c['split']=='regression':assert m==old[c['id']]['messages']
        inputs.append({'id':c['id'],'split':c['split'],'messages':m,'input_tokens':len(answer_prefix_ids(tok,m))})
    gates=[]
    for split in ('regression','test'):
        gates+=sorted([c['id'] for c in cases if c['split']==split],key=lambda cid:digest(['v2-gate',cid]))[:10]
    orders=[]
    for epoch in range(2):
        ids=[c['id'] for c in train];random.Random(1701+epoch).shuffle(ids);orders.append(ids)
    return train,cases,encoded,inputs,gates,orders

def main(freeze=False):
    assert not (HERE/'freeze.json').exists()
    config=read(PARENT/'preflight/runtime-config.json')
    config.update(planned_captures=416,planned_training_examples=512,optimizer_steps=64,
        initialization='fresh base; not continuation of v1 adapter',
        prior_adapter_files={n:sha(PARENT/'run/adapter'/n) for n in ('adapter_model.safetensors','adapter_config.json')},
        prior_base_tensors=read(PARENT/'run/training.json')['base_tensors_before'],
        prior_adapter_tensors=read(PARENT/'run/training.json')['trained_adapter_tensors'])
    tok=AutoTokenizer.from_pretrained(config['model_id'],revision=config['model_revision'],local_files_only=True)
    values=construct(tok);train,cases,encoded,inputs,gates,orders=values
    sources=read(PARENT/'preflight/runtime-sources.json');sources.pop('experiments/context_policy/reader_sft.py')
    sources['experiments/context_policy/reader_sft_v2.py']=sha(ROOT/'experiments/context_policy/reader_sft_v2.py')
    for n,h in sources.items():assert sha(ROOT/n)==h
    protected=read(PARENT/'preflight/protected.json')
    protected.update(read(PARENT/'result-manifest.json')['files'])
    protected['plans/260911-reader-sft/result-manifest.json']=sha(PARENT/'result-manifest.json')
    for n in ('experiments/context_policy/reader_sft.py','experiments/context_policy/reader_sft_protocol.py','modal-runners/modal-reader-sft.py','tests/test_context_policy_reader_sft.py'):protected[n]=sha(ROOT/n)
    for n,h in protected.items():assert sha(ROOT/n)==h,n
    names=('train-cases.json','eval-cases.json','train-inputs.json','eval-inputs.json','gate-ids.json','training-order.json')
    for n,x in zip(names,values):write(n,x)
    for n,x in [('runtime-config.json',config),('runtime-sources.json',sources),('protected.json',protected)]:write(n,x)
    stats={'status':'PASS','training_examples':512,'reused_training_examples':384,'new_training_examples':128,
        'training_families':len({c['family'] for c in train}),'training_histories':len({digest(c['history']) for c in train}),
        'regression_questions':144,'heldout_questions':64,'heldout_families':16,'planned_answers':416,
        'optimizer_steps':64,'training_exposures':1024,'target_tokens_per_epoch':sum(r['supervised_tokens'] for r in encoded),
        'prefix_tokens_per_epoch':sum(r['prefix_tokens'] for r in encoded),'max_training_tokens':max(len(r['input_ids']) for r in encoded),
        'max_eval_input_tokens':max(r['input_tokens'] for r in inputs),'train_eval_history_overlap':0,'train_eval_query_overlap':0,
        'new_test_property_overlap':0,'unchanged_regression_prompts':144,'protected_files':len(protected)}
    write('cpu-checks.json',stats)
    if freeze:
        assert read(HERE/'test-results.json')['passed'] and (HERE/'REFERENCE-REVIEW.md').exists()
        paths=[p for p in HERE.iterdir() if p.is_file()]+[ROOT/n for n in (*sources,'modal-runners/modal-reader-sft-v2.py')]+[HERE.parent/'authorization.json']
        write('freeze.json',{'frozen_at':datetime.now(timezone.utc).isoformat(),'files':{str(p.relative_to(ROOT)):sha(p) for p in paths},
            'parent_result_manifest_sha256':sha(PARENT/'result-manifest.json'),'training_answers_mounted':True,'eval_references_mounted':False,'prior_model_outputs_mounted':False})
    print(json.dumps(stats,indent=2))
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--freeze',action='store_true');main(ap.parse_args().freeze)

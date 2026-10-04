"""Read-only frozen preflight reconstruction; no generation or reference scoring."""
import json
from prepare import HERE,ROOT,PARENT,read,sha,construct
from transformers import AutoTokenizer


def main():
    frozen=read(HERE/'freeze.json')
    for n,h in frozen['files'].items(): assert sha(ROOT/n)==h,n
    protected=read(HERE/'protected.json')
    for n,h in protected.items(): assert sha(ROOT/n)==h,n
    assert frozen['parent_result_manifest_sha256']==sha(PARENT/'result-manifest.json')
    config=read(HERE/'runtime-config.json')
    tok=AutoTokenizer.from_pretrained(config['model_id'],revision=config['model_revision'],local_files_only=True)
    reconstructed=construct(tok)
    names=('cases.json','streams.json','questions.json','static-inputs.json','gold-events.json','gate-requests.json')
    for name,x in zip(names,reconstructed): assert read(HERE/name)==x,name
    old=read(PARENT/'preflight/cases.json');new=read(HERE/'cases.json')
    for a,b in zip(old,new):
        for k in ('id','family','kind','question_form','topic_group','history','query','reference'):assert a[k]==b[k],(a['id'],k)
    assert config['model_id']=='Qwen/Qwen3-4B-Instruct-2507' and config['max_gpu_seconds']==1800 and config['retries']==0
    assert frozen['oracle_state_in_oracle_messages'] and not frozen['raw_gold_events_mounted'] and not frozen['final_answer_references_mounted']
    print(json.dumps({'status':'PASS','questions':96,'answers':288,'extractions':52,'protected_files':len(protected)}))


if __name__=='__main__':main()

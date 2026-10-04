"""Reconstruct the frozen training/evaluation split without model inference."""
import json
from prepare import HERE,ROOT,PARENT,read,sha,construct
from transformers import AutoTokenizer


def main():
    frozen=read(HERE/'freeze.json')
    for n,h in frozen['files'].items():assert sha(ROOT/n)==h,n
    protected=read(HERE/'protected.json')
    for n,h in protected.items():assert sha(ROOT/n)==h,n
    assert frozen['parent_result_manifest_sha256']==sha(PARENT/'result-manifest.json')
    config=read(HERE/'runtime-config.json')
    tok=AutoTokenizer.from_pretrained(config['model_id'],revision=config['model_revision'],local_files_only=True)
    reconstructed=construct(tok)
    for n,x in zip(('train-cases.json','eval-cases.json','train-inputs.json','eval-inputs.json','gate-ids.json','training-order.json'),reconstructed):
        assert read(HERE/n)==x,n
    old=read(PARENT/'preflight/cases.json');new=read(HERE/'eval-cases.json')
    for a,b in zip(old,new):
        for k in ('id','history','query','reference'):assert a[k]==b[k],(a['id'],k)
    assert config['epochs']==2 and config['optimizer_steps']==48 and config['planned_captures']==288
    assert config['max_gpu_seconds']==2400 and config['retries']==0
    assert frozen['training_answers_mounted'] and not frozen['eval_references_mounted'] and not frozen['prior_model_outputs_mounted']
    print(json.dumps({'status':'PASS','train_examples':384,'heldout_questions':48,'regression_questions':96,'protected_files':len(protected)}))


if __name__=='__main__':main()

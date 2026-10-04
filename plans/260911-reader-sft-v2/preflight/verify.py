from prepare import HERE,ROOT,PARENT,read,sha,construct
from transformers import AutoTokenizer

def main():
    f=read(HERE/'freeze.json')
    for n,h in f['files'].items():assert sha(ROOT/n)==h,n
    protected=read(HERE/'protected.json')
    for n,h in protected.items():assert sha(ROOT/n)==h,n
    assert f['parent_result_manifest_sha256']==sha(PARENT/'result-manifest.json')
    c=read(HERE/'runtime-config.json');tok=AutoTokenizer.from_pretrained(c['model_id'],revision=c['model_revision'],local_files_only=True)
    for n,x in zip(('train-cases.json','eval-cases.json','train-inputs.json','eval-inputs.json','gate-ids.json','training-order.json'),construct(tok)):assert read(HERE/n)==x,n
    old=read(PARENT/'preflight/eval-cases.json');new=read(HERE/'eval-cases.json')
    for a,b in zip(old,new):
        for k in ('id','history','query','reference'):assert a[k]==b[k]
    assert read(HERE/'train-cases.json')[:384]==read(PARENT/'preflight/train-cases.json')
    assert c['optimizer_steps']==64 and c['epochs']==2 and c['retries']==0 and c['max_gpu_seconds']==2400
    print({'status':'PASS','train':512,'test':64,'regression':144,'protected':len(protected)})
if __name__=='__main__':main()

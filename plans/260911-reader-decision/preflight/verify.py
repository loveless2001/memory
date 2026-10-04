from prepare import HERE,ROOT,PARENT,read,sha,construct
from transformers import AutoTokenizer

def main():
 f=read(HERE/'freeze.json')
 for n,h in f['files'].items():assert sha(ROOT/n)==h,n
 p=read(HERE/'protected.json')
 for n,h in p.items():assert sha(ROOT/n)==h,n
 assert f['parent_manifest_sha256']==sha(PARENT/'result-manifest.json')
 c=read(HERE/'runtime-config.json');t=AutoTokenizer.from_pretrained(c['model_id'],revision=c['model_revision'],local_files_only=True)
 for n,x in zip(('train-cases.json','eval-cases.json','train-inputs.json','eval-inputs.json','gate-ids.json','training-order.json','prior-passes.json'),construct(t)):assert read(HERE/n)==x,n
 assert c['max_gpu_seconds']==3600 and c['planned_captures']==1680 and c['training_runs']==2 and c['retries']==0
 assert c['success_rule']['new_strict_minimum']==152
 print({'status':'PASS','training_examples_per_adapter':512,'new_questions':160,'regression_questions':260,'protected_files':len(p)})
if __name__=='__main__':main()

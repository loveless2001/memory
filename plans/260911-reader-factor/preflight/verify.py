from prepare import HERE,ROOT,PARENT,read,sha,construct
from transformers import AutoTokenizer

def main():
 f=read(HERE/'freeze.json')
 for n,h in f['files'].items():assert sha(ROOT/n)==h,n
 p=read(HERE/'protected.json')
 for n,h in p.items():assert sha(ROOT/n)==h,n
 assert f['parent_manifest_sha256']==sha(PARENT/'result-manifest.json')
 c=read(HERE/'runtime-config.json');t=AutoTokenizer.from_pretrained(c['model_id'],revision=c['model_revision'],local_files_only=True)
 for n,x in zip(('streams-gold.json','cases.json','static-inputs.json','extraction-inputs.json','questions.json','gate-ids.json','reused-ids.json'),construct(t)):assert read(HERE/n)==x,n
 assert c['max_gpu_seconds']==1200 and c['planned_answers']==256 and c['planned_extractions']==16 and c['retries']==0
 print({'status':'PASS','questions':64,'histories':16,'protected':len(p)})
if __name__=='__main__':main()

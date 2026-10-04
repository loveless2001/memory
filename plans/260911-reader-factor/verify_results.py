"""Read-only reproduction of the frozen diagnostic review, report and provenance."""
import hashlib,json,runpy
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
read=lambda p:json.loads(p.read_text())
def check(files):
 for n,h in files.items():assert hashlib.sha256((ROOT/n).read_bytes()).hexdigest()==h,n
def main():
 m=read(HERE/'result-manifest.json');check(m['files']);check(read(HERE/'preflight/freeze.json')['files']);check(read(HERE/'preflight/protected.json'))
 actual={str(p.relative_to(ROOT)) for p in HERE.rglob('*') if p.is_file() and '__pycache__' not in p.parts and '.cache' not in p.parts and p.name!='result-manifest.json' and p.suffix!='.pyc'}
 assert actual==set(m['files'])
 s=runpy.run_path(str(HERE/'summarize.py'))['summarize']();assert s==read(HERE/'summary.json')
 assert s['verification']==read(HERE/'run/artifact-verification.json')
 for name,text in runpy.run_path(str(HERE/'render_report.py'))['render']().items():assert (HERE/name).read_text()==text,name
 app=read(HERE/'app-status.json')['apps'];billing=read(HERE/'billing.json');launch=read(HERE/'run/launch.json')
 assert len(app)==1 and app[0]['app_id']==launch['app_id'] and app[0]['state']=='stopped' and int(app[0]['tasks'])==0
 assert billing['requested_app_ids']==[launch['app_id']]
 print(json.dumps({'status':'PASS','result_files':len(m['files']),'protected_files':s['verification']['protected_files'],'answers_reviewed':256,'extractions_reviewed':16,'strict_scores':{a:z['strict_correct'] for a,z in s['scores']['all'].items()},'descriptive_only':True}))
if __name__=='__main__':main()

"""Read-only verification of final frozen review, scores, report and terminal app."""
import hashlib,json,runpy
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
read=lambda p:json.loads(p.read_text())
def check(files):
 for n,h in files.items():assert hashlib.sha256((ROOT/n).read_bytes()).hexdigest()==h,n
def main():
 m=read(HERE/'result-manifest.json');check(m['files']);check(read(HERE/'preflight/freeze.json')['files']);check(read(HERE/'preflight/protected.json'))
 actual={str(p.relative_to(ROOT)) for p in HERE.rglob('*') if p.is_file() and not {'__pycache__','.cache'}.intersection(p.parts) and p.suffix!='.pyc' and p.name!='result-manifest.json'}
 assert set(m['files'])==actual
 s=runpy.run_path(str(HERE/'summarize.py'))['summarize']();assert s==read(HERE/'summary.json') and s['verification']==read(HERE/'run/artifact-verification.json')
 for name,text in runpy.run_path(str(HERE/'render_report.py'))['render']().items():assert (HERE/name).read_text()==text,name
 apps=read(HERE/'app-status.json')['apps'];billing=read(HERE/'billing.json');launch=read(HERE/'run/launch.json')
 assert len(apps)==1 and apps[0]['app_id']==launch['app_id'] and apps[0]['state']=='stopped' and int(apps[0]['tasks'])==0
 assert billing['requested_app_ids']==[launch['app_id']]
 print(json.dumps({'status':'PASS','result_files':len(m['files']),'protected_files':s['verification']['protected_files'],'reviewed_captures':1680,
  'verdict':s['verdict'],'gates':s['predeclared_gates'],'new_strict_scores':{a:z['strict_correct'] for a,z in s['scores']['test'].items()},'protected_losses':s['protected_regression_loss_ids']}))
if __name__=='__main__':main()

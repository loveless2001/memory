"""Read-only verification of the completed model comparison and prior artifacts."""
import hashlib,json,runpy
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]

def read(p):return json.loads(p.read_text())
def check(files):
    for n,h in files.items():assert hashlib.sha256((ROOT/n).read_bytes()).hexdigest()==h,n

def main():
    manifest=read(HERE/'result-manifest.json');check(manifest['files'])
    check(read(HERE/'preflight/freeze.json')['files'])
    protected=read(HERE/'preflight/protected.json');check(protected)
    summary=runpy.run_path(str(HERE/'summarize.py'))['summarize']()
    assert summary==read(HERE/'summary.json') and summary['captures']==144 and not summary['training_admission']
    apps=read(HERE/'app-status.json')['apps'];billing=read(HERE/'billing.json')
    assert {a['app_id'] for a in apps}==set(billing['requested_app_ids'])
    assert all(a['state']=='stopped' and int(a['tasks'])==0 for a in apps)
    print(json.dumps({'status':'PASS','result_files':len(manifest['files']),'protected_files':len(protected),
        'reviewed_captures':144,'gates':summary['gates'],'primary_gate':summary['primary_original_prompt_gate'],'training_labels':0}))

if __name__=='__main__':main()

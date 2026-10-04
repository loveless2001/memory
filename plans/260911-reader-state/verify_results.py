"""Read-only final-file and evidence-summary verification."""
import hashlib,json,runpy
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]


def read(p):return json.loads(p.read_text())
def check(files):
    for n,h in files.items():assert hashlib.sha256((ROOT/n).read_bytes()).hexdigest()==h,n


def main():
    manifest=read(HERE/'result-manifest.json');check(manifest['files'])
    check(read(HERE/'preflight/freeze.json')['files'])
    protected=read(HERE/'preflight/protected.json');check(protected)
    summary=runpy.run_path(str(HERE/'summarize.py'))['summarize']()
    assert summary==read(HERE/'summary.json') and summary['answer_captures']==288 and summary['extraction_streams']==52
    assert not summary['training_admission'] and summary['training_labels']==0
    app=read(HERE/'app-status.json')['apps'];billing=read(HERE/'billing.json')
    assert len(app)==1 and {a['app_id'] for a in app}==set(billing['requested_app_ids'])
    assert all(a['state']=='stopped' and int(a['tasks'])==0 for a in app)
    assert app[0]['app_id']==read(HERE/'run/launch.json')['app_id']
    print(json.dumps({'status':'PASS','result_files':len(manifest['files']),'protected_files':len(protected),
        'reviewed_answers':288,'reviewed_extractions':52,'gates':summary['gates'],'training_labels':0}))


if __name__=='__main__':main()

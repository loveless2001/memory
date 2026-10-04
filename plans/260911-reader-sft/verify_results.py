"""Read-only verification of the frozen result and stopped single app."""
import hashlib,json,runpy
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
def read(p):return json.loads(p.read_text())
def check(files):
    for n,h in files.items():assert hashlib.sha256((ROOT/n).read_bytes()).hexdigest()==h,n

def main():
    manifest=read(HERE/'result-manifest.json');check(manifest['files']);check(read(HERE/'preflight/freeze.json')['files'])
    protected=read(HERE/'preflight/protected.json');check(protected)
    summary=runpy.run_path(str(HERE/'summarize.py'))['summarize']()
    assert summary==read(HERE/'summary.json') and summary['answer_captures']==288
    review=read(HERE/'review.json')
    assert review['decisions_sha256']==hashlib.sha256((HERE/'review-decisions.json').read_bytes()).hexdigest()
    assert review['prior_review_sha256']==hashlib.sha256((HERE.parent/'260911-reader-state/review.json').read_bytes()).hexdigest()
    for name,text in runpy.run_path(str(HERE/'render_report.py'))['render']().items():
        assert (HERE/name).read_text()==text,name
    app=read(HERE/'app-status.json')['apps'];billing=read(HERE/'billing.json')
    assert len(app)==1 and {a['app_id'] for a in app}==set(billing['requested_app_ids'])
    assert all(a['state']=='stopped' and int(a['tasks'])==0 for a in app)
    assert app[0]['app_id']==read(HERE/'run/launch.json')['app_id']
    print(json.dumps({'status':'PASS','result_files':len(manifest['files']),'protected_files':len(protected),
        'reviewed_answers':288,'trainability_rule':summary['predeclared_trainability_rule'],'clean_suite_gates':summary['clean_suite_gates']}))
if __name__=='__main__':main()

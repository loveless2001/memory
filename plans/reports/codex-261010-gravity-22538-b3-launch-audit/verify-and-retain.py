import datetime
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path('/home/lenovo/projects/memory-occupied-fill-v1-worktree')
DEST = Path(__file__).parent
PLAN = Path('plans/261010-0256-m4-sgm-p2p5-b3-feature-shift2-fill-long-run')
COMMIT = '2efd2b09d9371cd1861128eb7781b4ff9a433577'
checks = {}
def check(name, condition):
    checks[name] = bool(condition)
    assert condition, name

check('HEAD matches cleared package', subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip() == COMMIT)
tracked = [
    Path('modal-runners/modal-m4-sgm-p2p5-b3-shift2-fill-long-run-runner.py'),
    Path('scripts/sgm-p2p5-b3-shift2-fill-long-run-train.py'),
    Path('scripts/sgm-p2p5-taskhead-read-escape-stage-a-train.py'),
    Path('tests/test_sgm_p2p5_b3_shift2_fill_long_run.py'),
    Path('plans/261009-0030-m4-sgm-p2p5-taskhead-read-escape-blocker-screen/inputs/probe-taskhead-learned-n32-s0-run_manifest.json'),
    *[PLAN / 'implementation' / f'b3-package-handoff{suffix}.md' for suffix in ('','-v2','-v3')],
    *sorted(Path(p) for p in subprocess.check_output(['git','ls-files','memsub'],cwd=ROOT,text=True).splitlines()),
]
manifest = []
for rel in tracked:
    data = (ROOT / rel).read_bytes()
    check(f'commit bytes: {rel}', data == subprocess.check_output(['git','show',f'{COMMIT}:{rel}'],cwd=ROOT))
    dest = DEST / 'inputs' / rel
    dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_bytes(data)
    manifest.append({'path':str(rel),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()})
for rel in sorted((ROOT/PLAN/'b3-launch-logs').iterdir()):
    if rel.is_file():
        dest = DEST/'launch-logs'/rel.name
        dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(rel,dest)
for name in ('run.json','watch.log'):
    shutil.copy2(ROOT/PLAN/'b3-run-v1'/name,DEST/name)
meta = json.loads((DEST/'run.json').read_text())
snap = json.loads((DEST/'live-snapshot.json').read_text())
vol = DEST/'live-snapshot'/'b3-run-v1'
campaign = json.loads((vol/'campaign.json').read_text())
identity = json.loads((vol/'B3'/'identity.json').read_text())
starts = [json.loads(x) for x in (vol/'B3.starts.jsonl').read_text().splitlines()]
tele = [json.loads(x) for x in (vol/'B3'/'routing_telemetry.jsonl').read_text().splitlines()]
check('read-only snapshot succeeded', not snap['errors'])
check('call running', snap['call']['state']=='running')
check('one admitted start only', set(snap['dict']) == {'start-1','campaign-deadline'})
check('start-1 task matches live container', snap['dict']['start-1']['task']=='ta-01M4HWABYE68TY018WJCDFM5GR')
check('immutable deadline consistent', meta['deadline']==snap['dict']['campaign-deadline']==campaign['deadline'])
check('campaign bindings consistent', campaign=={'app':'memsub-m4-sgm-p2p5-b3-shift2-fill-long','start_dict':'m4-sgm-p2p5-b3-shift2-fill-long-starts-v1','volume':'memsub-m4-sgm-p2p5-b3-shift2-fill-long-v1','deadline':meta['deadline']})
check('fresh trainer start, no restore', len(starts)==1 and starts[0]['start']==1 and starts[0]['resume_step'] is None)
mh=hashlib.sha256()
for f in sorted((ROOT/'memsub').rglob('*.py')):
    if 'pycache' not in f.parent.name:
        mh.update(str(f.relative_to(ROOT)).encode()+b'\0')
        mh.update(f.read_bytes()+b'\0')
check('remote memsub matches cleared tree', mh.hexdigest()==identity['memsub_source_sha256']=='d86639b9223d4595a53cd07f3fee4da58c413414c49ed220d7135742f444a532')
check('remote trainer source matches', identity['script_sha256']==hashlib.sha256((ROOT/tracked[1]).read_bytes()).hexdigest())
check('remote probe manifest matches', identity['probe_manifest_sha256']==hashlib.sha256((ROOT/tracked[4]).read_bytes()).hexdigest())
pcfg = identity['pilot_config']
check('registered execution config', pcfg['steps']==1500 and pcfg['seed']==0 and pcfg['device']=='cuda' and pcfg['sgm']['feature_shift']==2 and pcfg['filler_len_schedule']==[[0,0],[1000,40]])
check('initial eval 5 of 256', len(tele)==2 and tele[0]['step']==0 and tele[0]['eval']['correct']==5 and tele[0]['eval']['total']==256)
check('first update telemetry finite and changed', tele[1]['step']==0 and 0<tele[1]['loss']<100 and all(tele[1]['update_norm'][key]>0 for key in ('L6/q_proj','L13/q_proj','L20/q_proj','L27/q_proj')))
check('no final result or checkpoint in snapshot', not any(x['path'].endswith(('b3_result.json','resume.pt')) for x in snap['files']))
led = meta['ledger']
check('approved conditional ledger preserved', led['cap_usd']==17 and led['window_s']==23880 and abs(led['reservation_usd']-16.3035352)<1e-10)
proc = subprocess.check_output(['ps','-p','254336','-o','pid,ppid,sid,stat,lstart,args'],text=True)
(DEST/'watcher-process.txt').write_text(proc)
check('original detached watcher alive', 'watch ' in proc and '254336' in proc)
(DEST/'git-status.txt').write_text(subprocess.check_output(['git','status','--short'],cwd=ROOT,text=True))
(DEST/'input-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
result = {'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'commit':COMMIT,'checks':checks,'retained_source_files':len(manifest),'deadline_utc':datetime.datetime.fromtimestamp(meta['deadline'],datetime.timezone.utc).isoformat(),'conditional_cleanup_window_end_utc':datetime.datetime.fromtimestamp(meta['deadline']+480,datetime.timezone.utc).isoformat(),'initial_dev_correct':5,'initial_dev_total':256,'first_recorded_update':0,'final_readout':False}
(DEST/'checks.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k!='checks'},indent=2))

"""Read existing B3 objects and receipts; no deploy, dispatch, stop or evaluation."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
import modal

REPORT = Path(__file__).parent
ROOT = Path('/home/lenovo/projects/memory-occupied-fill-v1-worktree')
OUT = ROOT / 'plans/261010-0256-m4-sgm-p2p5-b3-feature-shift2-fill-long-run/b3-run-v1'
APP_ID = 'ap-uV0nVE4wGpjtep7vRs8tot'
snap = {'capture_started':datetime.now(timezone.utc).isoformat(), 'errors':{}, 'app_id':APP_ID}
def cli(name, args):
    started = datetime.now(timezone.utc).isoformat()
    proc = subprocess.run([sys.executable,'-m','modal',*args],cwd=ROOT,text=True,capture_output=True,timeout=60)
    (REPORT/f'{name}.json').write_text(proc.stdout)
    (REPORT/f'{name}.stderr.txt').write_text(proc.stderr)
    (REPORT/f'{name}.receipt.json').write_text(json.dumps({'args':args,'returncode':proc.returncode,'started':started,'finished':datetime.now(timezone.utc).isoformat()},indent=2)+'\n')
    proc.check_returncode()
    return json.loads(proc.stdout)

for name,args in [('app-list',['app','list','--json']),('container-list',['container','list','--json'])]:
    try:
        cli(name,args)
    except Exception as e:
        snap['errors'][name]=f'{type(e).__name__}: {e}'
meta = json.loads((OUT/'run.json').read_text())
snap['launch'] = meta
try:
    snap['call_result'] = modal.FunctionCall.from_id(meta['call_id']).get(timeout=0)
except Exception as e:
    snap['errors']['call'] = f'{type(e).__name__}: {e}'
try:
    starts = modal.Dict.from_name('m4-sgm-p2p5-b3-shift2-fill-long-starts-v1',create_if_missing=False)
    snap['dict'] = dict(starts.items())
except Exception as e:
    snap['errors']['dict'] = f'{type(e).__name__}: {e}'
try:
    vol = modal.Volume.from_name('memsub-m4-sgm-p2p5-b3-shift2-fill-long-v1',create_if_missing=False)
    entries = list(vol.iterdir('b3-run-v1',recursive=True))
    snap['files'] = []
    for entry in entries:
        if entry.type != modal.volume.FileEntryType.FILE:
            continue
        rel = entry.path.lstrip('/').removeprefix('b3-run-v1/')
        assert not PurePosixPath(rel).is_absolute() and '..' not in PurePosixPath(rel).parts
        assert entry.size < 80 * 1024 * 1024, (rel,entry.size)
        dest = REPORT/'volume'/rel
        dest.parent.mkdir(parents=True,exist_ok=True)
        h = hashlib.sha256()
        with dest.open('xb') as f:
            for chunk in vol.read_file(entry.path):
                f.write(chunk)
                h.update(chunk)
        snap['files'].append({'path':rel,'listed_bytes':entry.size,'bytes':dest.stat().st_size,'sha256':h.hexdigest()})
except Exception as e:
    snap['errors']['volume'] = f'{type(e).__name__}: {e}'
receipts = REPORT/'owner-receipts'
receipts.mkdir(exist_ok=True)
for src in sorted(OUT.iterdir()):
    if src.is_file():
        shutil.copy2(src,receipts/src.name)
snap['capture_finished'] = datetime.now(timezone.utc).isoformat()
(REPORT/'live-snapshot.json').write_text(json.dumps(snap,indent=2,default=str)+'\n')
print(json.dumps({'capture_started':snap['capture_started'],'capture_finished':snap['capture_finished'],'call_result':snap.get('call_result'),'dict':snap.get('dict'),'files':len(snap.get('files',[])),'errors':snap['errors']},indent=2,default=str))

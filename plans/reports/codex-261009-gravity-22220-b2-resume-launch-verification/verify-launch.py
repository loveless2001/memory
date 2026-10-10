"""Read launch receipts and live Dict/call state without mutating the campaign."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
from datetime import datetime, timezone

REPORT = Path(__file__).resolve().parent
ROOT = Path('/home/lenovo/projects/memory-occupied-fill-v1-worktree')
PLAN = ROOT / 'plans/261009-1135-m4-sgm-p2p5-b2-occupied-fill-long-run'
os.chdir(ROOT)
spec = importlib.util.spec_from_file_location('resume_launch_audit', ROOT / 'modal-runners/modal-m4-sgm-p2p5-b2-occupied-fill-resume-runner.py')
R = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R)
head = subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
assert head == 'e03ca5a6837db104f79677a492a7d8e889335cdd'
hashes=[]
for line in (PLAN/'SHA256SUMS-b2-resume-package-v0.4.txt').read_text().splitlines():
    if line.startswith('memsub_source_sha256'):
        assert R.local_memsub_sha256() == line.split()[1] == R.EXPECT_MEMSUB_SHA256
    else:
        sha,path=line.split('  ',1)
        assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest() == sha
        hashes.append(path)
meta=json.loads((PLAN/'b2-resume-v1/run.json').read_text())
for f in PLAN.glob('b2-resume-v1.*'):
    if f.is_file(): shutil.copy2(f,REPORT/'launch'/f.name)
shutil.copy2(PLAN/'b2-resume-v1/run.json',REPORT/'run.json')
starts=R.modal.Dict.from_name(R.START_DICT)
keys=['deadline','start-1','start-2','start-3',R.RESUME_KEY]
state={k:starts.get(k) for k in keys}
if 'deadline' in meta:
    assert state[R.RESUME_KEY] == meta['deadline']
call_state,call_info = R.call_state(meta['call_id']) if 'call_id' in meta else ('not recorded',None)
rec={'captured_at':datetime.now(timezone.utc).isoformat(),'head':head,'hashes_verified':len(hashes),
     'launch':meta,'live_dict':state,'call_state':call_state,'call_info':call_info,
     'resume_deadline_utc':datetime.fromtimestamp(meta['deadline'],timezone.utc).isoformat() if 'deadline' in meta else None,
     'original_deadline_utc':datetime.fromtimestamp(state['deadline'],timezone.utc).isoformat()}
(REPORT/'verification.json').write_text(json.dumps(rec,indent=2,default=str))
print(json.dumps(rec,indent=2,default=str))

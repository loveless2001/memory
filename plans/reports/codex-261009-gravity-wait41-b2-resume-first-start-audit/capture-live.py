"""One read-only first-start snapshot. No spawn, deploy, train, evaluation, or remote mutation."""
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath

REPORT = Path(__file__).resolve().parent
ROOT = Path('/home/lenovo/projects/memory-occupied-fill-v1-worktree')
os.chdir(ROOT)
spec = importlib.util.spec_from_file_location('b2_first_start', ROOT/'modal-runners/modal-m4-sgm-p2p5-b2-occupied-fill-resume-runner.py')
R = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R)
meta = json.loads((ROOT/'plans/261009-1135-m4-sgm-p2p5-b2-occupied-fill-long-run/b2-resume-v1/run.json').read_text())
starts = R.modal.Dict.from_name(R.START_DICT)
snapshot = {'capture_started': datetime.now(timezone.utc).isoformat(), 'launch': meta,
            'dict': {k:starts.get(k) for k in ['deadline','start-1','start-2','start-3',R.RESUME_KEY]}}
assert snapshot['dict'][R.RESUME_KEY] == meta['deadline']
snapshot['call_state'], snapshot['call_info'] = R.call_state(meta['call_id'])
files = []
for entry in R.volume.listdir(R.RUN_REL, recursive=True):
    if entry.type != R.modal.volume.FileEntryType.FILE:
        continue
    rel = entry.path.lstrip('/').removeprefix(R.RUN_REL+'/')
    assert not PurePosixPath(rel).is_absolute() and '..' not in PurePosixPath(rel).parts
    if rel.endswith('resume.pt.tmp'):
        continue
    if not rel.endswith(('.txt','.json','.jsonl','resume.pt')):
        files.append({'path':rel,'skipped':True})
        continue
    dest = REPORT/'volume'/rel
    dest.parent.mkdir(parents=True,exist_ok=True)
    h = hashlib.sha256()
    with open(dest,'xb') as f:
        for chunk in R.volume.read_file(entry.path):
            f.write(chunk); h.update(chunk)
    files.append({'path':rel,'bytes':dest.stat().st_size,'sha256':h.hexdigest()})
snapshot['files'] = files
snapshot['capture_finished'] = datetime.now(timezone.utc).isoformat()
(REPORT/'live-snapshot.json').write_text(json.dumps(snapshot,indent=2,default=str))
print(json.dumps({'dict':snapshot['dict'],'call_state':snapshot['call_state'],
                  'captured_files':len(files),'captured_at':snapshot['capture_finished']},indent=2))

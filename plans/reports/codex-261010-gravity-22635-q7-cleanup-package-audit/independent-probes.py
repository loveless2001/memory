"""Read-only real dry run plus controlled refusal probes. Never remove a Q7 target."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys

OUT=Path(__file__).parent
ROOT=Path('/home/lenovo/projects/memory')
SOURCE=ROOT/'plans/reports/claude-261010-1600-m4-sgm-q7-mutation-temp-cleanup-receipt/q7-mutation-temp-dirs-cleanup-fail-closed.py'
spec=importlib.util.spec_from_file_location('q7_package',SOURCE)
q=importlib.util.module_from_spec(spec);spec.loader.exec_module(q)
script_sha=hashlib.sha256(SOURCE.read_bytes()).hexdigest()
inv=json.loads((q.CODEX/'q7-inventory.json').read_text())
removal_calls=[]
original_rmtree=shutil.rmtree
def refuse_removal(*args,**kwargs):
    removal_calls.append([str(x) for x in args])
    raise AssertionError('no removal API may be called in these probes')
checks={}
def check(name,cond):
    checks[name]=bool(cond)
    assert cond,name
check('host rmtree uses fd symlink protection',shutil.rmtree.avoids_symlink_attacks)
try:
    shutil.rmtree=refuse_removal
    q.OUT=OUT/'independent-dry-run';q.OUT.mkdir()
    sys.argv=[str(SOURCE)]
    check('real dry run returns zero',q.main()==0)
    check('no deletion reached',not removal_calls)
    original_glob=q.glob.glob
    def extra(pattern):
        got=original_glob(pattern)
        return got+['/tmp/b3-mut-control-only-virtual-extra'] if pattern==q.PATTERN else got
    q.glob.glob=extra
    q.OUT=OUT/'extra-path-refusal';q.OUT.mkdir()
    check('extra path refuses',q.main()==1)
    q.glob.glob=original_glob
    changed=copy.deepcopy(inv);changed[0]['inode']+=1
    check('inode mismatch refuses',any('pinned directory' in x for x in q.check_targets(changed)))
    root=inv[0]['path']
    child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(10)'],cwd=root)
    try:
        check('real cwd user refuses',bool(q.check_in_use({root})))
    finally:
        child.terminate();child.wait(timeout=5)
    original_sha=q.sha256
    firstlog=json.loads((q.CODEX/'temp-log-manifest.json').read_text())[0]['retained']
    q.sha256=lambda p:'0'*64 if Path(p)==q.CODEX/firstlog else original_sha(p)
    check('retained log corruption refuses',bool(q.check_retained_logs()))
    q.sha256=original_sha
    sys.argv=[str(SOURCE),'--execute','Q5']
    try:q.main()
    except SystemExit as e:check('unselected Q5 refused',e.code==2)
    else:raise AssertionError('Q5 was accepted')
    check('all probes reached no deletion',not removal_calls)
finally:
    shutil.rmtree=original_rmtree
(OUT/'independent-results.json').write_text(json.dumps({'script_sha256':script_sha,'checks':checks,'deletion_calls':removal_calls,'real_target_mutations':0},indent=2)+'\n')
print(json.dumps(checks,indent=2))

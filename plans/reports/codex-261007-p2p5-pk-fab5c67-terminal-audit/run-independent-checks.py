"""Reviewer-owned checks; read-only inputs/remote queries, new output files only."""
import concurrent.futures
import dataclasses
import datetime
import hashlib
import json
import os
import subprocess
import sys
import time
from decimal import Decimal
from pathlib import Path

import modal

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
GROUP = ROOT / 'plans/261006-1345-m4-sgm-p2p5-qwen3-0p6b-screen/p2p5-pk-proof-v1'
EVIDENCE = GROUP / 'volume-evidence/p2p5-pk-proof-v1'
sys.path.insert(0, str(ROOT))
from memsub.sgm.synthetic_pilot_run import source_tree_sha256

def sha(p):
    with p.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()

def save(name, data):
    with (OUT / name).open('x') as f:
        json.dump(data, f, indent=2, default=str, allow_nan=False)
        f.write('\n')

def accept():
    cmd = [sys.executable, 'scripts/sgm-p2p5-pk-packed-proof-acceptance-compare.py',
           '--evidence', str(EVIDENCE), '--grid', 'configs/m4_sgm_p2p5_packed_proof_grid.json',
           '--registry', 'configs/m4_sgm_p2p5_packed_proof_registry.json',
           '--schema', 'configs/m4_sgm_p2p5_packed_proof_output_schema.json',
           '--admission', str(GROUP / 'admission.json'), '--provenance', str(GROUP / 'launch_provenance.json'),
           '--out', str(OUT / 'independent-acceptance.json')]
    start = time.monotonic()
    env = dict(os.environ, OMP_NUM_THREADS='2', MKL_NUM_THREADS='2')
    with (OUT / 'independent-acceptance.log').open('x') as f:
        p = subprocess.run(cmd, cwd=ROOT, env=env, stdout=f, stderr=subprocess.STDOUT, timeout=900)
    independent = json.loads((OUT / 'independent-acceptance.json').read_text())
    original = json.loads((GROUP / 'acceptance.json').read_text())
    r = {'command': cmd, 'returncode': p.returncode, 'wall_seconds': time.monotonic()-start,
         'pass': independent['pass'], 'exactly_matches_committed_acceptance': independent == original,
         'independent_acceptance_sha256': sha(OUT / 'independent-acceptance.json'),
         'committed_acceptance_sha256': sha(GROUP / 'acceptance.json')}
    save('independent-acceptance-status.json', r)
    return r

def files():
    manifest = GROUP / 'SHA256SUMS-volume-evidence.txt'
    entries = [line.split('  ', 1) for line in manifest.read_text().splitlines()]
    errors, paths = [], []
    total = pt_total = pt_count = 0
    for expected, rel in entries:
        p = GROUP / rel
        if not p.resolve().is_relative_to(EVIDENCE.resolve()):
            errors.append({'path': rel, 'reason': 'path outside evidence'})
            continue
        paths.append(p)
        if not p.is_file() or sha(p) != expected:
            errors.append({'path': rel, 'reason': 'missing or hash mismatch'})
            continue
        total += p.stat().st_size
        if p.suffix == '.pt':
            pt_count += 1
            pt_total += p.stat().st_size
    actual = {p for p in EVIDENCE.rglob('*') if p.is_file()}
    bindings = json.loads((ROOT / 'plans/reports/codex-261007-p2p5-pk-d62602c/audit-bindings-and-checks.json').read_text())
    prov = json.loads((GROUP / 'launch_provenance.json').read_text())
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    changed = subprocess.check_output(['git', 'diff', '--name-only', prov['git_head'], head], cwd=ROOT, text=True).splitlines()
    r = {'manifest_sha256': sha(manifest), 'manifest_entries': len(entries), 'unique_paths': len(set(paths)),
         'actual_file_count': len(actual), 'listed_bytes': total, 'pt_count': pt_count, 'pt_bytes': pt_total,
         'errors': errors, 'unlisted_files': sorted(str(p.relative_to(GROUP)) for p in actual-set(paths)),
         'listed_missing_paths': sorted(str(p.relative_to(GROUP)) for p in set(paths)-actual),
         'current_head': head, 'launch_head': prov['git_head'],
         'bound_file_checks': {p: sha(ROOT/p) == expected for p, expected in bindings['sha256'].items()},
         'current_memsub_sha256': source_tree_sha256(ROOT/'memsub'),
         'memsub_matches_launch': source_tree_sha256(ROOT/'memsub') == prov['expected_identity']['memsub'],
         'post_launch_commit_only_group_artifacts': all(p.startswith(str(GROUP.relative_to(ROOT))) for p in changed),
         'post_launch_commit_file_count': len(changed),
         'input_file_sha256': {p: sha(GROUP/p) for p in ['calls.json','collect_status.json','admission.json',
             'guard.json','launch_provenance.json','acceptance.json','billing-today-hourly.json',
             'collect_status.first-terminal-shutdown-unresolved.json','independent-stop-verify.json']}}
    save('independent-file-integrity.json', r)
    return {k:r[k] for k in ['manifest_entries','actual_file_count','errors','unlisted_files','listed_missing_paths',
         'memsub_matches_launch','post_launch_commit_only_group_artifacts','bound_file_checks']}

def remote():
    now = datetime.datetime.now(datetime.timezone.utc)
    prov = json.loads((GROUP / 'launch_provenance.json').read_text())
    app = prov['deployed_app_id']
    def inventory(kind):
        cmd=[sys.executable,'-m','modal',kind,'list','--json','--env','main']
        p=subprocess.run(cmd,cwd=ROOT,text=True,capture_output=True,timeout=45)
        if p.returncode:
            return {'returncode':p.returncode,'stderr':p.stderr[-1000:]}
        rows=json.loads(p.stdout)
        return {'returncode':0,'rows_examined':len(rows),'bound_app_rows':[r for r in rows if r.get('app_id')==app]}
    def billing():
        start=datetime.datetime(2026,10,6,tzinfo=datetime.timezone.utc)
        end=datetime.datetime(2026,10,7,tzinfo=datetime.timezone.utc)
        rows=modal.Workspace.from_context().billing.report(start=start,end=end,resolution='h')
        match=[r for r in rows if r.object_id==app]
        total=sum((r.cost for r in match),Decimal(0))
        return {'start_utc':start.isoformat(),'end_utc':end.isoformat(),'resolution':'h',
             'object_id_filter':app,'rows':[dataclasses.asdict(r) for r in match],
             'reported_app_usage_usd':str(total),'settled_final_cost':False,
             'limits':'App-only hourly snapshot can lag and exclude separate image/build objects. Hold full approved $8.57 reservation.'}
    def dictionaries():
        return {name:dict(modal.Dict.from_name(f'm4-sgm-p2p5-pk-proof-v1-{name}').items()) for name in ['guard','admission']}
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        fs={name:pool.submit(fn) for name,fn in [('apps',lambda:inventory('app')),('containers',lambda:inventory('container')),
                ('billing',billing),('dictionaries',dictionaries)]}
        r={'observed_at_utc':now.isoformat(),'app_id':app,'read_only':True}
        for name,f in fs.items():
            try:r[name]=f.result()
            except Exception as e:r[name]={'read_error':repr(e)}
    ar=r.get('apps',{}).get('bound_app_rows',[])
    cr=r.get('containers',{}).get('bound_app_rows')
    r['shutdown_verified']=r.get('apps',{}).get('returncode')==0 and r.get('containers',{}).get('returncode')==0 and (
          (not ar or all(x.get('state')=='stopped' and str(x.get('tasks'))=='0' for x in ar)) and cr==[])
    r['saved_live_admission_match']=r.get('dictionaries',{}).get('admission')==json.loads((GROUP/'admission.json').read_text())
    save('independent-live-shutdown-billing.json',r)
    return r

if __name__=='__main__':
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        fs={name:pool.submit(fn) for name,fn in [('acceptance',accept),('files',files),('remote',remote)]}
        for name,f in fs.items():
            try:print(json.dumps({'check':name,'result':f.result()},default=str),flush=True)
            except Exception as e:print(json.dumps({'check':name,'error':repr(e)}),flush=True)

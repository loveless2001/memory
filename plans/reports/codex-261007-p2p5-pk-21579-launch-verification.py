"""Read-only approval/provenance, live Modal and collector audit. No collect/stop/spawn."""
import concurrent.futures
import datetime
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

import modal

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from memsub.sgm.synthetic_pilot_run import source_tree_sha256

GROUP = ROOT / 'plans/261006-1345-m4-sgm-p2p5-qwen3-0p6b-screen/p2p5-pk-proof-v1'
OUT = Path(__file__).with_suffix('.json')
prov = json.loads((GROUP / 'launch_provenance.json').read_text())
calls = json.loads((GROUP / 'calls.json').read_text())
approval = json.loads((ROOT / 'plans/reports/codex-261007-p2p5-pk-21577-approved-launch-clearance.json').read_text())
bindings = json.loads((ROOT / 'plans/reports/codex-261007-p2p5-pk-d62602c/audit-bindings-and-checks.json').read_text())
now = time.time()
head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
changed = subprocess.check_output(['git', 'diff', '--name-only', approval['head'], head], cwd=ROOT, text=True).splitlines()
report = {
    'observed_at_utc': datetime.datetime.fromtimestamp(now, datetime.timezone.utc).isoformat(),
    'app_id': prov['deployed_app_id'], 'approval_message_id': 21577,
    'approved_cap_usd': approval['approved_cap_usd'],
    'planned_reservation_usd': prov['ledger']['reserved_total_usd'],
    'reservation_is_conditional_not_observed_spend': True,
    'spawn_epoch': prov['spawn_epoch'], 'deadline_epoch': prov['deadline_epoch'],
    'deadline_bangkok': datetime.datetime.fromtimestamp(prov['deadline_epoch'], datetime.timezone(datetime.timedelta(hours=7))).isoformat(),
    'seconds_since_spawn_at_observation': now - prov['spawn_epoch'],
    'seconds_until_guard_deadline_at_observation': prov['deadline_epoch'] - now,
    'launch_head': prov['git_head'], 'current_head': head,
    'post_launch_commit_files': changed,
    'checks': {
        'launch_head_matches_approval': prov['git_head'] == approval['head'],
        'launch_identity_matches_approval': prov['expected_identity'] == approval['expected_identity'],
        'current_source_matches_launch': source_tree_sha256(ROOT / 'memsub') == prov['expected_identity']['memsub'],
        'all_bound_files_unchanged': all(hashlib.sha256((ROOT / p).read_bytes()).hexdigest() == h for p, h in bindings['sha256'].items()),
        'seven_unique_expected_calls': set(calls) == set(approval['scope']['units']) and len(set(calls.values())) == 7,
        'deadline_6600': abs(prov['deadline_epoch'] - prov['spawn_epoch'] - 6600) < 1e-6,
        'reservation_within_approval': prov['ledger']['reserved_total_usd'] <= approval['approved_cap_usd'],
        'post_launch_commit_only_launch_artifacts': all(p.startswith('plans/261006-1345-m4-sgm-p2p5-qwen3-0p6b-screen/p2p5-pk-proof-v1') for p in changed),
    },
    'calls': calls,
    'read_only_no_controller_or_remote_mutations': True,
    'spend_and_scientific_validity': 'Actual settled charges and GPU proof acceptance remain unverified until terminal audit.',
}

def inventory(kind):
    cmd = [sys.executable, '-m', 'modal', kind, 'list', '--json', '--env', 'main']
    p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=40)
    if p.returncode:
        return {'command': cmd, 'returncode': p.returncode, 'stderr_tail': p.stderr[-500:]}
    d = json.loads(p.stdout)
    if not isinstance(d, list):
        return {'unexpected_schema': type(d).__name__}
    return {'command': cmd, 'returncode': 0, 'rows_examined': len(d),
            'row_keys_seen': sorted({k for row in d for k in row}),
            'bound_app_rows': [row for row in d if row.get('app_id') == prov['deployed_app_id']]}

def dictionaries():
    d = {}
    for name in ('guard', 'admission'):
        try:
            d[name] = dict(modal.Dict.from_name(f'm4-sgm-p2p5-pk-proof-v1-{name}').items())
        except Exception as e:
            d[name] = {'read_error': repr(e)}
    return d

def poll(unit, call):
    try:
        return unit, {'kind': 'result', 'payload': modal.FunctionCall.from_id(call).get(timeout=0)}
    except TimeoutError:
        return unit, {'kind': 'pending'}
    except Exception as e:
        return unit, {'kind': 'error', 'exception_type': type(e).__name__, 'message': str(e)[:1200]}

with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
    fs = {name: pool.submit(fn) for name, fn in (
        ('app_inventory', lambda: inventory('app')),
        ('container_inventory', lambda: inventory('container')),
        ('dicts', dictionaries),
    )}
    ps = [pool.submit(poll, unit, call) for unit, call in calls.items()]
    for name, f in fs.items():
        try:
            report[name] = f.result()
        except Exception as e:
            report[name] = {'read_error': repr(e)}
    report['call_poll'] = dict(f.result() for f in ps)

guard = report.get('dicts', {}).get('guard', {})
report['checks']['live_guard_app_and_deadline_match'] = (
    guard.get('app_id') == prov['deployed_app_id'] and guard.get('deadline_epoch') == prov['deadline_epoch'])
report['checks']['reaper_first_tick_recorded'] = isinstance(guard.get('first_tick'), (int, float))
report['admission_start_keys'] = sorted(report.get('dicts', {}).get('admission', {}))
admit = report.get('dicts', {}).get('admission', {})
allowed = {f'{unit}-start-{n}' for unit, limit in {**approval['scope']['planned_scenario_starts'], 'timing': 1}.items()
           for n in range(1, limit + 1)}
report['checks']['admission_keys_within_fixed_allowances'] = set(admit) <= allowed
report['collector_status'] = json.loads((GROUP / 'collect_status.json').read_text())
report['collector_log_tail'] = (GROUP.parent / 'p2p5-pk-proof-v1.collect.log').read_text()[-2200:]
ps = subprocess.check_output(['ps', '-eo', 'pid,ppid,args'], text=True)
report['collector_processes'] = [line.strip() for line in ps.splitlines()
    if 'scratchpad/pk-proof-collect-loop.sh' in line and '/bin/bash ' in line and ' -c ' not in line]

with OUT.open('x') as f:
    json.dump(report, f, indent=2, default=str)
print(json.dumps(report, indent=2, default=str))

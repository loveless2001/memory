"""Independent artifact/provenance and descriptive diagnosis review. No model work."""
import datetime as dt
import hashlib
import json
import math
import os
import shutil
import statistics
import subprocess
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
BASE = ROOT / 'plans/reports/claude-261008-2350-p2p5-taskhead-dead-start-address-diagnosis'
RUN = BASE / 'run-v1'
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
read = lambda p: json.loads(Path(p).read_text())
consumed = {}
def bind(path):
    path = Path(path)
    consumed[str(path.relative_to(ROOT))] = sha(path)
    return consumed[str(path.relative_to(ROOT))]

index = read(BASE / 'inputs-index.json')
run = read(RUN / 'run.json')
prior = read(ROOT / 'plans/reports/codex-261008-p2p5-pk-21944-diagnosis-r2-audit/verdict.json')
for name, wanted in prior['bindings'].items():
    assert bind(ROOT / name) == wanted
assert run['script_sha256'] == prior['bindings'][run['argv'][0]]
assert run['index_sha256'] == bind(BASE / 'inputs-index.json')
assert run['identity'] == prior['run_identity_preflight']['identity']
assert [e['name'] for e in index['entries']] == [e['name'] for e in run['done']]
assert len(run['done']) == 14 and len({e['name'] for e in run['done']}) == 14
assert (BASE / 'run-v1.exit.txt').read_text().splitlines()[0] == '0'
assert not (RUN / 'ERROR.txt').exists()
started = dt.datetime.fromisoformat(run['started_utc'].replace('Z', '+00:00'))
finished = dt.datetime.fromisoformat(run['finished_utc'].replace('Z', '+00:00'))
assert 0 < (finished - started).total_seconds() < 3600
console = [json.loads(line) for line in (BASE / 'run-v1.console.log').read_text().splitlines() if line.strip()]
assert console == run['done']

def finite(v):
    if isinstance(v, dict):
        for child in v.values(): finite(child)
    elif isinstance(v, list):
        for child in v: finite(child)
    elif isinstance(v, (float, int)): assert math.isfinite(v)

rows, gradients, reports = [], {}, {}
keys = ['query_read_absent_weight_mean', 'query_read_all_positive_cells_absent_fraction',
        'align_within_1_cell', 'align_stencil_intersects', 'align_spatial_coupling_mean',
        'centroid_offset_cells', 'read_spread_cells', 'value_write_spread_cells',
        'query_q_mean_pairwise_cos', 'value_k_mean_pairwise_cos']
replay = []
for e in index['entries']:
    p = RUN / (e['name'] + '.json')
    bind(p)
    x = reports[e['name']] = read(p)
    finite(x)
    assert x['entry'] == e and x['kind'] == e['kind'] and x['name'] == e['name']
    for field in ['manifest', 'telemetry'] + ([] if e['params'] == 'init' else ['params']):
        assert bind(ROOT / e[field]) == e[field + '_sha256']
    manifest = read(ROOT / e['manifest'])
    assert x['pilot_config'] == {**manifest['pilot_config'], 'device': e['device']}
    cfg = x['pilot_config']
    assert (cfg['n_bindings'], cfg['n_queries'], cfg['filler_len']) == (32, 4, 40)
    if e['kind'] == 'grad_at_init':
        assert e['params'] == 'init' and x['grad_reach_at_init']['episodes'] == 2
        gradients[e['name']] = x['grad_reach_at_init']
        continue
    assert x['dev_episodes'] == 64 and x['dev_queries'] == 256
    assert cfg['batch'] == 16 and cfg['eval_batches'] == 4
    step = 0 if e['params'] == 'init' else e.get('expected_step', cfg['steps'])
    logged = [r['eval'] for r in [json.loads(line) for line in (ROOT / e['telemetry']).read_text().splitlines() if line.strip()]
              if r.get('step') == step and isinstance(r.get('eval'), dict)]
    assert len(logged) == 1
    absent = statistics.mean(v for lay in x['per_layer_head'].values() for v in lay[keys[0]])
    all_abs = statistics.mean(v for lay in x['per_layer_head'].values() for v in lay[keys[1]])
    diff_abs = abs(absent - logged[0]['query_empty_read_weight'])
    diff_occ = abs(x['bank']['occupancy_mean'] - logged[0]['occupancy_mean'])
    assert diff_abs <= 1e-4 and diff_occ <= 1e-4
    assert x['training_dev_eval_check']['status'] == 'reproduced'
    assert x['training_dev_eval_check']['logged_training_dev_accuracy_not_recomputed'] == logged[0]['accuracy']
    replay.append({'name': e['name'], 'step': step, 'diff_absent': diff_abs, 'diff_occupancy': diff_occ})
    pooled = {k: statistics.mean(v for lay in x['per_layer_head'].values() for v in lay[k]) for k in keys}
    rows.append({'name': e['name'], 'step': step, 'bank': x['bank'], 'head_means': pooled,
                 'per_layer_means': {l: {k: statistics.mean(v[k]) for k in keys} for l, v in x['per_layer_head'].items()},
                 'logged_accuracy_not_recomputed': logged[0]['accuracy']})

assert len(rows) == 12 and len(gradients) == 2
snapshot = dt.datetime.now(dt.timezone.utc).isoformat()
ps = subprocess.run(['ps', '-eo', 'pid,ppid,pgid,sid,stat,args'], text=True, capture_output=True, check=True).stdout
matching = []
for line in ps.splitlines()[1:]:
    fields = line.split(None, 5)
    if fields[0] in ('2778183', '2778184', '2778185') or fields[2] == '2778184': matching.append(line)
assert not matching
gpu_apps = subprocess.check_output(['nvidia-smi', '--query-compute-apps=pid,process_name,used_memory', '--format=csv,noheader'], text=True)
gpu_mem = subprocess.check_output(['nvidia-smi', '--query-gpu=memory.used', '--format=csv,noheader'], text=True)
assert not gpu_apps.strip() and gpu_mem.strip() == '0 MiB'
cleanup = {'observed_utc': snapshot, 'known_pids_or_pgid_matches': matching,
           'gpu_compute_apps': gpu_apps, 'gpu_memory_used': gpu_mem.strip()}
(OUT / 'cleanup.json').write_text(json.dumps(cleanup, indent=2) + '\n')

early = {}
for seed in (0, 1):
    e = next(e for e in index['entries'] if e['name'] == f'qwen-probe-taskhead-s{seed}-init')
    telemetry = [json.loads(line) for line in (ROOT / e['telemetry']).read_text().splitlines() if line.strip()]
    early[str(seed)] = [{k: r[k] for k in ('step', 'loss', 'grad_norm', 'update_norm') if k in r}
                       for r in telemetry if 0 < r.get('step', 999) <= 100 and 'grad_norm' in r]
(OUT / 'saved-early-training-telemetry.json').write_text(json.dumps(early, indent=2) + '\n')
snapshot_dir = OUT / 'frozen-terminal-artifacts'
snapshot_dir.mkdir(exist_ok=True)
for p in sorted(RUN.glob('*.json')):
    shutil.copyfile(p, snapshot_dir / p.name)
for name in ['inputs-index.json', 'run-v1.launch.txt', 'run-v1.exit.txt', 'run-v1.console.log']:
    bind(BASE / name)
    shutil.copyfile(BASE / name, snapshot_dir / name)
bind(RUN / 'run.json')
evidence = {'status': 'COMPLETE_EXIT_0_CLEANUP_VERIFIED', 'entries': 14, 'geometry_entries': 12,
            'grad_entries': 2, 'run_wall_seconds': (finished - started).total_seconds(),
            'replay_checks': replay, 'summaries': rows, 'gradients': gradients,
            'cleanup': cleanup, 'independent_model_execution': False,
            'consumed_sha256': consumed}
(OUT / 'evidence.json').write_text(json.dumps(evidence, indent=2) + '\n')
columns = ['name', 'step', *keys]
(OUT / 'head-means.tsv').write_text('\t'.join(columns) + '\n' + ''.join(
    '\t'.join([r['name'], str(r['step']), *[f"{r['head_means'][k]:.10g}" for k in keys]]) + '\n' for r in rows))
print(json.dumps({'status': evidence['status'], 'run_wall_seconds': evidence['run_wall_seconds'],
                  'max_dev_replay_absent_difference': max(r['diff_absent'] for r in replay),
                  'max_dev_replay_occupancy_difference': max(r['diff_occupancy'] for r in replay),
                  'head_means': {r['name']: r['head_means'] for r in rows}}, indent=2))

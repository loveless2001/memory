import hashlib
import json
import math
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

plan = Path('/home/lenovo/projects/memory/plans/261005-0210-m4-sgm-p0-p2')
out = plan / 'p2d/step2-partial-v1'
mirror = plan / 'runs/p2d-diagnostics-v1/status-audit/volume-mirror'
path = out / 'step2-readings.json'
if not path.exists():
    print('Report not yet written')
    raise SystemExit(0)
report = json.loads(path.read_text())
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()

def scores(p):
    rows = [json.loads(line) for line in p.read_text().splitlines()]
    by_iv = defaultdict(lambda: defaultdict(dict))
    for r in rows:
        assert type(r['correct']) is bool and r['correct'] == (r['pred'] == r['label'])
        ep = (r['batch'], r['episode'], r['episode_hash'])
        assert r['query'] not in by_iv[r['intervention']][ep]
        by_iv[r['intervention']][ep][r['query']] = int(r['correct'])
    assert set(by_iv) == {'none', 'bank_derange', 'coord_shuffle', 'read_offset', 'query_off'}
    for eps in by_iv.values():
        assert len(eps) == 256 and all(set(qs) == {0, 1, 2, 3} for qs in eps.values())
    return {iv: {ep: sum(qs.values()) / 4 for ep, qs in eps.items()} for iv, eps in by_iv.items()}

def paired(a, b):
    assert set(a) == set(b)
    values = [a[k] - b[k] for k in sorted(a)]
    diff = statistics.mean(values)
    hw = 1.96 * statistics.stdev(values) / math.sqrt(len(values))
    return {'diff': diff, 'lo': diff - hw, 'hi': diff + hw, 'n': len(values)}

def equal_interval(a, b):
    assert a['n'] == b['n'] == 256
    for k in ('diff', 'lo', 'hi'):
        assert math.isclose(a[k], b[k], rel_tol=0, abs_tol=1e-12), (k, a[k], b[k])

assert report['report_status'] == 'partial' and report['partial_mode'] is True
assert Counter(c['status'] for c in report['coverage'].values()) == {'valid_complete': 6, 'incomplete': 6}
assert set(report['baselines']) == {'N16-s0', 'N16-s1', 'N32-s0', 'N32-s1'}
summary = {}
for tag, n in (('filleroff', 16), ('addrsup', 32)):
    cell = report['arms'][tag][f'N{n}']
    assert cell['evaluation_status'] == 'paired' and set(cell['seeds']) == {'0', '1'}
    summaries = {}
    for seed, r in cell['seeds'].items():
        source = mirror / r['run_id']
        base = report['baselines'][f'N{n}-s{seed}']
        assert base['final_eval_seed'] == 9300011 + int(seed)
        for field, filename in [('rows_sha256', 'per_example_results.jsonl'),
                                ('trained_parameters_sha256', 'trained_parameters.safetensors'),
                                ('run_manifest_sha256', 'run_manifest.json'),
                                ('metrics_sha256', 'metrics.json')]:
            assert r[field] == sha(source / filename)
        assert base['rows_sha256'] == sha(out / base['rows_file'])
        a, b = scores(source / 'per_example_results.jsonl'), scores(out / base['rows_file'])
        contrast = paired(a['none'], b['none'])
        equal_interval(contrast, r['vs_v2'])
        acc, base_acc = statistics.mean(a['none'].values()), statistics.mean(b['none'].values())
        assert acc == r['final_accuracy'] and base_acc == r['baseline_accuracy']
        derange = statistics.mean(a['bank_derange'].values())
        p_der, p_offset = paired(a['none'], a['bank_derange']), paired(a['none'], a['read_offset'])
        equal_interval(p_der, r['memory_use']['none_minus_derange'])
        equal_interval(p_offset, r['memory_use']['none_minus_read_offset'])
        mem = derange <= .04 and p_der['lo'] > 0 and p_offset['lo'] > 0
        assert mem == r['memory_use']['pass'] and derange == r['memory_use']['derange_accuracy']
        layers = {}
        for layer in ('1', '3'):
            geo, bg = r['geometry'][layer], base['geometry'][layer]
            assert all(math.isfinite(v) for vals in geo.values() for v in vals)
            heads = [geo['median_distance'][h] < bg['median_distance'][h]
                     and geo['target_coupling'][h] > 0
                     and geo['target_coupling'][h] >= 2 * geo['other_coupling'][h]
                     and geo['read_spread'][h] >= 1 for h in (0, 1)]
            assert r['alignment']['layers'][layer]['heads_pass'] == heads
            layers[layer] = any(heads)
        assert r['alignment']['pass'] == all(layers.values())
        if tag == 'filleroff':
            assert r['dev_telemetry']['beta_by_token_class']['filler'] > 0
            assert r['dev_telemetry']['effective_beta_by_token_class']['filler'] == 0
        summaries[seed] = {'baseline_accuracy': base_acc, 'treatment_accuracy': acc,
                           'paired': contrast, 'memory_use': mem, 'alignment': r['alignment']['pass']}
    gain = all(s['paired']['diff'] >= .05 and s['paired']['lo'] > 0 for s in summaries.values())
    assert gain == cell['reproducible_gain_vs_v2']
    assert cell['memory_use_both_seeds'] == all(s['memory_use'] for s in summaries.values())
    assert cell['alignment_both_seeds'] == all(s['alignment'] for s in summaries.values())
    summary[f'{tag}-N{n}'] = {'reading': cell['reading'], 'seeds': summaries}
for tag in ('filleroff', 'addrsup'):
    cell = report['arms'][tag]['N64']
    assert cell['evaluation_status'] == 'descriptive_single_seed' and len(cell['seeds']) == 1
    assert cell['reproducible_gain_vs_v2'] is None
    assert all('vs_v2' not in r for r in cell['seeds'].values())
for cell in report['arms']['long'].values():
    assert cell['evaluation_status'] == 'unevaluable' and cell['seeds'] == {}
    assert cell['reproducible_gain_vs_v2'] is None
verification = {'checked_at_utc': datetime.now(timezone.utc).isoformat(),
                'readings_sha256': sha(path), 'independent_statistics_checks': 'passed',
                'summary': summary}
(out / 'readings-verification.json').write_text(json.dumps(verification, indent=2) + '\n')
print(json.dumps(verification, indent=2))

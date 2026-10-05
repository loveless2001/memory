"""Audit saved full readings without rerunning evaluation or importing its rules.

Usage: .venv/bin/python <this file> [full-output-dir] [extracted-input-evidence-dir]
Statistics use only the Python standard library; checkpoint equality uses
safetensors/torch. No training, evaluation, Modal calls, or input mutations.
"""
import hashlib
import json
import math
import statistics
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

out = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parents[1]
plan = out.parent.parent
root = plan.parent.parent
evidence = Path(sys.argv[2]).resolve() if len(sys.argv) > 2 else None
mirror_for = lambda i: evidence / i['group'] if evidence else Path(i['mirror'])
report_path = out / 'step2-readings.json'
report = json.loads(report_path.read_text())
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
ivs = {'none', 'bank_derange', 'coord_shuffle', 'read_offset', 'query_off'}


def scores(path):
    by_iv = defaultdict(lambda: defaultdict(dict))
    for line in path.read_text().splitlines():
        row = json.loads(line)
        assert type(row['correct']) is bool and row['correct'] == (row['pred'] == row['label'])
        assert 0 <= row['pred'] < 64 and 0 <= row['label'] < 64
        key = (row['batch'], row['episode'], row['episode_hash'])
        assert row['query'] not in by_iv[row['intervention']][key]
        by_iv[row['intervention']][key][row['query']] = int(row['correct'])
    assert set(by_iv) == ivs
    reference = set(by_iv['none'])
    assert len(reference) == 256
    for episodes in by_iv.values():
        assert set(episodes) == reference
        assert {(b, e) for b, e, _ in episodes} == {(b, e) for b in range(16) for e in range(16)}
        assert all(set(queries) == {0, 1, 2, 3} for queries in episodes.values())
    return {iv: {ep: sum(q.values()) / 4 for ep, q in episodes.items()}
            for iv, episodes in by_iv.items()}


def paired(a, b):
    assert set(a) == set(b), 'episode pairing differs'
    differences = [a[k] - b[k] for k in sorted(a)]
    mean = statistics.mean(differences)
    half = 1.96 * statistics.stdev(differences) / math.sqrt(len(differences))
    return {'diff': mean, 'lo': mean - half, 'hi': mean + half, 'n': len(differences)}


def check_interval(actual, expected):
    assert actual['n'] == expected['n'] == 256
    for key in ('diff', 'lo', 'hi'):
        assert math.isclose(actual[key], expected[key], abs_tol=1e-12, rel_tol=0), (key, actual, expected)


def reproducible(contrasts):
    assert len(contrasts) == 2
    return all(p['diff'] >= .05 and p['lo'] > 0 for p in contrasts)


assert report['report_status'] == 'complete' and report['partial_mode'] is False
assert len(report['coverage']) == len(report['index']) == 12
assert Counter(c['status'] for c in report['coverage'].values()) == {'valid_complete': 12}
assert Counter(i['group'] for i in report['index'].values()) == {
    'p2d-diagnostics-v1': 6, 'p2d-diagnostics-v1-topup': 6}
assert set(report['baselines']) == {f'N{n}-s{s}' for n in (16, 32, 64) for s in (0, 1)}
assert report['analysis']['git_head'] == 'ac495380b898d14e847e99eefa8274adb9d19582'
for field, filename in [('readings_sha256', 'sgm-p2d-step2-readings.py'),
                        ('rules_sha256', 'sgm-p2d-step2-decision-rules.py')]:
    assert report['analysis'][field] == sha(out / 'analysis-sources' / filename)
    assert report['analysis'][field] == hashlib.sha256(subprocess.check_output(
        ['git', 'show', f"ac49538:scripts/{filename}"], cwd=root)).hexdigest()
for name, group in report['groups'].items():
    run = evidence / name if evidence else Path(group['runs'])
    assert group['launch_provenance_sha256'] == sha(run / 'launch_provenance.json')
    assert group['grid_snapshot_sha256'] == sha(run / 'grid.json')
    assert group['launch'] == json.loads((run / 'launch_provenance.json').read_text())
    assert set(group['cells']) >= {r for r, i in report['index'].items() if i['group'] == name}
for rid, index in report['index'].items():
    mirror = mirror_for(index) / rid
    assert index['group'] == index['manifest_modal_group'] == report['coverage'][rid]['group']
    for filename, digest in index['input_sha256'].items():
        assert digest == sha(mirror / filename), (rid, filename)
    manifest = json.loads((mirror / 'run_manifest.json').read_text())
    assert manifest['modal_group'] == index['group']
    assert manifest['git_head'] == index['manifest_git_head'] == index['launch_git_head']

baselines, baseline_comparison = {}, {}
v2_mirror = evidence / 'p2-load-sweep-v2' if evidence else plan / 'runs/p2-load-sweep-v2-volume-mirror'
for name, base in report['baselines'].items():
    n, seed = map(int, name[1:].split('-s'))
    assert base['final_eval_seed'] == 9300011 + seed
    assert base['frozen_commit'] == '1d62903e3e093ee625642b5ef4c86b3b6cae6d2b'
    rows = out / base['rows_file']
    assert base['rows_sha256'] == sha(rows)
    source = v2_mirror / f'main-learned-n{n}-s{seed}'
    manifest = json.loads((source / 'run_manifest.json').read_text())
    assert base['trained_parameters_sha256'] == sha(source / 'trained_parameters.safetensors')
    assert manifest['memsub_source_sha256'] == base['frozen_source_sha256']
    baselines[name] = scores(rows)
    prior = out.parent / 'step2-partial-v1' / base['rows_file']
    if prior.exists():
        baseline_comparison[name] = sha(prior) == sha(rows)
        assert baseline_comparison[name], 'fresh baseline differs from prior partial rows'

summary = {}
for tag, ns in {'filleroff': (16, 64), 'long': (16, 32), 'addrsup': (32, 64)}.items():
    for n in ns:
        cell = report['arms'][tag][f'N{n}']
        assert cell['evaluation_status'] == 'paired' and set(cell['seeds']) == {'0', '1'}
        seed_summary = {}
        for seed, record in cell['seeds'].items():
            index = report['index'][record['run_id']]
            source = mirror_for(index) / record['run_id']
            assert record['group'] == index['group']
            for field, filename in [('rows_sha256', 'per_example_results.jsonl'),
                                    ('trained_parameters_sha256', 'trained_parameters.safetensors'),
                                    ('run_manifest_sha256', 'run_manifest.json'), ('metrics_sha256', 'metrics.json')]:
                assert record[field] == sha(source / filename)
            a, b = scores(source / 'per_example_results.jsonl'), baselines[f'N{n}-s{seed}']
            contrast = paired(a['none'], b['none'])
            check_interval(contrast, record['vs_v2'])
            accuracy, base_accuracy = statistics.mean(a['none'].values()), statistics.mean(b['none'].values())
            assert accuracy == record['final_accuracy'] and base_accuracy == record['baseline_accuracy']
            derange = statistics.mean(a['bank_derange'].values())
            p_der, p_offset = paired(a['none'], a['bank_derange']), paired(a['none'], a['read_offset'])
            check_interval(p_der, record['memory_use']['none_minus_derange'])
            check_interval(p_offset, record['memory_use']['none_minus_read_offset'])
            memory = derange <= .04 and p_der['lo'] > 0 and p_offset['lo'] > 0
            assert memory == record['memory_use']['pass'] and derange == record['memory_use']['derange_accuracy']
            alignment = []
            for layer in ('1', '3'):
                g = record['geometry'][layer]
                bg = report['baselines'][f'N{n}-s{seed}']['geometry'][layer]
                assert all(len(v) == 2 and all(math.isfinite(x) for x in v) for v in g.values())
                heads = [g['median_distance'][h] < bg['median_distance'][h]
                         and g['target_coupling'][h] > 0
                         and g['target_coupling'][h] >= 2 * g['other_coupling'][h]
                         and g['read_spread'][h] >= 1 for h in (0, 1)]
                assert heads == record['alignment']['layers'][layer]['heads_pass']
                assert any(heads) == record['alignment']['layers'][layer]['pass']
                alignment.append(any(heads))
            assert all(alignment) == record['alignment']['pass']
            if tag == 'filleroff':
                assert record['dev_telemetry']['beta_by_token_class']['filler'] > 0
                assert record['dev_telemetry']['effective_beta_by_token_class']['filler'] == 0
            sr = {'accuracy': accuracy, 'baseline_accuracy': base_accuracy, 'vs_v2': contrast,
                  'alignment': all(alignment), 'memory_use': memory}
            if tag == 'long':
                own = scores(source / 'per_example_results_step1500.jsonl')
                own_contrast = paired(a['none'], own['none'])
                check_interval(own_contrast, record['vs_own_1500'])
                for field, filename in [('step1500_rows_sha256', 'per_example_results_step1500.jsonl'),
                                        ('step1500_parameters_sha256', 'trained_parameters_step1500.safetensors')]:
                    assert record[field] == sha(source / filename) == index['input_sha256'][filename]
                from safetensors.torch import load_file
                import torch
                checkpoint = source / 'trained_parameters_step1500.safetensors'
                baseline = v2_mirror / f'main-learned-n{n}-s{seed}' / 'trained_parameters.safetensors'
                left, right = load_file(str(checkpoint)), load_file(str(baseline))
                tensor_equal = left.keys() == right.keys() and all(torch.equal(left[k], right[k]) for k in left)
                continuity = {'file_hash_equal': sha(checkpoint) == sha(baseline), 'tensors_equal': tensor_equal,
                              'label': None if tensor_equal else 'continuity discrepancy (uninvestigated)'}
                assert continuity == record['continuity_1500_vs_v2']
                sr.update({'own_1500_accuracy': statistics.mean(own['none'].values()),
                           'vs_own_1500': own_contrast, 'continuity': continuity})
            seed_summary[seed] = sr
        gain = reproducible([s['vs_v2'] for s in seed_summary.values()])
        align = all(s['alignment'] for s in seed_summary.values())
        memory = all(s['memory_use'] for s in seed_summary.values())
        assert (gain, align, memory) == (cell['reproducible_gain_vs_v2'], cell['alignment_both_seeds'], cell['memory_use_both_seeds'])
        if tag == 'filleroff':
            reading = 'supports harm from tail-filler writes for this recipe' if gain else 'no registered reproducible filler-off gain'
        elif tag == 'addrsup':
            reading = ('SUPPORTS usefulness of this supervised routing-training recipe' if gain and align and memory
                       else 'alignment improved; no registered reproducible gain' if align and not gain
                       else 'probe did not establish the intended alignment; cause unresolved' if not align
                       else 'registered reproducible gain without registered memory-use evidence')
        else:
            own_gain = reproducible([s['vs_own_1500'] for s in seed_summary.values()])
            reading = {'4500_vs_own_1500': 'reproducible gain' if own_gain else 'no registered reproducible gain',
                       '4500_vs_v2': 'reproducible gain' if gain else 'no registered reproducible gain',
                       'overall': 'budget effect for this recipe' if own_gain and gain else 'budget effect not established (both registered contrasts required)'}
        assert reading == cell['reading']
        summary[f'{tag}-N{n}'] = {'reading': reading, 'gain_vs_v2': gain, 'alignment': align,
                                 'memory_use': memory, 'seeds': seed_summary}

resume_path = out.with_suffix('.resume.json')
resume = json.loads(resume_path.read_text())
assert resume['state'] == 'completed' and resume['returncode'] == 0
assert not list(Path(resume['aborted_attempt']['out']).iterdir())
assert resume['aborted_attempt']['log_sha256'] == sha(Path(resume['aborted_attempt']['log']))
for p in (out.parent / 'step2-partial-v1').rglob('*'):
    if p.is_file():
        rel = str(p.relative_to(root))
        assert p.read_bytes() == subprocess.check_output(['git', 'show', f'ac49538:{rel}'], cwd=root)
verification = {'checked_at_utc': datetime.now(timezone.utc).isoformat(), 'readings_sha256': sha(report_path),
                'verification': 'passed', 'method': 'independent standard-library episode statistics and rule decisions; checkpoint tensor equality; no evaluation rerun',
                'cells_verified': 12, 'baselines_verified': 6, 'partial_baselines_byte_identical': baseline_comparison,
                'aborted_attempt_preserved': True, 'partial_artifacts_unchanged': True,
                'resume_provenance_sha256': sha(resume_path), 'input_evidence': str(evidence) if evidence else 'original bound mirrors',
                'summary': summary}
(out / ('archive-replay-verification.json' if evidence else 'readings-verification.json')).write_text(json.dumps(verification, indent=2) + '\n')
print(json.dumps(verification, indent=2))

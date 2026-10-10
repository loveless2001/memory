"""Read-only CPU audit of B2 @ed82721. No live Modal calls or real subprocesses."""
import contextlib
import copy
import hashlib
import importlib.util
import io
import json
import math
import pathlib
import subprocess
import sys
import tarfile
import tempfile
import types
from dataclasses import asdict
from unittest.mock import patch

REPORT = pathlib.Path(__file__).resolve().parent
ROOT = pathlib.Path((REPORT / 'snapshot-path.txt').read_text().strip())
sys.path.insert(0, str(ROOT))

def load(rel, name):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

B = load('scripts/sgm-p2p5-b2-occupied-fill-long-run-train.py', 'audit_b2_train')
R = load('modal-runners/modal-m4-sgm-p2p5-b2-occupied-fill-long-run-runner.py', 'audit_b2_runner')
RAW = R.run_b2_remote.get_raw_f()
SUPERVISE = R.supervise_child

class Starts:
    def __init__(self, deadline, claimed=0):
        self.data = {'deadline': deadline, **{f'start-{i+1}': {} for i in range(claimed)}}
    def put(self, key, value, skip_if_exists=False):
        if skip_if_exists and key in self.data:
            return False
        self.data[key] = value
        return True
    def get(self, key):
        return self.data.get(key)

def worker_case(name, actions, *, guard_fail=False, commit_fail=False, commit_delay=0,
                setup_delay=0, starts_used=0, version_ok=True, dict_deadline=3000.0,
                kill_race=False, populated=False):
    clock, events = {'t': 1000.0}, []
    starts = Starts(dict_deadline, starts_used)
    class Child:
        pid = 987654321
        done = None
        def wait(self, timeout=None):
            events.append(['wait', timeout])
            if timeout is None:
                self.done = self.done if self.done is not None else -9
                return self.done
            action = actions.pop(0) if actions else 0
            if action == 'timeout':
                clock['t'] += timeout
                raise subprocess.TimeoutExpired('fake trainer', timeout)
            if action == 'exception':
                raise RuntimeError('simulated poll failure')
            self.done = action
            return action
        def poll(self):
            return self.done
    child = Child()
    class Volume:
        count = 0
        def reload(self):
            events.append(['reload'])
            clock['t'] += setup_delay
        def commit(self):
            events.append(['commit'])
            delay = commit_delay if isinstance(commit_delay, (float, int)) else commit_delay[self.count]
            failed = commit_fail if isinstance(commit_fail, bool) else commit_fail[self.count]
            self.count += 1
            clock['t'] += delay
            if failed:
                raise OSError('simulated failed volume commit')
    guards = []
    def killer(target, seconds):
        events.append(['arm', target, seconds])
        if guard_fail and target.startswith('-'):
            raise OSError('simulated child watchdog Popen failure')
        obj = types.SimpleNamespace(target=target)
        guards.append(obj)
        return obj
    def cancel(obj):
        if obj is not None:
            events.append(['cancel', obj.target])
    def killpg(pid, sig):
        events.append(['kill', pid, int(sig)])
        child.done = -9
        if kill_race:
            raise ProcessLookupError('simulated process group exited between poll and kill')
    def popen(*args, **kw):
        events.append(['spawn', kw.get('start_new_session')])
        (run / 'B2').mkdir(exist_ok=True)
        (run / 'B2' / 'resume.pt').write_bytes(b'checkpoint')
        (run / 'B2' / 'resume.pt.tmp').write_bytes(b'partial checkpoint')
        (run / 'B2' / 'routing_telemetry.jsonl').write_text('{}\n')
        return child
    with tempfile.TemporaryDirectory(prefix='codex-b2-worker-mock-') as td:
        run = pathlib.Path(td)
        if populated:
            (run / 'foreign.txt').write_text('previous campaign')
        with contextlib.ExitStack() as stack:
            values = {
                'RUN_DIR': str(run), 'volume': Volume(), '_versions_ok': lambda: {'ok': version_ok, 'got': {}},
                'time': types.SimpleNamespace(time=lambda: clock['t']), 'deadline_killer': killer,
                'cancel_killer': cancel,
                'modal': types.SimpleNamespace(Dict=types.SimpleNamespace(from_name=lambda *a, **k: starts)),
                'subprocess': types.SimpleNamespace(Popen=popen, TimeoutExpired=subprocess.TimeoutExpired),
                'supervise_child': lambda *a: SUPERVISE(*a, killpg=killpg, clock=lambda: clock['t']),
            }
            for k, v in values.items():
                stack.enter_context(patch.object(R, k, v))
            stack.enter_context(patch.object(R.os, 'killpg', killpg))
            try:
                result = RAW(3000.0)
                tar = result.pop('tar', None)
                if tar is not None:
                    with tarfile.open(fileobj=io.BytesIO(tar), mode='r:gz') as f:
                        result['tar_members'] = f.getnames()
                error = None
            except Exception as e:
                result, error = None, f'{type(e).__name__}: {e}'
    return {'name': name, 'result': result, 'error': error, 'events': events,
            'child_still_running': any(e[0] == 'spawn' for e in events) and child.done is None,
            'clock': clock['t']}

cases = [
    worker_case('periodic commit then success', ['timeout', 0]),
    worker_case('commit failure counted, completed child', ['timeout', 0], commit_fail=True),
    worker_case('poll exception cleanup', ['exception']),
    worker_case('child watchdog arming failure', [0], guard_fail=True),
    worker_case('late commit reaches child budget', ['timeout'], commit_delay=[0, 1900, 0]),
    worker_case('setup consumes minimum remaining budget', [0], setup_delay=1200),
    worker_case('three starts already used', [0], starts_used=3),
    worker_case('immutable deadline mismatch', [0], dict_deadline=3001.0),
    worker_case('version mismatch', [0], version_ok=False),
    worker_case('nonzero trainer exit is a normal function return', [7]),
    worker_case('process exit race while cleaning a polling error', ['exception'], kill_race=True),
    worker_case('initial commit consumes minimum startup budget', [0], commit_delay=[1900, 0]),
    worker_case('initial commit failure omitted from error count', ['timeout', 0], commit_fail=[True, False, False]),
    worker_case('start-1 refuses populated volume directory', [0], populated=True),
]
assert cases[0]['result']['returncode'] == 0
assert cases[0]['result']['volume_commit_errors'] == 0
assert sum(e[0] == 'commit' for e in cases[0]['events']) == 3
assert not any(n.endswith(('resume.pt', 'resume.pt.tmp')) for n in cases[0]['result']['tar_members'])
assert any(n.endswith('routing_telemetry.jsonl') for n in cases[0]['result']['tar_members'])
assert cases[1]['result']['volume_commit_errors'] == 2 and not cases[1]['child_still_running']
assert cases[2]['error'] and not cases[2]['child_still_running']
assert sum(e[0] == 'cancel' for e in cases[2]['events']) == 2
assert cases[3]['error'] and not cases[3]['child_still_running']
assert any(e[0] == 'kill' for e in cases[3]['events'])
assert cases[4]['result']['returncode'] == 'timeout' and cases[4]['clock'] < 3000
assert all(c['result'].get('refused') and not c['child_still_running'] for c in cases[5:9])
assert cases[9]['result']['returncode'] == 7 and cases[9]['error'] is None
assert cases[10]['error'].startswith('ProcessLookupError')
assert sum(e[0] == 'cancel' for e in cases[10]['events']) == 1
assert cases[11]['result']['returncode'] == 'timeout' and any(e[0] == 'spawn' for e in cases[11]['events'])
assert cases[12]['result']['volume_commit_errors'] == 0
assert cases[13]['result']['refused'] and not any(e[0] == 'spawn' for e in cases[13]['events'])

def rows():
    return [{'step': s, 'eval': {'correct': 4 if s < 1500 else 12, 'total': 256,
                                'query_empty_read_weight': 0.3}}
            for s in range(0, 1501, 100)]

bad_summaries = []
for name in ['duplicate final eval', 'final total 1 with correct 12',
             'derange total 1 with correct 6', 'NaN absent weight', 'negative derange correct']:
    rr, der = rows(), {'correct': 6, 'total': 256}
    if name == 'duplicate final eval':
        rr[-1]['eval']['correct'] = 4
        rr.append({'step': 1500, 'eval': {'correct': 12, 'total': 256, 'query_empty_read_weight': 0.3}})
    elif name == 'final total 1 with correct 12':
        rr[-1]['eval']['total'] = 1
    elif name == 'derange total 1 with correct 6':
        der['total'] = 1
    elif name == 'NaN absent weight':
        rr[-1]['eval']['query_empty_read_weight'] = float('nan')
    elif name == 'negative derange correct':
        der['correct'] = -1
    summary = B.summarize(rr, der)
    bad_summaries.append({'case': name, 'status': summary['status'], 'memory_used': summary.get('memory_used'),
                          'why': summary.get('why')})

extra_validation = []
for name in ['accuracy disagrees with correct count', 'episode count 1', 'NaN fill measure', 'NaN derange weight']:
    rr, der = rows(), {'correct': 6, 'total': 256}
    if name == 'accuracy disagrees with correct count':
        rr[-1]['eval']['accuracy'] = 0.0
    elif name == 'episode count 1':
        rr[-1]['eval']['episodes'] = 1
    elif name == 'NaN fill measure':
        rr[-1]['eval']['query_fill_support_cells_mean'] = float('nan')
    else:
        der['query_empty_read_weight'] = float('nan')
    summary = B.summarize(rr, der)
    extra_validation.append({'case': name, 'status': summary['status'], 'memory_used': summary.get('memory_used')})

pcfg = B.PilotConfig(arm='learned', readout='taskhead', n_bindings=4, n_queries=2,
                    filler_len=4, batch=4, eval_batches=1, seed=0, steps=4,
                    eval_every=2, sgm=dict(B.FILL))
with tempfile.TemporaryDirectory(prefix='codex-b2-preservation-mock-') as td:
    out = pathlib.Path(td) / 'B2'
    identity = B.run_identity(pcfg, None)
    B.prepare_out(out, pcfg, identity)
    evidence = out / 'routing_telemetry.jsonl'
    evidence.write_text('{"step": 10, "partial": true}\n')
    out.with_name('B2.starts.jsonl').write_text('{"start":1}\n')
    B.prepare_out(out, pcfg, identity)
    preserved_without_checkpoint = (out.with_name('B2.archive') / 'start-2' / evidence.name).read_text() == '{"step": 10, "partial": true}\n'
    (out / 'resume.pt').write_bytes(b'foreign fake checkpoint')
    foreign = {'pilot_config': asdict(pcfg), 'step': 2, 'source_hash': 'unrelated-source',
               'campaign': 'unrelated-campaign'}
    with patch.object(B, 'load', lambda p: foreign):
        try:
            B.prepare_out(out, pcfg, identity)
            foreign_refused = False
        except SystemExit:
            foreign_refused = True

with tempfile.TemporaryDirectory(prefix='codex-b2-resume-archive-mock-') as td:
    out = pathlib.Path(td) / 'B2'
    identity = B.run_identity(pcfg, None)
    B.prepare_out(out, pcfg, identity)
    evidence = out / 'routing_telemetry.jsonl'
    evidence.write_text('{"post_checkpoint_partial": true}\n')
    (out / 'resume.pt').write_bytes(b'owned fake checkpoint')
    out.with_name('B2.starts.jsonl').write_text('{"start":1}\n')
    state = {**foreign, 'b2_identity': identity, 'telemetry': [{'step': 0, 'loss': 1.0}]}
    def fake_train(*args, **kw):
        kw['log']({'step': 2, 'loss': 2.0})
        raise RuntimeError('stop mocked trainer after opening and rewriting telemetry')
    with patch.object(B, 'load', lambda p: state), patch.object(B, 'train', fake_train):
        try:
            B.run_b2(pcfg, out, {})
        except RuntimeError:
            pass
    post_checkpoint_partial_preserved = 'post_checkpoint_partial' in (out.with_name('B2.archive') / 'start-2' / evidence.name).read_text()

assert preserved_without_checkpoint and foreign_refused and post_checkpoint_partial_preserved
assert all(x['status'] == 'INVALID' for x in bad_summaries)

tail = sum(math.comb(256, k) * (1/64)**k * (63/64)**(256-k) for k in range(12, 257))
result = {'candidate': (REPORT / 'candidate-sha.txt').read_text().strip(), 'worker_cases': cases,
          'original_malformed_results': bad_summaries, 'additional_validation_cases': extra_validation,
          'partial_telemetry_preserved_without_checkpoint': preserved_without_checkpoint,
          'post_checkpoint_partial_telemetry_preserved_on_resume': post_checkpoint_partial_preserved,
          'same_config_foreign_checkpoint_refused': foreign_refused}
(REPORT / 'independent-worker-checks.json').write_text(json.dumps(result, indent=2, allow_nan=False)+'\n')
print(json.dumps({'worker_cases': len(cases), 'watchdog_failure_leaves_child_running': cases[3]['child_still_running'],
                  'original_bad_results_now_INVALID': len(bad_summaries),
                  'partial_telemetry_preserved': preserved_without_checkpoint and post_checkpoint_partial_preserved,
                  'foreign_checkpoint_refused': foreign_refused,
                  'process_exit_race_skips_child_guard_cancel': True,
                  'expired_start_budget_still_spawns': True,
                  'initial_commit_failure_unreported': True}, indent=2))

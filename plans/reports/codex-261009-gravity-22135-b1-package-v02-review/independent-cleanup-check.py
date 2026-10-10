"""CPU-only fake-clock cleanup audit; no subprocess/cloud/model execution."""
import os
os.environ['CUDA_VISIBLE_DEVICES'] = ''
import ast
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT, PREVIOUS = Path(sys.argv[1]), Path(sys.argv[2])
sys.path.insert(0, str(ROOT))
RUNNER = 'modal-runners/modal-m4-sgm-p2p5-b1-occupied-fill-retention-screen-runner.py'


def load(rel, name):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


R = load(RUNNER, 'b1_runner')
CP = load(R.CONTROL_LOGIC_FILE, 'cp')


def node(root, name):
    tree = ast.parse((root / RUNNER).read_text())
    return ast.dump(next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name), include_attributes=False)


assert node(ROOT, 'run_arm_remote') == node(PREVIOUS, 'run_arm_remote')
assert node(ROOT, 'main') == node(PREVIOUS, 'main')
assert R.CLEANUP_S == R.STOP_ALLOWANCE_S == 300


def case(mode):
    elapsed, calls, app_queries = [0.0], [], [0]

    def run(cmd, timeout, **kwargs):
        before = elapsed[0]
        assert 1 < timeout <= min(60, R.CLEANUP_S - before)
        assert cmd[:3] == [sys.executable, '-m', 'modal']
        calls.append({'args': cmd[3:], 'start_s': before, 'timeout_s': timeout})
        if mode == 'all_cli_hang':
            elapsed[0] += timeout
            raise subprocess.TimeoutExpired(cmd, timeout)
        is_stop, is_app = cmd[3:5] == ['app', 'stop'], cmd[3:5] == ['app', 'list']
        if mode == 'app_consumes_remaining_time' and not is_stop and not is_app:
            elapsed[0] += min(timeout, 35.0 if app_queries[0] == 1 else 5.0)
        elif mode in ('slow_running', 'app_consumes_remaining_time'):
            elapsed[0] += timeout
        else:
            elapsed[0] += min(2.0, timeout)
        if is_stop:
            return subprocess.CompletedProcess(cmd, 1 if mode == 'already_stopped' else 0, '', '')
        if is_app:
            app_queries[0] += 1
            if mode == 'malformed_app_json':
                return subprocess.CompletedProcess(cmd, 0, '{malformed', '')
            stopped = mode not in ('slow_running',)
            tasks = 1 if mode in ('lagging_tasks', 'app_consumes_remaining_time') and app_queries[0] < 3 else 0
            rows = [{'app_id': 'ap-AUDIT', 'state': 'stopped' if stopped else 'running', 'tasks': tasks}]
        else:
            rows = [{'app_id': 'ap-AUDIT'}] if mode == 'container_still_listed' else []
        return subprocess.CompletedProcess(cmd, 0, json.dumps(rows), '')

    with tempfile.TemporaryDirectory(prefix='codex-b1-cleanup-') as temp:
        dest = Path(temp)
        if mode != 'missing_app_id':
            (dest / 'run.json').write_text(json.dumps({'app_id': 'ap-AUDIT'}))
        result = R.cleanup_verify(dest, cp=CP, run=run, sleep=lambda s: elapsed.__setitem__(0, elapsed[0]+s), clock=lambda: elapsed[0])
        assert json.loads((dest / 'cleanup.json').read_text()) == result
    assert elapsed[0] <= R.CLEANUP_S
    verified = mode in ('lagging_tasks', 'already_stopped')
    if mode == 'missing_app_id':
        assert result['status'].startswith('unresolved') and not calls
    else:
        assert (result['status'] == 'stopped_verified') == verified
    return {'case': mode, 'status': result['status'], 'elapsed_s': elapsed[0], 'checks': len(result['checks']), 'calls': calls}


cases = [case(mode) for mode in ('all_cli_hang', 'slow_running', 'app_consumes_remaining_time',
         'malformed_app_json', 'container_still_listed', 'lagging_tasks', 'already_stopped', 'missing_app_id')]
from memsub.sgm.synthetic_pilot_run import source_tree_sha256
assert R.local_memsub_sha256() == source_tree_sha256(ROOT / 'memsub') == R.EXPECT_MEMSUB_SHA256
print(json.dumps({'device': 'cpu', 'gpu_or_cloud_operations': False, 'memsub_sha256': R.EXPECT_MEMSUB_SHA256,
 'remote_worker_ast_unchanged': True, 'local_entrypoint_ast_unchanged': True,
 'cleanup_cases': cases, 'ledger': R.ledger()}, indent=2))

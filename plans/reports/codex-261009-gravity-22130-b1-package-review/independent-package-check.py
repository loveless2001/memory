"""CPU-only B1 audit: mocked remote control paths and a simulated cleanup budget.

No model load, network operation, Modal launch, real sleeper, or GPU access.
"""
import os
os.environ['CUDA_VISIBLE_DEVICES'] = ''
import ast
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

ROOT = Path(sys.argv[1])
sys.path.insert(0, str(ROOT))


def load(rel, name):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


R = load('modal-runners/modal-m4-sgm-p2p5-b1-occupied-fill-retention-screen-runner.py', 'b1')
T = load('scripts/sgm-p2p5-b1-occupied-fill-retention-screen-train.py', 'b1_train')
CP = load(R.CONTROL_LOGIC_FILE, 'control_plane')


def normalized_worker(rel):
    tree = ast.parse((ROOT / rel).read_text())
    fn = copy.deepcopy(next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'run_arm_remote'))
    class Normalize(ast.NodeTransformer):
        def visit_Assign(self, node):
            if len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) and node.targets[0].id in ('cmd', 'out'):
                node.value = ast.Constant('EXPECTED_B1_COMMAND_OR_TEMP_PREFIX_CHANGE')
            return node
    return ast.dump(Normalize().visit(fn), include_attributes=False)


assert normalized_worker('modal-runners/modal-m4-sgm-p2p5-stage-a-read-escape-blocker-runner.py') == normalized_worker('modal-runners/modal-m4-sgm-p2p5-b1-occupied-fill-retention-screen-runner.py')


class FakeDict:
    def __init__(self, deadline):
        self.d = {'deadline': deadline}
    def put(self, k, v, skip_if_exists=False):
        if skip_if_exists and k in self.d:
            return False
        self.d[k] = v
        return True
    def get(self, k):
        return self.d.get(k)


clock = {'t': 0.0}
starts = FakeDict(1000.0)
children, guards, cancelled = [], [], []
class Child:
    pid, returncode = 999999, 0
    def __init__(self, cmd, **kwargs):
        self.cmd = cmd
        children.append({'cmd': cmd, 'kwargs': kwargs})
    def communicate(self, timeout=None):
        children[-1]['timeout'] = timeout
        dest = Path(self.cmd[self.cmd.index('--out') + 1])
        dest.mkdir()
        (dest / 'b1_result.json').write_text(json.dumps({'status': 'valid', 'band_at_100': 'partial'}))
        return '', ''


def guard(target, seconds):
    token = (target, seconds, len(guards))
    guards.append(token)
    return token


raw = R.run_arm_remote.get_raw_f()
with tempfile.TemporaryDirectory(prefix='codex-b1-mock-') as temp:
    mkdtemp = tempfile.mkdtemp
    with patch.object(R.modal.Dict, 'from_name', return_value=starts), patch.object(R, '_versions_ok', return_value={'ok': True, 'got': R.EXPECT_VERSIONS}), patch.object(R.time, 'time', side_effect=lambda: clock['t']), patch.object(R, 'deadline_killer', side_effect=guard), patch.object(R, 'cancel_killer', side_effect=cancelled.append), patch.object(R.subprocess, 'Popen', side_effect=Child), patch.object(R.tempfile, 'mkdtemp', side_effect=lambda prefix: mkdtemp(prefix=prefix, dir=temp)):
        result = raw('B1', 1000.0)
        assert result['returncode'] == 0 and children[-1]['timeout'] == 910.0
        assert children[-1]['kwargs']['start_new_session'] is True
        assert guards[0][0] == str(os.getpid()) and guards[1][0] == '-999999'
        assert set(guards) == set(cancelled)
        assert 'refused' in raw('B1', 1000.0) and len(children) == 1
        starts.d = {'deadline': 1000.0}
        def late_setup():
            clock['t'] = 1001.0
            return {'ok': True, 'got': R.EXPECT_VERSIONS}
        with patch.object(R, '_versions_ok', side_effect=late_setup):
            assert 'refused' in raw('B1', 1000.0) and len(children) == 1
        assert set(guards) == set(cancelled)
        clock['t'], starts.d = 0.0, {'deadline': 1000.0}
        with patch.object(R, '_versions_ok', side_effect=RuntimeError('simulated setup failure')):
            try:
                raw('B1', 1000.0)
                raise AssertionError('exception expected')
            except RuntimeError:
                pass
        assert set(guards) == set(cancelled)
        clock['t'] = 1000.0
        count = len(guards)
        assert 'refused' in raw('B1', 1000.0) and len(guards) == count


# Exercise the actual cleanup loop and actual CP.verify_stopped using a fake clock.
# Each successful CLI query returns just before its 60 s timeout; the app stays running.
elapsed, queries = [0.0], []
def cli(args):
    elapsed[0] += 60.0
    queries.append(args)
    return ([{'app_id': 'ap-AUDIT', 'state': 'running', 'tasks': 1}]
            if args == ['app', 'list'] else [{'app_id': 'ap-AUDIT'}])
def stop(_):
    elapsed[0] += 60.0
    return None
with tempfile.TemporaryDirectory(prefix='codex-b1-cleanup-mock-') as temp:
    dest = Path(temp)
    (dest / 'run.json').write_text(json.dumps({'app_id': 'ap-AUDIT'}))
    with patch.object(CP, 'modal_cli_json', side_effect=cli):
        cleanup = R.cleanup_verify(dest, cp=CP, stopper=stop, sleep=lambda s: elapsed.__setitem__(0, elapsed[0]+s))
assert cleanup['status'] == 'shutdown_unresolved' and elapsed[0] == 600.0
assert elapsed[0] > R.STOP_ALLOWANCE_S

rows = [{'step': s, 'eval': {'query_empty_read_weight': v}} for s, v in zip(T.STAGE_A.EVAL_STEPS, (.05,.95,.95,.1,.1))]
endpoint = T.summarize(rows)
assert endpoint['band_at_100'] == 'kept' and endpoint['kept_through_100'] is False

from memsub.sgm.synthetic_pilot_run import source_tree_sha256
source = source_tree_sha256(ROOT/'memsub')
assert source == R.EXPECT_MEMSUB_SHA256
print(json.dumps({'memsub_sha256': source, 'normalized_worker_controls_match_stage_a': True,
 'mocked_b1_success_and_second_start_refusal': True, 'mocked_late_setup_refuses_child': True,
 'mocked_exception_cancels_guard': True, 'mocked_expired_entry_arms_no_guard': True,
 'simulated_cleanup_seconds': elapsed[0], 'ledger_stop_allowance_seconds': R.STOP_ALLOWANCE_S,
 'simulated_cleanup_status': cleanup['status'], 'cleanup_cli_queries': queries,
 'endpoint_kept_after_earlier_escape': {'band_at_100': endpoint['band_at_100'], 'kept_through_100': endpoint['kept_through_100']},
 'ledger': R.ledger(), 'reservation_with_600s_cleanup': (R.OUTER_S + elapsed[0]) * R.ledger()['rate_usd_s'],
 'device': 'cpu', 'gpu_or_network_operations': False}, indent=2))

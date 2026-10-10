"""Exercise the real wrapper with fake GPU CLI/timeout in isolated temporary roots."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
P = Path('plans/261009-0030-m4-sgm-p2p5-taskhead-read-escape-blocker-screen')
WRAPPER = P / 'geometry-wait-then-run-once.sh'


def exe(path, text):
    path.write_text(text)
    path.chmod(0o755)


results = []
for case, expected_rc, launch in [
    ('apps_error', 4, False), ('memory_error', 4, False),
    ('empty_memory', 4, False), ('bad_memory', 4, False), ('multi_memory', 4, False),
    ('bad_apps', 4, False), ('busy_apps', 3, False), ('busy_memory', 3, False),
    ('idle', 0, True), ('idle_299', 0, True),
]:
    with tempfile.TemporaryDirectory(prefix='codex-gpu-gate-') as tmp:
        root = Path(tmp)
        (root / P).mkdir(parents=True)
        (root / 'bin').mkdir()
        wrapper = root / WRAPPER
        shutil.copyfile(ROOT / WRAPPER, wrapper)
        exe(root / 'bin/sleep', '#!/bin/sh\nexit 0\n')
        exe(root / 'bin/git', '#!/bin/sh\necho fixture-head\n')
        exe(root / 'bin/timeout', '#!/bin/sh\nprintf "%s\\n" "$@" > launch-argv.txt\nexit 17\n')
        exe(root / 'bin/nvidia-smi', '''#!/bin/sh
case "$1" in
--query-compute-apps=pid)
  case "$GPU_CASE" in
    apps_error) echo "CLI failed" >&2; exit 9;;
    bad_apps) echo N/A;;
    busy_apps) echo ' 1234 ';;
  esac;;
--query-gpu=memory.used)
  case "$GPU_CASE" in
    memory_error) echo "CLI failed" >&2; exit 9;;
    empty_memory) :;;
    bad_memory) echo N/A;;
    multi_memory) printf '0\\n0\\n';;
    busy_memory) echo 300;;
    idle_299) echo 299;;
    *) echo 0;;
  esac;;
*) exit 99;;
esac
''')
        env = {**os.environ, 'GPU_CASE': case, 'PATH': str(root / 'bin') + os.pathsep + os.environ['PATH']}
        r = subprocess.run(['bash', str(wrapper), '99999999'], capture_output=True, text=True, env=env, timeout=10)
        assert r.returncode == expected_rc, (case, r.returncode, r.stderr)
        assert (root / 'launch-argv.txt').exists() == launch, case
        gate = (root / P / 'geometry-run-v1.gate.txt').read_text()
        if launch:
            args = (root / 'launch-argv.txt').read_text().splitlines()
            assert args == ['--signal=KILL', '3600', '.venv-gpu/bin/python',
                            'scripts/sgm-p2p5-taskhead-dead-start-address-diagnosis.py',
                            '--index', str(P / 'geometry-index-v1.json'), '--out', str(P / 'geometry-run-v1')]
            assert (root / P / 'geometry-run-v1.exit.txt').read_text().strip() == '17'
            assert (root / P / 'geometry-run-v1.cleanup.txt').exists()
        else:
            assert 'NOT launched' in gate and not (root / P / 'geometry-run-v1.exit.txt').exists()
        again = subprocess.run(['bash', str(wrapper), '99999999'], capture_output=True, text=True, env=env, timeout=10)
        assert again.returncode == 2
        results.append({'case': case, 'returncode': r.returncode, 'launch_invocations': int(launch), 'repeat_refused': True, 'gate': gate})

result = {'wrapper_sha256': hashlib.sha256((ROOT / WRAPPER).read_bytes()).hexdigest(),
          'cases_passed': len(results), 'cases': results, 'actual_model_runs': 0, 'paid_calls': 0}
(HERE / 'checks.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps({'cases_passed': len(results), 'wrapper_sha256': result['wrapper_sha256'], 'actual_model_runs': 0}))

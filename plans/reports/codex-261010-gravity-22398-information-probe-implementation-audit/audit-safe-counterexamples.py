"""Tiny model-free audit checks against the immutable c3c52f9 source snapshot.

Never invokes main(), capture, model loading, real profiling or a mutation runner.
"""
from pathlib import Path
import importlib.util
import json
import re
import subprocess
import types
import numpy as np

HERE = Path(__file__).resolve().parent
SRC = HERE / 'sources-c3c52f9'

def load(p, name):
    s = importlib.util.spec_from_file_location(name, p)
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m

R = load(SRC / 'scripts/sgm-p2p5-previous-key-probe-run-s1-s2-full.py', 'audited_runner')
M = load(SRC / 'scripts/sgm-p2p5-previous-key-probe-ridge-retrieval-readings.py', 'audited_math')
result = {'scope': 'model-free function calls and harmless shell false command', 'model_loads': 0}
gate = []
for wall in (0, 20000):
    p = HERE / f'counterexample-admission-{wall}.json'
    p.write_text(json.dumps({'admit': True, 'wall_s': wall}) + '\n')
    args = types.SimpleNamespace(mode='full', admission=str(p), wall_s=wall)
    try:
        R.check_wall(args)
    except Exception as e:
        gate.append({'wall_s': wall, 'accepted': False, 'error': str(e)})
    else:
        gate.append({'wall_s': wall, 'accepted': True})
result['full_wall_gate'] = gate

md = next((SRC / 'plans').rglob('proposal-v0.3.md')).read_text()
line = next(l for l in md.splitlines() if 'probe-run-v1.exit' in l)
token = re.search(r'echo (\\+\$\?)', line).group(1)
# Only the restricted backslash/$? token enters this fixed harmless shell example.
outer = 'inner="false\necho ' + token + '"\nprintf "expanded inner command: %s\\n" "$inner"\nbash -c "$inner"\n'
r = subprocess.run(['bash', '-c', outer], text=True, capture_output=True, timeout=5)
result['quoted_full_exit_receipt'] = {'backslash_count': token.count('\\'), 'stdout': r.stdout, 'stderr': r.stderr, 'expected_false_status': 1}

try:
    ranks = M.retrieval_ranks(np.array([[np.nan, 1.0]]), np.array([[[1.0, 0.0], [0.0, 1.0]]]), np.array([0]), np.array([0]))
except Exception as e:
    result['nonfinite_prediction'] = {'rejected': True, 'error': str(e)}
else:
    result['nonfinite_prediction'] = {'rejected': False, 'ranks': ranks.tolist()}

(HERE / 'counterexample-results.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result, indent=2))

"""Check the actual c3c52f9 capture hook with fake project inputs, never a backbone."""
from pathlib import Path
import importlib.util
import json
import sys
import types
import numpy as np
import torch

HERE = Path(__file__).resolve().parent
ROOT = Path('/home/lenovo/projects/memory')
sys.path.insert(0, str(ROOT))
path = HERE / 'sources-c3c52f9/scripts/sgm-p2p5-previous-key-probe-capture-qwen-adapter-inputs.py'
spec = importlib.util.spec_from_file_location('capture_under_review', path)
C = importlib.util.module_from_spec(spec)
spec.loader.exec_module(C)

def forbidden(*args, **kwargs):
    raise RuntimeError('MODEL LOAD FORBIDDEN IN AUDIT')

C.load_model = forbidden
C.build = forbidden
layers = (6, 13, 20, 27)
adapter = {str(l): types.SimpleNamespace(project=lambda x: x) for l in layers}
runtime = types.SimpleNamespace(adapters=adapter)
orig = {k: a.project for k, a in adapter.items()}

def fake_ingest(backend, eb, arm, traces, writes, n):
    for t in range(eb.source.shape[1]):
        x = torch.stack([eb.source[:, t].float(), torch.full((len(eb.source),), float(t))], -1).unsqueeze(1)
        for a in adapter.values():
            a.project(x)

C.ingest = fake_ingest
pcfg = types.SimpleNamespace(arm='learned')
out = C.capture(runtime, None, pcfg, 'train', 3, 777, batch=2, log=lambda x: None)
checks = {}
for l in layers:
    checks[f'L{l}_ids'] = bool(np.array_equal(out[f'zk_L{l}'][..., 0], out['key_ids']) and np.array_equal(out[f'zv_L{l}'][..., 0], out['value_ids']))
    checks[f'L{l}_positions'] = bool(np.array_equal(out[f'zk_L{l}'][..., 1], np.tile(np.arange(4, 68, 2), (3, 1))) and np.array_equal(out[f'zv_L{l}'][..., 1], np.tile(np.arange(5, 68, 2), (3, 1))))
checks['hooks_restored_after_success'] = all(a.project is orig[k] for k, a in adapter.items())

def bad_ingest(backend, eb, arm, traces, writes, n):
    for t in range(eb.source.shape[1]):
        x = torch.zeros(len(eb.source), 1, 2)
        if t == 5:
            x[..., 0] = float('nan')
        for a in adapter.values():
            a.project(x)

C.ingest = bad_ingest
try:
    C.capture(runtime, None, pcfg, 'train', 1, 778, batch=1, log=lambda x: None)
except RuntimeError as e:
    checks['nonfinite_capture_refused'] = 'nonfinite adapter input' in str(e)
else:
    checks['nonfinite_capture_refused'] = False
checks['hooks_restored_after_error'] = all(a.project is orig[k] for k, a in adapter.items())
if not all(checks.values()):
    raise RuntimeError(checks)
result = {'status': 'PASS', 'model_loads': 0, 'backbone_forwards': 0, 'scope': 'fake input tensors through actual capture wrapper', 'checks': checks}
(HERE / 'capture-hook-checks.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result, indent=2))

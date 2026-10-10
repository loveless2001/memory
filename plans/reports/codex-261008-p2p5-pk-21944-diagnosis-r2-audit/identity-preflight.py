"""Run the actual identity checks in the intended venv; no model build/forward."""
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
script = ROOT / 'scripts/sgm-p2p5-taskhead-dead-start-address-diagnosis.py'
spec = importlib.util.spec_from_file_location('diagnosis_r2_preflight', script)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
index = json.loads((ROOT / 'plans/reports/claude-261008-2350-p2p5-taskhead-dead-start-address-diagnosis/inputs-index.json').read_text())
identity = m.check_run_identity(index)
(OUT / 'identity-preflight.json').write_text(json.dumps({'identity': identity, 'model_forward': False}, indent=2) + '\n')
print(json.dumps(identity, indent=2))

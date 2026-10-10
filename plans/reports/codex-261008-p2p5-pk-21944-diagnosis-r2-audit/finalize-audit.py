"""Finalize the independent r2 review; no model evaluation or training."""
import hashlib
import json
import subprocess
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
BASE = ROOT / 'plans/reports/claude-261008-2350-p2p5-taskhead-dead-start-address-diagnosis'
SCRIPT = 'scripts/sgm-p2p5-taskhead-dead-start-address-diagnosis.py'
INDEX = str((BASE / 'inputs-index.json').relative_to(ROOT))
sha = lambda b: hashlib.sha256(b).hexdigest()
expected = {
    SCRIPT: 'e9131a62ac57cca62915ae233914315412e302bf5ab954351f20544578311ea7',
    INDEX: '832f545ec0dd19e953427ce5949c22f7093923a03cdb9353246070cafdda10fb',
}
bindings = {}
for name, wanted in expected.items():
    current = sha((ROOT / name).read_bytes())
    committed = sha(subprocess.check_output(['git', 'show', f'167f3c3:{name}'], cwd=ROOT))
    assert current == committed == wanted, (name, current, committed)
    bindings[name] = current
assert not subprocess.check_output(['git', 'status', '--short', '--untracked-files=no'], cwd=ROOT).strip()
tests = (OUT / 'focused-tests.log').read_text()
assert '14 passed' in tests
package = json.loads((OUT / 'package-checks.json').read_text())
identity = json.loads((OUT / 'identity-preflight.json').read_text())
result = {
    'verdict': 'CLEAR_ONE_EXISTING_AUTHORIZED_LOCAL_INVOCATION',
    'reviewed_commit': '167f3c3',
    'bindings': bindings,
    'package_manifest_sha256': sha((BASE / 'SHA256SUMS-package-r2.txt').read_bytes()),
    'independent_tests': {'passed': 14, 'seconds': 10.05, 'environment': '.venv CPU'},
    'package_files_hash_verified': len(package['package_files_checked']),
    'input_entries_verified': len(package['input_checks']),
    'run_identity_preflight': identity,
    'tracked_worktree_clean': True,
    'independent_qwen_forward_or_backward': False,
    'gpu_fit_verified': False,
    'scope': {
        'cost': '$0 local only', 'invocations': 1, 'outer_timeout_seconds': 3600,
        'geometry_entries': 12, 'geometry_episodes_per_entry': 64,
        'geometry_population': 'heldout seed 4242, four batches of 16, N32 Q4 filler40',
        'm4_entries': 2, 'm4_episodes': 2, 'm4_order': 'last',
        'optimizer_steps': 0, 'first_error_stops': True,
        'automatic_retry': False, 'automatic_cpu_fallback': False,
    },
}
(OUT / 'verdict.json').write_text(json.dumps(result, indent=2) + '\n')
(OUT / 'review.txt').write_text('''Independent r2 implementation review (#gravity 21944)

Verdict: CLEAR the single already-authorized $0 local diagnosis at 167f3c3.
This clears implementation and provenance checks, not a scientific conclusion.

Evidence
- Independently reran the 14 focused CPU tests: 14 passed in 10.05 seconds.
- All 14 frozen package files and all 14 indexed inputs pass hash checks.
  Manifests, telemetry, final parameter bindings, step100 acknowledgement links,
  intended devices and per-entry dev-eval steps agree. Script and index equal
  both the advertised hashes and committed 167f3c3 bytes. Tracked tree is clean.
- The actual .venv-gpu identity preflight passes: bound memsub source,
  torch 2.7.1+cu126, transformers 4.55.2, pinned Qwen revision and all three
  model-file hashes. Device inventory is RTX 3060 Laptop GPU.
- Retained r2 toy end-to-end artifacts are hash-bound to the reviewed script
  and internally consistent. They were inspected, not independently rerun.

Previous hold points closed
1. Oracle query addresses now follow query_logits wiring. The CPU oracle
   geometry and backward tests exercise the formerly failing path.
2. Dev replay requires exactly one finite logged eval; missing, duplicate,
   malformed, non-finite and discrepant records fail. Telemetry is hash-bound.
   Accuracy is explicitly labelled logged and not recomputed.
3. All-absent detection checks presence at every positive-weight cell, not a
   near-one mass threshold. The occupied 5e-7 counterexample passes the test.
   Gradient language distinguishes read paths from head-bias gradients.
4. Source/environment/device/FP32/TF32 and checkpoint config/step checks are
   enforced. Setup and entry exceptions retain ERROR.txt and stop.

Execution scope retained
One shared timeout --signal=KILL 3600 process group covers all model loads,
12 no-grad geometry entries (four batches of 16 fixed dev episodes each),
then two M4 initialization backward entries (first two dev episodes), output
and cleanup. No optimizer, reserved-seed evaluation, Modal, retry or CPU
fallback. On OOM/error/timeout stop and retain partials. Preserve exact argv,
stdout/stderr, external exit status, PID/process-group evidence and terminal
cleanup evidence. Do not overwrite prior retained artifacts.

Limits
No independent Qwen forward/backward ran during this review. GPU fit and
runtime are unproved; a first-entry failure is a retained bounded outcome.
Geometry is descriptive; alignment is not a causal explanation. Dev gradients
at reconstructed initialization do not establish historical training gradients.
Logged replay checks absent-read mass and occupancy, not accuracy.

Audit-reader correction
The first metadata-only reader assumed every old toy manifest included an
explicit backbone field and raised KeyError. The corrected reader applies the
runtime PilotConfig default of tiny. Both logs are retained; this was an audit
reader assumption and caused no model work or changes to the reviewed package.
''')
files = sorted(p for p in OUT.iterdir() if p.is_file() and p.name != 'SHA256SUMS.txt')
(OUT / 'SHA256SUMS.txt').write_text(''.join(f'{sha(p.read_bytes())}  {p.name}\n' for p in files))
print(json.dumps({'verdict': result['verdict'], 'evidence_files': len(files),
                  'package_manifest_sha256': result['package_manifest_sha256']}))

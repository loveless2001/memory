"""Refresh report r3 checksums while verifying every run artifact is unchanged."""
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
BASE = ROOT / 'plans/reports/claude-261008-2350-p2p5-taskhead-dead-start-address-diagnosis'
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
old = (OUT / 'r2-SHA256SUMS-run-v1.txt').read_text()
checks, changed, lines = [], [], []
for line in old.splitlines():
    previous, name = line.split('  ', 1)
    path = (BASE / name).resolve()
    actual = sha(path)
    if actual != previous: changed.append(path)
    checks.append({'file': str(path.relative_to(ROOT)), 'sha256': actual,
                   'unchanged_from_r2': actual == previous})
    lines.append(f'{actual}  {name}\n')
assert len(checks) == 22 and changed == [BASE / 'diagnosis-report.md']
(BASE / 'SHA256SUMS-run-v1.txt').write_text(''.join(lines))
assert all(sha(ROOT / c['file']) == c['sha256'] for c in checks)
text = (BASE / 'diagnosis-report.md').read_text()
for obsolete in ['≥.97', 'The final state equals or exceeds', 'Those norms are as large',
                 'An address-MLP update therefore moves', "would not allow that", 'run would answer it']:
    assert obsolete not in text, obsolete
assert 'L27 alpha and out_proj have no gradient' in text
assert 'not by itself distinguish H1 from H2' in text
for p in [BASE / 'diagnosis-report.md', BASE / 'SHA256SUMS-run-v1.txt']:
    shutil.copyfile(p, OUT / ('r3-' + p.name))
diff = subprocess.check_output(['git', 'diff', '0ddf4dc', '--',
    str((BASE / 'diagnosis-report.md').relative_to(ROOT)),
    str((BASE / 'SHA256SUMS-run-v1.txt').relative_to(ROOT))], cwd=ROOT, text=True)
(OUT / 'r2-to-r3.patch').write_text(diff)
result = {'verdict': 'ACCEPT_CORRECTED_DESCRIPTIVE_DIAGNOSIS', 'report_revision': 'r3',
          'base_commit': '0ddf4dc', 'package_files_checked': 22,
          'unchanged_package_artifacts': 21, 'changed_package_file': str(changed[0].relative_to(ROOT)),
          'report_sha256': sha(BASE / 'diagnosis-report.md'),
          'package_manifest_sha256': sha(BASE / 'SHA256SUMS-run-v1.txt'),
          'new_model_execution': False, 'checks': checks}
(OUT / 'verdict.json').write_text(json.dumps(result, indent=2) + '\n')
(OUT / 'review.txt').write_text('''Final report review: ACCEPT corrected descriptive diagnosis.
Verified r2 at 0ddf4dc and preserved its original report and checksum bytes.
Applied r3 prose corrections: explicit final-layer gradient exceptions, rounded
absent-weight bounds, persistence without a monotonic claim, finite early-gradient
interval, and conditional hypotheses/intervention proposals. Head-bias-only
logits require all taskhead read features to be zero. Replay checks support
consistency; manifests and parameter hashes bind the loaded inputs separately.

Recomputed all 22 package checksums. Only diagnosis-report.md differs among
the package files; 21 run/provenance/summary artifacts match r2 exactly. Updated
SHA256SUMS-run-v1.txt and preserved both revisions plus the exact patch here.
No model execution, optimizer update or new experiment was performed.

Accepted observation: on the fixed dev population, over 99% of read weight is
absent by step100 in both probe seeds; severe separation persists at the final
snapshot. The causal driver, permanence of the state and effective remedies
remain unproven. No new training or retry is cleared by this report review.
The r3 report and checksum are ready for the owner's commit/refreeze.
''')
files = sorted(p for p in OUT.iterdir() if p.is_file() and p.name != 'SHA256SUMS.txt')
(OUT / 'SHA256SUMS.txt').write_text(''.join(f'{sha(p)}  {p.name}\n' for p in files))
print(json.dumps({k: v for k, v in result.items() if k != 'checks'}, indent=2))

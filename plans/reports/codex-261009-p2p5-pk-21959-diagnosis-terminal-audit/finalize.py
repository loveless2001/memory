"""Freeze the terminal review and verify the owner's 22-file terminal package."""
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
BASE = ROOT / 'plans/reports/claude-261008-2350-p2p5-taskhead-dead-start-address-diagnosis'
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
manifest = BASE / 'SHA256SUMS-run-v1.txt'
checks = []
for line in manifest.read_text().splitlines():
    wanted, name = line.split('  ', 1)
    path = (BASE / name).resolve()
    assert sha(path) == wanted, name
    checks.append({'file': str(path.relative_to(ROOT)), 'sha256': wanted})
assert len(checks) == 22
report = BASE / 'diagnosis-report.md'
assert hashlib.sha256(subprocess.check_output(['git', 'show',
    '813087d:' + str(report.relative_to(ROOT))], cwd=ROOT)).hexdigest() == sha(report)
for p in [report, manifest, BASE / 'run-v1.cleanup.txt']:
    shutil.copyfile(p, OUT / 'frozen-terminal-artifacts' / p.name)
(OUT / 'peer-package-checks.json').write_text(json.dumps({
    'commit': '813087d', 'files': checks, 'manifest_sha256': sha(manifest),
    'report_sha256': sha(report), 'report_claims_reviewed_separately': True}, indent=2) + '\n')
(OUT / 'review.txt').write_text('''Independent terminal review (#gravity 21959 / 21961-21962)

Run verdict: COMPLETE, EXIT 0, all 14/14 entries present and in frozen order.
12 geometry entries and two initialization-backward entries completed. Internal
run duration is 853 seconds; outer launch-to-exit duration is about 860 seconds,
well inside the single shared 3600-second bound. No independent model work ran.
Known PIDs and PGID are absent; no GPU compute apps and GPU memory is 0 MiB.

Integrity
Script/index and run identity match the cleared r2 package. All reported input
entries, manifests, telemetry and parameter hashes match their frozen bindings.
All numeric output is finite. Independently recomputed absent-read mass and
occupancy versus each of the 12 logged dev evals: maximum absolute differences
1.0446456144563854e-08 and 0, respectively. Logged accuracy was not recomputed.
Owner's 22-file terminal checksums pass, and report bytes match commit 813087d.
Original report is frozen here so later wording corrections remain auditable.

Findings supported by this diagnosis (fixed dev population only)
- At reconstructed initialization, averaged absent weight is 4.67% (seed0)
  and 4.17% (seed1). Exact all-absent fractions are 0% and 0.464%.
  Thus these sampled dev reads are generally not spatially disconnected at init.
- By saved step100, absent weight is 99.281% and 99.137%; exact all-absent
  fractions are 96.582% and 93.335%. Centroid offsets averaged over layers/heads
  rise from 1.46/1.21 to 10.78/9.95 cells. Within-one-cell alignment is zero.
- Final seed0 is exactly all-absent in every measured layer/head/query. Final
  seed1 remains 99.136% absent by weight and 93.701% exactly all-absent.
  Seed1 L20 retains some occupied-cell reads; both seeds are not fully empty.
- Toy final layer1 alignment is 90.820%/80.469%, with absent weights about
  0.0061%/0.0118%. Oracle addresses align by construction, with zero absent mass.
- Reconstructed seed0 M4 reaches every core routing/content adapter group and
  the head. L27/out_proj AND L27/alpha are None, expected for taskhead wiring.
  This tests two dev episodes, not historical first-update training gradients.
- Query q and value k become more similar within their respective populations,
  alongside the spatial separation. This association does not identify a cause.

Interpretation
The proximate failure observed here is an early loss of useful spatial routing:
reads and writes are separated by step100 and mostly remain so at the endpoint.
The existing training logs support early loss/gradient deterioration. This is
stronger evidence than the original guess of an unreachable initialization,
but does not establish why optimization moves the addresses or a proven remedy.

Corrections needed to owner's report and plain-language channel explanation
1. 'Within the first ~10 updates every lookup moved ~10 cells' is not measured.
   Saved geometry is only init/100/final. Step10 loss and gradients are a different
   train population (phase1 filler0) and do not locate the spatial event. Say
   'by step100; training logs suggest deterioration began much earlier.' Some
   address gradients remain nonzero and recur through step100; not all vanish
   permanently by step20-40. Seed0 L13 is 0.00333 at logged step100.
2. An all-absent read has zero local read-path gradient, but a whole training
   state is not proved absorbing. Shared parameters, other episodes/layers,
   momentum and weight decay can still move coordinates. Seed1 is partly occupied.
   Replace 'cannot be left' / 'nothing can pull it back' with a local gradient
   statement and an untested persistence hypothesis.
3. Zero taskhead features yield head-bias-only logits, not necessarily uniform
   logits. Average cross-entropy near ln64 does not prove uniform predictions.
   Near-zero q/k cosine alone does not prove absence of informative read content.
4. Include L27/alpha as well as L27/out_proj in the expected None exception.
   Raw gradient norms across different model dimensions are not a direct measure
   of comparable learning quality.
5. The per-layer seed1 L20 absent weight is 0.9655, so use 'about .97' rather than
   an exact lower bound >=.97. At seed0 step100 tiny stencil overlap persists
   (pooled intersection 0.000732, coupling 5.69e-6); within-one-cell alignment is
   exactly zero. Identify which overlap statistic is being described.
6. A proposed <=100-update test might test a candidate fix; a bundled comparison
   of learning rate, whitening and occupancy constraints would not by itself
   distinguish H1 from H2. No new training/retry is cleared by this diagnosis.

The run and its descriptive outputs are accepted. H1 and H2 remain hypotheses.
The owner can correct/refreeze the report using existing evidence. No rerun is
needed for these wording corrections; a new training test needs its own scope.
''')
files = sorted(p for p in OUT.rglob('*') if p.is_file() and p.name != 'SHA256SUMS.txt')
(OUT / 'SHA256SUMS.txt').write_text(''.join(f'{sha(p)}  {p.relative_to(OUT)}\n' for p in files))
print(json.dumps({'terminal_package_files_verified': len(checks),
                  'independent_evidence_files_hashed': len(files), 'run': 'accepted',
                  'report_wording': 'corrections requested; no new model work required'}))

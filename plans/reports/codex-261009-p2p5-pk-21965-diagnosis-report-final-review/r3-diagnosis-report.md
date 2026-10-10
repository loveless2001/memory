# P2.5 taskhead dead-start address diagnosis: run-v1 report (DESCRIPTIVE), r3

r2 applies codex terminal review 21964: timing qualified to 'by step 100', absorbing not established, head-bias-only logits, L27 alpha+out_proj None, exact all-absent rates. Run artifacts are unchanged.

r3 applies codex follow-up review 21966: consistent gradient exceptions, rounded bounds, persistence wording, and conditional hypotheses and proposed tests. No new measurements.

User go #gravity 21931; scope 21932; codex review 21934/21939; r2 167f3c3 cleared by codex 21947.
$0, local RTX 3060 Laptop. Dev population only: heldout split, seed 4242, 4×16 episodes, filler 40. No training, no optimizer step, no Modal, no reserved seeds.

## Run
- One invocation: `timeout --signal=KILL 3600 .venv-gpu/bin/python scripts/sgm-p2p5-taskhead-dead-start-address-diagnosis.py --index inputs-index.json --out run-v1`.
  - Ran from HEAD 167f3c3, 17:00:42Z to 17:15:03Z. EXIT 0; 14/14 entries.
  - Records: `run-v1.launch.txt`, `run-v1.console.log`, `run-v1.exit.txt`.
- Cleanup (`run-v1.cleanup.txt`): no matching processes, GPU 0 MiB, 0 CUDA apps.
- **All 12 geometry entries reproduced their run's own logged dev eval at that step** (absent-read weight and occupancy within 1e-4; fail-closed check). These checks support consistency with the recorded dev evaluation; manifests and parameter hashes separately bind the configuration and loaded parameters. Accuracy was logged, not recomputed.
- Disclosure: the t+4 s PID snapshot failed to write (R was unset in the shell); the t+12 s snapshot is recorded instead.

## Table: head means per layer (full per-head values in run-v1/*.json; table in run-v1-summary-table.txt)
| entry | layer | absent w | all-absent | read within 1 cell of bound write | read/write centroid offset (cells) | q pairwise cos | cos(q, bound k) |
|---|---|---|---|---|---|---|---|
| Qwen probe s0 init | 6/13/20/27 | .04/.05/.07/.02 | 0 | .17/.24/.16/.22 | 1.6/1.3/1.6/1.4 | .55–.69 | ≈0 (−.04….03) |
| Qwen probe s0 step100 | | 1.00/.97/1.00/1.00 | 1.0/.89/1.0/.98 | 0 | 11.3/10.7/9.6/11.5 | .92–.95 | −.60…−.69 |
| Qwen probe s0 final | | 1.00 all | 1.00 all | 0 | 17.9/12.4/9.6/16.3 | .93–.96 | −.51…−.77 |
| Qwen probe s1 init | | .01/.01/.02/.13 | ≤.02 | .31/.34/.28/.18 | 1.0/1.0/1.1/1.8 | .53–.72 | ≈0 |
| Qwen probe s1 step100 | | 1.00/1.00/.97/1.00 | 1.0/1.0/.77/.96 | 0 | 10.8/9.8/9.6/9.6 | .93–.95 | −.37…−.52 |
| Qwen probe s1 final | | ≈ same as step100 | | 0 | 10.9/9.8/9.6/10.0 | .93–.95 | −.37…−.54 |
| Qwen P2.5 residual learned s0 final | | .73/.72/.50/.30 | .70/.46/.50/.25 | .24/.06/.26/.12 | 10.6/8.1/4.3/3.3 | .96–.996 | −.08…−.35 |
| Qwen P2.5 oracle s0 final (by construction) | | 0 | 0 | 1.0 | n/a (oracle grid) | | |
| Toy P2C s0 init | 1/3 | 0/0 | 0 | .22/.17 | 0.2/0.8 | .02/.04 | ≈0 |
| Toy P2C s0 final (61% dev) | | 0/.03 | 0/.006 | **.91**/.13 | 0.1/2.1 | .01/.28 | **.90**/.27 |
| Toy P2C s1 final (70% dev) | | 0/0 | 0/0 | **.81/.58** | 0.2/0.2 | .01/.52 | **.90/.46** |

M4, dev-gradient reach at init (first 2 dev episodes, no optimizer step):
- Qwen s0: loss 4.43. address_mlp grad 0.05/0.26/0.59/1.84 (L6/13/20/27). q/k/v grads 0.2–9.3. Head grad 7.7.
- Toy s0: loss 4.23. address_mlp grad 0.33/0.49. Head grad 0.53.
- Every Qwen group got a numeric gradient except L27 alpha and L27 out_proj, which are both None, as expected for the taskhead arm.

From the logged training telemetry, which is not a measurement of this run (training batches, phase-1 filler 0):
- The address-MLP grad norm falls from 2.6e-2…5.6e-1 at logged step 0 to at most 7.4e-3 (s0) and 2.0e-5 (s1) at logged step 10. In the inspected rows through step 100, s0 L20 is exactly 0.0 from step 40, and s1 L6/L13 are exactly 0.0 from step 20. Other groups retain or regain nonzero gradients.
- Loss falls from 4.23/4.30 to about 4.16, near ln 64, within those 10 updates and stays near it.
- Some address gradients remain or recur through step 100 (e.g. s0 L13 3.3e-3 at step 100). These rows suggest early deterioration; they do not establish when each lookup moved.

## Findings (descriptive)
1. **Not a dead start at initialization.**
   - At init, Qwen reads land on allocated cells (absent weight ≤.13; essentially no all-absent reads). Spatial overlap with the bound write is similar to the toy at init (within 1 cell .16–.34 vs .17–.30).
   - At reconstructed seed0 init, the two-episode dev task loss gives a nonzero gradient to every core routing/content adapter group, including the address MLP. L27 alpha and out_proj have no gradient, as expected for this taskhead wiring. Raw norms across the different model dimensions do not establish comparable learning quality.
2. **The reads left the memory early in training.**
   - **Established BY step 100** (both seeds, all 4 layers): read centroids sit about 10 cells from the value-write centroids. Per layer, about .97–1.00 of the read weight is on absent cells (s1 L20 is .9655). Head-pooled, s0 goes 4.67% → 99.28% → 100% and s1 4.17% → 99.14% → 99.14% (init/100/final, codex 21964).
   - Exactly all-absent reads at step 100 are 96.6% (s0) and 93.3% (s1). Within-one-cell alignment is exactly 0. Spatial coupling is ≈0, with a tiny remainder (s0 L13 max 9.1e-5).
   - The severe read/write separation persists at the final snapshot.
   - The logged training rows (a different population) SUGGEST deterioration within the first ~10 updates: loss near ln 64 and address gradients falling by orders of magnitude. They do not establish that every lookup had moved by then.
   - An all-absent read is exactly 0, so that read has zero LOCAL read-path gradient to its address and to the writes. The full training state is not shown to be absorbing: other reads and layers, shared parameters, and AdamW momentum and decay can still move it. s1 keeps some occupied reads.
3. **q and k collapsed in direction.** The pairwise cosine of query q vectors rose from .53–.72 at init to .92–.96, and value-write k vectors moved the same way. cos(q, bound k) went from ≈0 to −.4…−.8 (anti-aligned).
   - In the toy, q/k stay diverse (cos ≈.01 at the aligned layer), and cos(q, bound k) rises to .90 where the reads align.
4. **The P2.5 residual-head learned run shows the same direction, less extreme.** Reads are .3–.73 absent, offsets 3–11 cells, q cos .96–.996.

## Hypotheses (NOT tested; any mechanism claim needs a registered test)
- **H1, escape from noisy reads.**
  - At init the read features may carry little usable content: cos(q, bound k) ≈ 0, which does not establish absence of informative content. The loss is above ln 64.
  - Moving a read onto absent cells zeroes that read's features. If all taskhead read features are zero, the logits are head-bias-only, not necessarily uniform. Suppressing unhelpful reads might reduce loss toward ln 64.
  - The all-absent reads then have zero local read-path gradient, which makes leaving hard. Whether the state is absorbing is not shown.
- **H2, step size versus anisotropic features.**
  - Qwen q vectors are more similar at init (cos .5–.7; toy .01–.04). This could make an address-MLP update move many reads in similar directions; the measured cosine alone does not establish the update's direction or size.
  - With AdamW at lr 3e-3, early parameter updates might separate reads from writes before useful alignment forms. This diagnosis did not measure the movement caused by individual updates.
  - The toy's more diverse q vectors might respond differently. The toy comparison does not establish immunity to this failure or isolate feature similarity as the cause.
- H1 and H2 are compatible. Distinguishing them, or testing a fix, needs new short training runs, which this diagnosis did not authorize.

## Caveats
- Spatial geometry is only one factor of read gain; content q·k, beta and stored residuals also matter.
- Absent mass is not content.
- Init is a deterministic reconstruction, not a saved observation.
- Three dev snapshots plus the logged training rows do not establish the full trajectory.
- The training rows are a different population (train split, filler 0).
- The toy and Qwen differ in backbone, depth, width and geometry.
- The oracle is a by-construction control, not a learned-address comparison.

## Unresolved questions
- What drives the observed separation? Candidate interventions include (a) a lower address-MLP lr, (b) centered or whitened q/k inputs, or (c) reads constrained to retain occupied-cell support. A bounded local test could measure whether a selected intervention preserves routing; it would not by itself distinguish H1 from H2. Any such test is new training and needs its own frozen scope, codex review and a user go.
- Why does cos(q, bound k) turn negative rather than staying near 0?

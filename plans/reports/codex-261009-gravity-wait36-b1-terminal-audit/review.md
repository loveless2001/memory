# Independent B1 terminal audit — wait 36

**B1 completed 100 updates cleanly and is PARTIAL.** Original-stencil absent weight at update 100 is **0.2600495**, versus **0.9927544** for the retained A0 baseline. The combined fill-plus-anchor variant reduced the recorded escape substantially on this seed, but missed the preregistered kept threshold of 0.2 and was not kept through the five dev checkpoints. There is **no demonstrated dev-accuracy gain**: final 8/256 (3.125%) versus initial 9/256 (3.516%). This does not unlock a longer run.

## Artifact reconciliation

Both terminal exits are zero. The saved result is reproduced exactly by running the frozen summary/classifier on the collected telemetry, without training or model evaluation. The PilotConfig matches A0 apart from the three variant fields; dev seed, versions, TF32 flags and remaining SGM settings match. Policy/source identities reconcile. All 46 saved parameter tensors are finite; the terminal 8,625,720-byte safetensors SHA256 matches the manifest: `96d40040fe28f99b6e9f1bba4cf37a3753f3bf71694d3a1c63ab02a7439ab3bc`. The original file is preserved in the owner worktree; `retained-parameters.json` records its binding. It contains adapters/head parameters, not optimizer/RNG state for an exact resume.

The loop's bound 100-update configuration, complete dev schedule and clean terminal return support completion of this scoped run. Fifteen telemetry rows comprise five dev evaluations and ten train snapshots at updates 0,10,...,90; these are not a log of every individual optimizer update. Run records/readout were committed on the variant branch at c002fd2; raw artifacts are retained and audit copies are checksummed.

| Dev update | A0 pre-fill absent weight | B1 pre-fill absent weight | B1 fully absent reads | B1 correct / total |
|---|---:|---:|---:|---:|
| 0 | 0.0467013 | 0.0467012 | 0.0% | 9/256 |
| 25 | 0.9960537 | 0.4420408 | 21.80% | 3/256 |
| 50 | 0.9993223 | 0.4558267 | 14.82% | 3/256 |
| 75 | 0.9997459 | 0.3824879 | 14.48% | 3/256 |
| 100 | 0.9927544 | 0.2600495 | 13.16% | 8/256 |

The absent-weight metric is pooled missing interpolation mass, not the fraction of wholly empty reads. B1's endpoint improvement over A0 is 73.27 percentage points of this weight. The variant failed the kept criterion; no success threshold was revised afterward. This is a single-seed, filler-0, short mechanics comparison, not a general capacity or useful-retrieval claim.

## Interpretation corrections to owner 22142 / c002fd2 readout

1. **The blend's contribution is unmeasured.** A 13.16% fully-absent fraction does not mean the blend is inactive on the other reads: partially supported reads also receive it, with mean pre-fill missing mass still 26.0%. Empty banks are absent here, and nearest occupied distance averages 0.8045 cells. These establish support geometry, not prediction contribution or correct binding retrieval. No fill-off/bank intervention or contribution norms were collected.
2. **Logged loss includes the anchor.** At step 90, total 4.2077308 minus `0.1 × 0.4361982` yields task cross-entropy approximately **4.1641110**, close to `ln(64) = 4.1588831`. The inferred task loss is below ln64 at logged steps 60 and 70 (4.1470352 / 4.1480974). The subtraction uses saved FP32 scalars, with rounding tolerance. Neither total loss above ln64 nor fluctuating task loss establishes that memory adds noise or information. Final accuracy has no observed gain over initialization; useful memory dependence remains untested.
3. **Occupancy is not write-address spread.** More occupied cells establish increased cardinality, while the saved read-spread metric establishes read spread. No quantitative write-address variance was reported, so the claim that both read and write addresses spread wider is not established by these artifacts.
4. **Observed timing does not isolate a cause or price a longer schedule.** Median logged step times are 8.7106 s versus A0's 5.0313 s (1.731×); B1 child wall was 1054.3 s. This is consistent with extra fill work but is not an isolated overhead profile. A 1500-step recipe enters filler-40 at step 1000, which this variant has not profiled. The short filler-0 timing does not establish an all-in $10–12 or $15 bound.
5. **The 0.67 s lifecycle gap is not queue time.** It measures local start to the remote call. The retained Dict claim places worker entry approximately 17.87 s after that call, combining queue/startup. Queue time alone is not measured.

The raw numerical result stands. Correct these interpretations without rewriting its metrics or gates. A longer run is one possible new experiment, not the only available next step; free reconciliation already corrects the loss interpretation. Any follow-up needs its own concrete source/config, restart versus warm-start semantics, resource/deadline/cost audit and scoped authorization. No retry, extension, extra evaluation, new seed or 100-to-1500 continuation is authorized here.

## Shutdown and billing

Both client and cleanup exit zero. The cleanup's stop command returned one because the app was already stopped; its independent verification correctly reports `stopped_verified`. Fresh read-only Modal app/container snapshots independently confirm bound app **ap-ROPSmaSeABkUyr4X1d4RD2** stopped at **04:16:07Z**, zero tasks and no containers. No further stop action is needed.

The owner captured provisional **$0.70688371**. The independent report now returns **$0.71087544**, demonstrating backfill already occurred. It comprises 03:00 UTC **$0.06919454** plus 04:00 UTC **$0.64168090**, for this exact app ID only. Resources: L40S $0.57849977, CPU $0.05612931, memory $0.07594663, egress $0.00029973. This is currently below the $2.50 budget, not a final invoice or completeness guarantee.

A query ending at the current time with hourly full-interval semantics initially returned only the closed 03:00 bucket. The second query explicitly ends at 05:00Z to retrieve the still-open 04:00 bucket; that future endpoint does not make the data complete. The 04:00 hour is open at capture. [Modal's billing documentation](https://modal.com/docs/guide/billing) explicitly allows collection delays and recommends a buffer when completeness matters. Unit rates were checked against [Modal pricing](https://modal.com/pricing). A read-only recheck after 05:05Z is scheduled separately; no paid work is involved.

## Evidence and stop point

The run is complete, the app is shut down, the retention target was not met, and no follow-up has launched. Billing remains provisional until the scheduled closed-hour recheck. The prior missing amendment-bound checkpoint disclosure remains unchanged; this terminal parameter file is a different run and cannot substitute for it.

Evidence: `artifact-verification.json`, `verify-artifacts.py`, copied raw terminal files under `collected/`, independent live snapshots, both raw billing reports and `billing-snapshot.json`, `loss-decomposition.json`, `lifecycle-timing.json`, the retained owner readout at c002fd2, and `SHA256SUMS`.

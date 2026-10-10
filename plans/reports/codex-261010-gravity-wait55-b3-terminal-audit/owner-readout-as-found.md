# B3 (shift2 bundle) final readout: memory_used FALSE

One campaign from `2efd2b0` (codex package PASS 22525; user go/$17 cap 22535). Seed 4242 = reused, inspected DEV data.

## Run
- precheck ok 03:04:19Z → deploy 03:04:27Z, app `ap-uV0nVE4wGpjtep7vRs8tot` → spawn 03:04:43Z, call `fc-01M4HWABMJ4SHV1CRX72J7WTMM`,
  write-once deadline 09:34:47Z. Logs: `b3-launch-logs/01–07`.
- One start only (`B3.starts.jsonl`: start 1, resume_step null), container `ta-01M4HWABYE68TY018WJCDFM5GR`. No retry,
  redeploy, extension or second seed.
- Call returned rc 0, wall 12,209 s, volume_commit_errors 0. Watcher: "call returned" → cleanup `stop --yes` rc 0
  → **stopped_verified** (app stopped 13:28:37 +07, tasks 0, containers 0; 2 checks, 29 s).
- `collect` → 10 files fetched this call (resume.pt skipped), gate ok: "B3: valid, memory_used False, band kept".

## Gate (exploratory dev screen; chance 4/256)
| | none | bank derange | drop |
|---|---|---|---|
| B3 final (step 1500) | **8/256** | **8/256** | 0 |
| B2 final (reference) | 5/256 | 5/256 | 0 |

Criteria: final ≥ 12 AND derange drop ≥ 6 → **not met** (8 < 12; drop 0). Episode CI half-width ±0.020 (≈ ±5 correct):
8 vs B2's 5 is within noise. Equal counts ≠ "swap changes nothing" (per-example outputs not saved).

Dev by step 0…1500: 5 7 2 2 3 3 4 3 2 2 2 | 1 5 9 5 8 (filler-query phase from 1000).

## Telemetry (descriptive, not causal)
- Write gate beta per class (key/value/filler) .50/.50/.49 at init → .314/.313/.313 from step 300 to the end, i.e.
  flat and non-selective (B2 showed the same, at .121). Sink .46 → .24.
- alpha ≈ .018 in all four layers, unchanged from step 540 to the end. Train loss 4.16–4.17 ≈ ln 64 throughout.
- Empty read weight .03 → .06–.21 (band kept at end; not kept at every eval). Fully absent queries ≤ .073.
- Speed: ~6.5 s/update (0–999), ~10.6 s/update (1000–1499).

## Billing (modal billing report, hourly, snapshot ~06:31Z; provisional)
L40S $5.41233272 + CPU $0.52513505 + Memory $0.71054215 = **$6.64800992**. Hourly 03Z 0.719 / 04Z 2.395 / 05Z 2.394
/ 06Z 1.140. 03Z looks partial (≈1,080 billed s vs ≈3,300 s of container time) → backfill likely. Wall-time ledger
estimate (03:04:59–06:28:37 ≈ 12,218 s × $0.00067854) ≈ $8.29. Either way well under the $16.3035352 reservation and
the $17 cap.

## Reading
Scope: "no demonstrated memory use for the shift2 bundle, fill+anchor recipe, seed 4242, this run". The $0 probe
(3d7b4d1) showed the key information is AVAILABLE in the shift2 input offline; this run says that availability did
not turn into learned use under this recipe. It does not show why (beta/alpha freezing is an untested lead).

## Hashes (sha256 prefix)
b3_result.json 1e7993bac9108516 · final_bank_derange_eval.json eee91e6a0464a918 · identity.json 7387c0866a765055 ·
routing_telemetry.jsonl 11ce8b205a11e5c1 · run_manifest.json 00bd28c941546541 · trained_parameters.safetensors
7e0b4999af3a9e96 (15.0 MB, untracked like B1/B2) · billing json 1c06111a380cdf43

## Open
- Codex terminal audit (wait #55 fired).
- Re-pull billing after backfill.
- User: what next for the line. No compute is authorized.

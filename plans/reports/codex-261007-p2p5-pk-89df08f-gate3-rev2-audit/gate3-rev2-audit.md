# Independent Gate-3 rev2 audit — 89df08f

**CLEARED for the scoped campaign budget request.** The six findings from the f8d8592 audit are resolved in the submitted implementation. This is engineering/package clearance, not launch authorization or a scientific result.

Reviewed HEAD: `89df08fd08e238936902bb764a2928ac7b9f30b4` (implementation fixes in `967b8bf`), submitted in gravity 21622. Claude held the submitted paths unchanged during review (21624). No tracked implementation changes against HEAD were present at completion.

## Bound package

| Item | Verified SHA256 |
|---|---|
| `pk-prep/gate3-rev2/SHA256SUMS-gate3-package-rev2.txt` | `dc052cc911c4e10012052c7b99ea0f5c9b33931210b2891ac40168f8dbce2466` |
| Analysis dependency manifest | `5df85db8acc636b767c982c15c7073fac6292dbf3f6d76f276c48ccc4c3acd1f` |
| memsub source tree | `2eee4228124e9d292ed4079476ca276e8ce8f9ac7c8d83d44bcd51333687a19b` |
| v6 price model | `6745896e3f4b6ae4abc33020c6c195bbf9d3bedd800980e0ae8e0cd3b461c7c5` |

All 35 listed file hashes plus the memsub tree entry match. The frozen prereg, Amendment PK, registered grid and v5 ledger are byte-identical to f8d8592. All 10 proof manifest hashes still match the frozen proof index. The previously verified manifest-only source bridge is unchanged; the accepted proof and its historical labels remain preserved.

## Independent verification

- **68 focused tests passed, 2 opt-in slow tests skipped**, 9.26 s. Command: `OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 timeout 300s .venv/bin/python -m pytest -q tests/test_sgm_pk_campaign_*.py tests/test_sgm_pk_control_plane_reaper_and_manifest_label.py`.
- Fresh tiny CPU parity against the independently exported `2fda0d4` reference: **11/11 bitwise**, maximum relative difference 0, reference import isolation passed, deliberate perturbation detected.
- Reviewer probes independently exercised the corrected order, both mixed interface outcomes, both interfaces failing, transitive dependency mutation, checkpoint mutation, invalid IDs in both collectors, replaced-app stop refusal, production collector verifier closures, malformed cell containment and failed-fetch isolation. All passed.
- Pure arithmetic rerun reproduces v6 exactly except its pre-commit git-head provenance. Separate equations reconstructed from accepted proof timings and the registered workload also reproduce the totals.

Evidence: [focused test log](independent-focused-tests.log), [independent parity](independent-tiny-parity/parity.json), [probe code](independent-probes.py), [probe results](probes-v2/independent-probes.json), [successful probe log](independent-probes-v2.log), [recomputed v6](independent-priced-estimate-v6.json), [independent ledger equations](independent-ledger-equations.json).

The indexed owner evidence reports a full suite of 463 passed / 2 skipped and slow tiny readings of 2 passed in 1298.32 s. I verified those evidence-file hashes and inspected the logs, but did **not** repeat the full suite or the slow end-to-end run in this focused re-audit. The unchanged numerical implementation had already passed the independent full suite in the prior audit. The first reviewer probe attempt used exact equality on separately rounded seconds; that assertion was corrected to the rounding error bound, and the successful rerun is retained separately. The observed 0.1 s component-sum difference is ordinary rounding.

## Disposition of the six findings

| Finding | Verified resolution |
|---|---|
| R1: oracle order | The first four reserved calls are oracle N32 s0/s1, then the same checkpoints at N16 s0/s1. All other arms follow afterward. Both mixed outcomes retain independent per-N gating; a failed N's other corners stay untouched. |
| R2: analysis binding | A non-circular manifest binds the seven-script reached closure, grid, registry/schema, prereg/amendment and memsub. Launch checks both analysis and launch sections. The reader checks before evidence/population access and again at the end, including checkpoint bytes. A private 0.50→0.99 rule mutation is refused with zero evidence/reserved accesses; a mid-run checkpoint mutation makes every reading unavailable. |
| R3: name-only stop | Both collectors reject null, empty, whitespace, non-string and missing IDs before any poll/side effect. The strict wrapper calls the real shared helper with a required ID. A changed live ID causes refusal with no stop call. |
| R4: shutdown verification | Both production collector closures now query app and container lists. Stopped with seven tasks, or a remaining bound container, stays unverified; stopped with zero tasks/no containers and unlisted with no containers pass. Raw bound rows and query errors are retained. The installed Modal CLI uses the expected snake_case app/container fields. |
| R5: malformed/fetched evidence | Malformed acknowledged records become per-cell INVALID while the valid co-tenant and durable shutdown report remain. Each collection uses a fresh directory. A nonzero fetch return code skips validation and makes all cells UNAVAILABLE, without reusing an older snapshot. Dict-export failure is also covered by the passing focused suite. The installed CLI download layout matches the collector's slot-directory layout. |
| R6: workload/ledger | Oracle now follows the prereg memory-arm three-intervention matrix, with interface accuracy still taken from `none`. V6 explicitly prices 18 parity cells plus 20 reserved populations (38 builds/loads), 64 telemetry dev batches, binding/rehash work, controller startup and its 2× requested basis, all 11 images, and the final central-reaper/one-start-readings architecture. V5 remains unchanged. |

The private source variants, synthetic checkpoints/rows and faked Modal calls in this audit are orchestration evidence. They are not registered experiment outputs and do not establish a Qwen screen result or a measured production-runtime bound.

## Cost and authorization boundary

The v6 **runtime estimate is $116.31395302286052** for slot and readings GPU/CPU/RAM work. The **conditional planning reserve is $259.98622130744764**, rounded **$259.99**, including app envelopes, nominal shutdown tails, images, controller and $5 margin. The image line is $1.852224 for 11 builds; the modeled controller line is $0.2814361249294577. Describe the estimate's runtime scope when presenting it to the user; build/controller charges are explicit in the reserve.

Independent reconstruction confirms 9876.11617938581 s of readings work and its 1.4× reserve. The model retains stated assumptions: accepted single-host proof timings, 50 MB/s checkpoint I/O, 30 s build/load and binding allowances, 10% unattributed readings work, three restarts per slot, 2× CPU/RAM billing basis and nominal control/stop latency. No increase beyond these registered restart/admission bounds is authorized by the model.

Current [Modal pricing](https://modal.com/pricing) matches the listed A100-80GB, CPU and RAM rates used. CPU/RAM charges can follow actual usage above the request, and [Modal timeouts](https://modal.com/docs/guide/timeouts) distinguish startup and execution and permit some overrun. Consequently **$259.99 remains a conditional reserve, not a platform cash ceiling or unconditional worst case**.

Existing user authorization supports preparation only. Claude may now present the concrete, scoped budget request for the reviewed package. Paid deployment/spawn remains pending explicit user authorization; this audit performs no remote mutations and requests no extra paid proof. The completed proof's separate $8.57 hold remains subject to settled app/build billing reconciliation; its earlier app-only snapshot is not a settled total.

No shared source, controller journals, frozen proof artifacts or registered populations were modified. No deploy, spawn, remote stop, commit or push was performed. Reviewer files are confined to this report directory.

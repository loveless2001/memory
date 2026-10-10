PK6 v3: arithmetic PASS; per-slot app lifetime design accepted for free implementation with the requirements below

Audited f63b65c719e3b497f72b1a77f89cfc79d9461579. Claude may proceed with free campaign preparation under the already chosen packed-P2.5 plan. The arithmetic and app-lifetime separation resolve the v2 reserve/global-lifetime mismatch in design. The apps, collector, guard setup, schema/registry and once-only readings consumer are not implemented or independently verified yet. This is not deployment/spending/registered-population clearance; that requires the final bound implementation audit and explicit user execution cap.

Independent verification

Reran the pricing CLI and separately reconstructed every slot, reading and reserve charge from the registered grid and audited raw T. Every numerical field agrees within floating-point rounding ($1e-10 tolerance). The rerun differs from the published JSON only in inputs.git_head: the original output was generated at parent1cd0469 before commit f63b65c. Actual script/source/input SHA values bind the consumed bytes correctly; treat that field as the generation's base HEAD, not a claim that the v3 script already existed at1cd0469.

Script SHA55cb88fe49d3e9de13e72656d1ce53f3e55b122ec5cc860c6b474bc0dd1d9e1e. Timing/exit/grid/memsub/prereg/amendment and accepted proof hashes all match the previously audited bytes. Accepted proof SHA f4afca2b has pass=true. Raw T still has exactly eighteen distinct configs, and each primary fixed-work rate independently recomputes. No packing-test or old L40S timing is consumed by v3.

| Quantity | Independently reproduced |
|---|---:|
| Estimate, requested resource basis | $114.467371 |
| Training-slot GPU hours summed | 31.596222 |
| Single readings-app GPU hours | 2.198196 |
| Training slots in parallel, model wall hours | 5.212750 |
| End-to-end with sequential readings, model wall hours | 7.410946 |
| Nine slot-app charged lifetime envelopes | $236.144861 |
| Readings-app charged lifetime envelope | $13.444144 |
| Image reserves, ten apps | $1.683840 |
| Reaper allowance across all ten lifetimes | $0.422326 |
| Separately stated residual margin | $5.000000 |
| Planning reserve total | $256.695171 |

The app-envelope model charges each individual lifetime plus 120s reaper period and 120s stop allowance at the 2x CPU/RAM basis. It therefore covers pre-admission startup/crash activity within that app's lifetime rather than assigning all nine GPUs the longest slot deadline. Fixed-work training, explicit serialized commit/write proxies, restart reload, repeated evaluation, readings loading, ten image reserves and reaper lifetimes are present. Write throughput50MB/s including fsync, reload30s, startup300s and stop/reaper bounds remain stated assumptions; nominal deadline enforcement does not guarantee completion or a platform cash ceiling. Official [Modal pricing](https://modal.com/pricing), [retry](https://modal.com/docs/guide/retries) and [timeout](https://modal.com/docs/guide/timeouts) documentation was rechecked on Oct7.

Requirements to carry into implementation

1. Use unique, manifest-bound app IDs, guard/admission names and artifact namespaces for each of the nine fixed slots and the readings app. Fix each absolute deadline once before any GPU input can run, include the deploy/guard-setup/control-plane prelude in charge accounting, and retain the stop-first whole-app behavior for each app. Exactly one GPU function container per app; two fixed cell processes per training slot. No lifetime reset on retry, redeploy, collector restart or migration. CPU tests must cover host/client loss, crashes before and after admission, missing/expired guards, one app's failure/expiration while other apps continue, stop-ID isolation, deadline cleanup and late/unacknowledged evidence. The collector must retain partial/FAILED/LOST states and verify every app's stop and zero-task/container state independently.

2. Four admitted starts apply to TRAINING slot apps only. The unchanged protocol permits exactly one reserved-population readings run after complete validation/parity. Give the readings app one admitted start, ordinary retries0, and refuse any deployed-crash re-entry before reserved sampling/evaluation; do not automatically repeat a partial readings pass. Retain partial readings as unavailable/incomplete if that single attempt fails. The same time envelope may still be priced conservatively; its lifetime does not authorize a second readings attempt. Correct v3's blanket "each app <=4 admitted starts" description before binding the final package.

3. Verify schedule capacity before choosing ten periodic reapers. [Modal's pricing table](https://modal.com/pricing) lists five deployed cron jobs for Starter, and [Period is a function schedule](https://modal.com/docs/guide/cron). The workspace plan/remaining quota was not verified: the installed SDK's exposed Workspace interface has no plan/schedule-quota read method. Do not assume ten schedules fit or use a paid deployment as a quota probe. Confirm the existing allowance read-only, or implement and reprice a compatible control plane that preserves each target app's independent absolute deadline and stop-ID binding. Free design/code work can continue without waiting for a paid operation.

4. Make input bindings enforcement, not just metadata. The final runner/collector must consume the exact independently cleared pricing/grid/prereg/amendment/source/helper/schema/registry and proof provenance, reject duplicate/incompatible T/input data and unreviewed changes to bound execution inputs. Unrelated existing outputs/reviewer artifacts need not be deleted or committed for this check. Publish a new preserved execution supplement for the per-app topology so the accepted v0.4 amendment and proof keep their bytes. After the manifest-label source correction/campaign implementation, recompute bindings and quote provenance. Independently audit the source bridge: preserve the old GPU proof identity and explain why the metadata-only change leaves its numerical evidence applicable; do not relabel old proof files with the new source hash.

5. Keep the all-charge assumptions and limits visible. The current successful shared supervisor uses60 generation commits +1 joint inheritance +4 output/COMPLETE commits +1 runner-final commit =66; v3's67 is a conservative allowance, not the exact existing call count. Restart publication and prolonged commit/write/load costs remain charged by the bounded app lifetime. Simultaneous slot throughput, long checkpoints/telemetry growth and startup/I/O proxies are not measured guarantees; deadline exhaustion must yield retained incomplete evidence, not an expanded budget or recipe.

Small report corrections

- There are20 readings population units: eighteen trained cells plus the two oracle N16 transfer evaluations. The script charges20*30=600s load/validation correctly; gravity21595's22 is a prose error. Emit the count and population list in the final manifest.
- v3 compared with the preserved $160.433367/$273.788301 L40S model is28.6511% lower expected cost and6.2432% lower reserve. The approximately30%/9% comparison referred to v2; refresh v3's wording. This remains a comparison of differently scoped arithmetic models and proxies, not empirical matched-host savings or a demonstrated wall-clock speedup.
- Clean the script header's stale slower-worker/30-commit descriptions; the actual code uses the primary rate and67 commits.
- The single-app comparison $362.677857 is an illustrative comparison and omits its own CPU reaper line; do not promote it to a complete absolute bound. The per-app reserve above includes the stated reaper charges.

The paid proof's full approved $8.57 remains separately held until final app/build charge reconciliation. It is not reusable campaign margin. No paid campaign, registered training cell, reserved reading, deployment or new paid proof attempt is authorized by this design audit.

Reviewer evidence: check-v3.py, cli-v3-reproduced.json/log, independent-v3-audit.json and independent-model-comparison.json. The audit changed only new reviewer-owned files and performed no remote mutations, shared-source edit, commit or push.

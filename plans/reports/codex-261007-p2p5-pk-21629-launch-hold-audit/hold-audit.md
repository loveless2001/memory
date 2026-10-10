# Launch hold audit — gravity 21629

**The failed attempt is stopped. Retry/reset clearance is pending the final repair package.** User 21627 approved the scoped campaign following the $259.99 conditional-reserve request; Claude reported an image-build failure before spawning the first training slot and put the launch on hold.

At **2026-10-07 06:07:56 UTC**, independent read-only Modal queries in environment `main` found:

| Bound app | State | Tasks | Containers |
|---|---|---:|---:|
| Controller `ap-eqwdT119XvSoBJC1I2kDqC` | stopped | 0 | 0 |
| Failed learned-N32 deployment `ap-5IEq26DjFCdkvzXtmoi3Ct` | stopped | 0 | 0 |

Raw app/container responses and [filtered verification](live-hold-state.json) are retained here. Independent Dict reads confirm the controller registry is empty and its write-once guard still binds the stopped controller, the approved v6 price hash, and its original deadline. The learned-N32 guard/admission Dicts do not exist. These reads used `create_if_missing=False`; they created or changed no remote state. See [Dict evidence](dicts-read-only.json).

The archived deployment log shows `_build_environment` failing during module import: `M4_PK_SLOT` is absent before the later image `.env` layer, and the cleared runner's unconditional module-level validation raises `SystemExit`. The image build exits with code 1. The previous audit missed this build-container import case. The registry/Dict evidence agrees with no slot training registration or admission; a stopped snapshot alone is not a historical billing measurement. Controller/build CPU charges may still exist and must be reconciled; do not equate this failure with zero total spend.

A private CPU probe reproduces the old import refusal under the build context (`modal.is_local() == False`, missing slot variable). The provisional working-tree repair limits module-level refusal to local invocations and adds an invalid-slot return at the start of `run_slot`. Its private snapshot:

- imports in the simulated build context;
- returns `slot_unset` before any admission lookup when the runtime slot is absent;
- still refuses missing/unknown slots locally;
- preserves all nine valid app identities.

See [preview probe results](build-import-preview-probes.json). This tests the import/control-flow repair only. It does not execute a paid build, import dependencies in a real remote builder, or clear the final source/manifest/reset package. The uncommitted snapshot SHA is recorded in the probe result.

Claude 21631 confirmed no redeploy, spawn, Dict/path deletion or other remote mutation pending audit, and is preserving the attempt plus exporting guard/registry/ticks and billing evidence. The original control guard is already consumed; it cannot silently be reused as a fresh launch. Review the concrete repair, frozen dependency/package hashes, preserved failed-attempt evidence, reset namespace/state operations and incurred-charge treatment together before any retry/reset. No new paid proof is required to test the local import fix.

No shared implementation, journal or proof artifacts were edited by this audit. No remote mutation, commit or push was performed.

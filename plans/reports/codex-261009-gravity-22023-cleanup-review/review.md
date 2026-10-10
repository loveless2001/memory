# Cleanup review for gravity 22023: exact B/C proposals

**No deletion is authorized by this review and no files were deleted.** The user
requested an inventory and approval before removal (22021). Claude asked Codex to
review groups B/C. These manifests make that choice concrete; they do not approve
the broader A/D/E/F/G/H proposals.

| Proposed group | Exact files | Logical size | Recommendation |
|---|---:|---:|---|
| C-recommended | 11,700 | 1,664,290,626 bytes / 1.550 GiB | Remove listed generated fixture tensors after user approval |
| B-review | 51 | 1,276,221,807 bytes / 1.189 GiB | Optional: remove listed intermediate real probe states after user accepts loss of those replay/resume points |

Both groups together are 2.739 GiB logical size. All candidate paths are untracked,
regular files with link count 1. JSONL manifests bind every exact path, byte size,
allocated size, inode and SHA256. The companion .paths.txt files are for review,
not blanket directory/glob deletion instructions. Candidate files were read for
inventory/hash checks only; no model was loaded or training performed.

## C: generated audit fixtures

The C files are tensor outputs under nine explicitly enumerated pytest-tmp and
rejection-probes directories in four Codex audits (84f0a69, d62602c, de656de,
e1632cb). They are generated CPU proof/rejection-test fixtures. For example, the
retained d62602c clearance labels this evidence synthetic CPU checker proof;
sample fixture manifests identify eight-update, N4, random tiny Qwen models.
They are not the canonical paid campaign final parameters.

Delete only the listed .pt/.safetensors files if approved. Preserve the source
tests, scripts, audit decisions, logs, JSON outputs, original checksum manifests
and this removal inventory. Two unrelated 41-byte synthetic checkpoint files
elsewhere in the C glob are outside this proposal. Do not remove whole audit
directories merely because their names match codex-261007-p2p5-pk-*.

The tests can regenerate these fixtures. Once removed, the historical raw tensor
fixtures cannot themselves be reinspected; retained reports/logs record the earlier
checks but are not substitutes for their deleted bytes.

## B: preserve the small research/evidence subset

Of the probe's 60 original paid-run checkpoints, the proposal excludes:

- Both step-100 checkpoints referenced by the frozen diagnosis index.
- Both earliest saved checkpoints (step 50) and both final full-state checkpoints
  (step 1500). Final trained_parameters.safetensors files also remain.
- The three damaged original downloads: s0 step850, s1 step200 and s1 step550.
  Their three verified supplemental counterparts under the Oct 8 Codex audit stay.
- Every manifest, telemetry file, diagnostic input/output, report, launch/collection
  record, checksum inventory and the entire local-smoke directory.

All 60 old verified-generation receipts match the freshly captured hashes of the
candidate/protected files, using the supplemental paths for the damaged originals.
The frozen diagnosis index's referenced file hashes also match. Thirty exact
protected files are listed separately, along with the preserved Stage A/smoke prefixes.

Removing the 51 intermediate states leaves those retained endpoints and logs,
but loses local parameter/optimizer/RNG replay at the removed updates. Historical
hashes alone cannot reconstruct checkpoint bytes. No remote copy was reverified
for recoverability by this review; do not promise reversibility.

## Tests, paused work, and the running experiment

Keep source tests while their production/tool code remains. The 86 tracked test
files total only 775,608 bytes (the larger directory figure includes other files
such as caches). Retiring code and its tests together can be proposed separately;
deleting tests alone would remove regression coverage for retained scripts.

The live repository README and CONTEXT-POLICY.md confirm the reader/retrieval work
is paused at the user's request. Paused does not establish that the work has been
abandoned; group E and reader evidence should remain a distinct user choice.

Stage A, both Python environments, diagnosis dependencies, and other projects are
outside these B/C removal manifests. Existing terminal wait #25 remains active.

## Approval and execution boundary

Ask the user to approve C-recommended and/or B-review by those exact names. The
user explicitly requested this approval step; it is not an inferred audit rule.
Before any approved deletion, check for changes to the listed files/protected
bindings and coordinate a single execution owner. Retain a separate deletion
receipt identifying removed paths/hashes and verifying protected files remained.
Do not rewrite old checksum manifests to hide the intentional missing artifacts.

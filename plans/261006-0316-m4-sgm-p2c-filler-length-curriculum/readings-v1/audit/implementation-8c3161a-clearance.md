# P2C committed implementation check — 8c3161a

Commit `8c3161ac90fda21ff1d767a392af2ed08f802ec5` contains exactly
the three working-file fixes independently checked in
`codex-261006-p2c-implementation-e64266e-checks.json`. Every committed
fix hash matches that audit's recorded hash and the working file; all
reviewed analysis, input-index, grid and prereg identities also match.
Tracked working files are clean.

**Source audit PASS.** The original prereg-byte binding and toy-test seed
findings are resolved in committed code. The prior independent evidence
remains 73 initial targeted tests, four affected fix tests, actual-byte
start/end rejection probes and offline launch/seed/cap checks. No new
test run is needed for this exact-byte commit verification.

CPU preflight r2 was observed running on this commit. It is not yet a
passing result. The original r1-aborted log is preserved and is not used
as completed parity evidence. No duplicate parity process was started.

The implementation owner's explicit full-suite evidence is now verified:
`plans/261006-0316-m4-sgm-p2c-filler-length-curriculum/full-suite-8c3161a.txt`
records **206 passed in 181.93 seconds**, `EXIT_STATUS=0`, and the full
8c3161a commit hash. Artifact SHA256:
`af9879204954e2ec09b24a77fcfd42d94e98fa51433e64ce0bc90fcf6be02c40`.
The reviewed source hashes still match and tracked files remain clean.
No duplicate test run was performed to verify this saved evidence.

**Execution gate remains pending:** verify the completed r2 report's
eight parsed/byte-equal fixtures, schedule smoke and start/end identity;
then present the concrete four-cell ledger for the prereg's scoped user
cap approval. No actual training, deployment or registered readings
cleared by this source audit.

The earlier grep/head pipeline alone was not a valid test success guard;
the owner withdrew that claim in #gravity 21394. The explicit status
capture above resolves the test-evidence gap. The r2 completed report was
not yet present when this check was recorded.

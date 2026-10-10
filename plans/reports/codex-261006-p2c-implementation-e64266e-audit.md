# P2C implementation audit — e64266e

Reviewed initial commit `e64266e624f24e2b69553000abcee92503843a73`
against prereg v0.2 `0c8d358`. **Initial commit held for two findings;
the working fixes pass the targeted independent checks. Final training
clearance remains held for committed fixes and a completed source-bound
CPU preflight.** The prereg also requires scoped user cap approval.

## Findings and current resolution

1. The original P2C readings smoke used the production `READINGS_BASE`
   (9_500_011 and 9_500_012) on untrained toy N4 models, with 16 episodes
   rather than the registered N32/N64 population of 256 episodes. Thus
   "zero reserved-seed use" was inaccurate for seed values. No registered
   population was evaluated by that toy smoke. The working fix overrides
   only the test's seed base to 777_000, spies on every observer call and
   separates the metadata rejection test from model evaluation. The P2G
   toy smoke receives the same development-seed discipline. Both fixed
   smoke tests pass; no registered endpoint evaluation by this auditor.
2. The inherited P2G identity hashed the index's prereg pointer/hash, but
   not the actual prereg file. An isolated temporary-file probe against
   the committed e64266e source reproduced acceptance of changed prereg
   bytes at finish. The working P2C private-module wrapper adds actual
   `prereg_sha256` to identity and validates it against the index before
   work. Independent actual-byte mutation probes now fail at both initial
   validation and finish, without changing the closed P2G implementation.

The original parity preflight r1 was aborted by its owner while fixing
item 2; its retained log is not a passing preflight. Final preflight must
run on the committed fixed source and end with identical bound identities.

## Independent checks that pass

- The schedule modifies only training batch construction. Model, task
  head, optimizer and generator remain outside the update loop and persist
  across update 1000. The four explicit pilots have 1500 updates, schedule
  [[0,0],[1000,40]], filler_writes=true and evaluation filler length 40.
  Default-schedule weight/evaluation fingerprints pass for both seeds;
  the short schedule smoke records [0,0,40,40] training lengths and full
  filler evaluations. With learned arm and writes on, ingest passes no
  oracle addresses or filler write mask.
- All ten reused manifest/config/source/group/parameter bindings and eight
  complete parity references validate. These saved-input checks do not
  substitute for the unfinished runtime parity gates.
- The five-row reading table is total across 24 label/flag combinations,
  requires strict boolean flags, and supports only reproducible gain with
  memory use and half=true. Reference gain and half are computed from
  episode-paired E=on observations, never preset at N64. No development
  curve selects a schedule or checkpoint.
- All twelve launcher/collector helper functions match the cleared P2G
  AST after the declared identity, seed and cell-count substitutions.
  New app/group/claims, four IDs and max_containers=4 are explicit.
  Ten closed P2G/shared P2D/recovery/guard source files are byte-identical.
  The test maintenance retains historical P2G identities and accepts only
  the new empty-schedule default for its legacy config round trip.
- Independent dry-run reproduces timeouts 8773/6952/11797/10809 seconds
  and reservation **$11.12716980** under requested **$12**. Missing cap and
  $11 are refused. A temporary grid/index pair rebinding the training
  population to the reserved seed is refused before launch. Approved cap
  remains None. The unchanged recovery helper selects artifact evaluation
  seeds rather than registered readings seeds.

## Test evidence and scope

The initial targeted P2C/modified-P2G suites passed **73 tests**, with the
known reserved-seed toy smoke deliberately deselected (51.52 seconds).
After the working fixes, the affected P2C/P2G readings and prereg tests
passed **4 tests**, 11 deselected (124.76 seconds). Seed spies confirm only
development seeds were used in both repaired toy pipelines. Exact commands
and reviewed source/working-file hashes are in
`codex-261006-p2c-implementation-e64266e-checks.json`.

This reviewer performed no paid work, registered training cell, reserved
population evaluation or duplicate parity job. No runtime, prereg, or
test edits by this reviewer; the implementation owner made the fixes.

# Independent revision-4 implementation clearance

**Cleared to request separate paid-proof approval for d62602c. This is not launch approval or campaign clearance.** No GPU, deployment, launch, stop, commit, or push action was performed by this reviewer. No registered campaign cells or reserved readings were run.

The six affected modules independently passed **88 tests in 235.37 seconds**. The complete invocation, exit status, log and real-worker CPU proof artifacts are retained in this directory. The reported **395-test full suite** and **11-case bitwise tiny parity** were read from the retained logs, not independently rerun as new results. Training math sources are unchanged from the preceding audited revision.

The independent rejection replay now closes all previously reported cases:

- joint missing metric fields, partial single-layer telemetry omissions and duplicated prediction rows fail whole acceptance;
- the real supervisor marks partial-layer outputs, duplicated rows and an overflowing accuracy literal `1e999` **FAILED**, before COMPLETE publication;
- zeroed predecessor digests and missing timing measurement lists fail;
- duplicate ranks, wrong k, repeated update IDs and an inconsistent fixed-work rate fail both timing validation and the whole acceptance call;
- the unmodified CPU proof and the whole checker with a valid synthetic timing fixture pass.

All timing fixtures in these CPU acceptance checks are explicitly synthetic: the retained real CPU timing records carry test GPU/source labels and commit stubs. They provide checker evidence, not real A100 execution, Volume commits or GPU restart equivalence. The separately approved GPU proof must still establish those facts.

The pinned Qwen parameter registry was independently rebuilt on CPU: **46 gradient names/shapes and 46 saved tensor names/shapes match**, with correct grid/source bindings. The frozen output schema was reconstructed from the real CPU fixture and matches. Actual consumed comparator/registry/schema/grid bindings pass against an independently reconstructed runner identity. The newly loaded private packing helper matches its bound SHA and uses warmup=2, measured=4, seed0=99.

Clearance is bound to `d62602cafb81872e362fa334fd2e3d62755e5339`, memsub source `2e422cea223ab8fb27dad1ca796ff9a1f1f7f03ebd98dfa5ed541e208b75ffc5`, and the full file hashes in `audit-bindings-and-checks.json`. The scoped tracked tree was clean and the hashes were rechecked after testing. The original preregistration, accepted amendment and registered 18-cell grid remain unchanged. A read-only inventory of the main Modal environment contained no matching proof app at the recorded time; see `proof-app-read-only-inventory.json`.

Independent arithmetic reproduces the planned **$8.560027** reservation. The A100-80GB, CPU and RAM list rates were refreshed against [Modal pricing](https://modal.com/pricing). The planning reservation includes $8.1242784 for one GPU container over 6600+120+120 seconds on the 2x CPU/RAM basis, $0.0173646 for reaper allowance, $0.168384 image allowance and $0.25 margin. Expected $4.40–$5.56 and 78 minutes remain estimates. The reservation is conditional on the disclosed concurrency, reaper scheduling/stop latency and billing assumptions, not an unconditional platform cash ceiling. If requesting a cent-denominated cap, use at least **$8.57** to cover the exact computed reservation.

The next authorized-by-review step is **an approval request**, confined to the frozen proof: serial A/Aprime/B/C/D/E plus timing, seeds99/100, eight-update curriculum-crossing cells, C=2, the stated start allowances, one GPU container, overall deadline6600 seconds, and whole-app stop/collection. No approval has been inferred from the earlier free-preparation instructions. After explicit user approval and the bounded proof, independently audit actual consumer artifacts, provenance, timing, shutdown and charges. Only a passing GPU proof/artifact audit can support the later campaign ledger and separate campaign cap approval.

Reproducers, scratch copies and conclusions are retained in `independent-rejection-probes.py/.json`, `registry-reconstruction.json`, `audit-bindings-and-checks.json`, and `final-clearance-checks.json`. The scripts refuse to overwrite their evidence; another execution needs a fresh scratch/report destination.

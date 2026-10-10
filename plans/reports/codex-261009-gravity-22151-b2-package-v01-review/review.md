# B2 occupied-fill long-run v0.1: HOLD

Audited candidate: `77e6a36c506e84b0afa6fd1a39650c84fa17fa4a`, side branch `m4-sgm-occupied-fill-v1`. Main checkout remains `95856b153e874508726c604a8c593c6ff73684cb`. This is a CPU preparation/audit result, not a launch or learning result. User 22149 selected long-run preparation; the requested $17 campaign approval is still pending at the last channel snapshot. Initial findings posted in #gravity as 22153.

The exact candidate was exported to an isolated git-archive snapshot. No candidate code, existing research artifacts, running app, or GPU was changed. No live Modal methods were called by the mocks; their Dict, Volume, process, clock, watchdog, and kill operations were replaced locally.

## Checks that pass

- All eight package file hashes and the memsub tree hash match the checksum manifest; memsub remains `d86639b9223d4595a53cd07f3fee4da58c413414c49ed220d7135742f444a532`. Launch shell passes `bash -n`.
- **34 focused CPU tests pass** in 15.99 seconds: B2, B1, and occupied-cell fallback suites. This includes the tiny CPU crash-after-checkpoint resume comparison of final parameter bytes, telemetry excluding timing, and deranged accuracy. The owner's committed 66-test receipt is retained in the candidate snapshot; this audit independently ran the 34 directly relevant tests, not all 66.
- The raw remote-worker mock completes normally after a polling timeout and periodic commit; commits again at completion; includes telemetry and per-start stdout/stderr in its tar; excludes `resume.pt` and `resume.pt.tmp`.
- Failed commits are counted. A polling exception kills/reaps the child and cancels both armed guards. Version mismatch, immutable deadline mismatch, an exhausted three-start ledger, and insufficient time after setup all refuse without spawning a trainer.
- A delayed commit followed by expiration of the child's time budget kills/reaps the trainer and returns a timeout. An ordinary nonzero trainer exit returns its failure without raising a function exception; it does not request an automatic retry. The mocks do not establish real watchdog timing, remote durability, or preemption behavior.

See `focused-tests.log`, `package-verification.json`, and the reproducible `independent-worker-checks.py` / `.json` for evidence.

## Required fixes before launch clearance

### 1. Own the child before arming its watchdog

Runner lines 155–157 create the trainer, then create its watchdog, then enter the child cleanup `try/finally`. If watchdog creation raises, the child cleanup is never entered. The outer `finally` cancels the worker guard. The independent fault injection reproduces a live, unreaped trainer with no child guard and no kill request. A function retry could then start another trainer while the first remains alive.

Establish the child ownership `try/finally` immediately after successful trainer creation, initialize the child guard to `None`, and create it inside that protected scope. Every exception path must kill/reap a surviving trainer and cancel every successfully armed guard. Cleanup must also handle the normal process-exit race without masking the primary error. Add a regression for watchdog creation failure after trainer creation.

### 2. Preserve attempt evidence when restarting or resuming

Train lines 78–89 delete the entire output directory when no checkpoint exists. Lines 97–99 reopen telemetry for writing on resume, keeping checkpoint rows but erasing post-checkpoint partial rows. Both evidence losses are reproduced in temporary directories. The sibling starts log and per-start worker logs survive, but they do not preserve the deleted telemetry or other contents of the arm directory.

Archive the previous attempt's artifacts before restart or rewriting, while keeping a clearly identified canonical resumed trajectory. Preserve both completed and lost/replayed-update evidence. Archive names must be unique and bounded by the admitted-start policy. A partial run cannot be silently replaced by a fresh run with only a starts-log entry left behind.

### 3. Bind stored state to its campaign and source

Train lines 81–85 accept any checkpoint with the same PilotConfig. The mock accepts a checkpoint explicitly marked with unrelated source and campaign identity. The worker reloads the named Volume and uses an existing run directory without checking an immutable run identity; a new Dict deadline does not prove the Volume is unused. Current source checks bind the mounted code, not the origin of persisted optimizer/RNG state.

Bind the Volume/run and every resume checkpoint to an immutable campaign identity plus the audited memsub, train script, and base-manifest hashes and exact PilotConfig. Refuse foreign or unowned nonempty contents before starting a trainer. Admit resumptions only from that same campaign under its original deadline and start ledger. This should preserve legitimate preemption recovery and refuse an unrelated same-config checkpoint.

### 4. Validate results before declaring them valid

`summarize` at train lines 59–75 silently overwrites duplicate eval steps and never validates the registered sample counts or measurement values. Each of these adversarial inputs produces **status valid and memory_used true**:

- A duplicate final evaluation replaces a below-threshold final count with 12.
- Final `correct=12, total=1`.
- Deranged `correct=6, total=1`, while unmodified total is 256.
- A NaN final absent-read weight, classified as partial.
- A negative deranged correct count.

Require the unique registered evaluation steps, integer counts within bounds, exactly 256 queries / 64 episodes for both final conditions, consistent accuracy/counts, and finite/ranged routing and fill measures. Malformed or incomplete evidence must yield INVALID with a reason. Preserve the fixed exploratory thresholds and ensure the runner cannot accept an unvalidated verdict. Paired per-query/episode rows at the final none/derange evaluations would strengthen verification without additional forward passes.

## Interpretation and operating qualifications

The numeric tail `P(X >= 12)` is **0.0008134323391238844** under an independent Binomial(256, 1/64) model. That arithmetic is correct. Its applicability to learned predictions is not established: these are four queries within each of 64 episodes, sharing source state, and the evaluator already estimates uncertainty by episode. Keep 12 correct plus a six-correct derangement drop as predeclared exploratory operational thresholds; do not turn the conditional binomial calculation into an established significance claim without a justified null and dependence model. Report success as meeting this criterion for this recipe/seed, with the paired observations and scope limitations.

The final bank intervention is implemented as a cyclic shift of complete episode banks within each batch, with no fixed points for batch 16. Evaluation regenerates the same held-out episodes from seed 4242. This is relevant causal evidence about bank dependence when paired with performance; absent mass alone remains a routing result.

The no-fix reference used A100 while B2 proposes L40S. Config and data seeds can match, but CPU resume parity does not establish bitwise equality across GPU architectures. Describe a historical same-recipe reference rather than an exactly reproduced contemporaneous hardware pair.

The earlier B1 readout's categorical statement that 100 updates could never show learning remains too strong. The code does establish a train/dev length mismatch: training has filler 0 until update 1000 while dev uses filler 40. That can limit interpretation of the short test; it does not demonstrate that learning was impossible. B1's actual conclusion remains no observed held-out gain, with partial routing support.

## Deadline, costs, and durability

The conditional compute reservation arithmetic checks: `(23640 + 300) * 0.00067854 = $16.2442476`. The cleanup function shares one 300-second budget, matching its ledger allowance; the outer shell kills the cleanup command at 330 seconds. The proposal correctly discloses the unenforced app-stop latency and CPU overuse assumptions. $17 is an approval request, not a guaranteed external billing ceiling. Long-input fallback timing remains unprofiled and the approximately $11 / 4.4-hour projection is only an estimate. Current [Modal pricing](https://modal.com/pricing) supports the resource rates and separately prices persistent storage and egress; the ledger currently leaves those costs out. Include or explicitly allocate their small expected costs and persistent-storage retention scope within the requested reserve.

[Modal's retry documentation](https://modal.com/docs/guide/retries) distinguishes function exceptions from container-crash rescheduling, and [preemption documentation](https://modal.com/docs/guide/preemption) says interrupted inputs restart. The Dict bounds **admitted worker starts**, not all possible billed container births before admission. The immutable campaign/client deadlines and shutdown verification remain necessary.

[Modal Volume documentation](https://modal.com/docs/guide/volumes) describes explicit and background commits and reloads. `safe_commit` records failures but proves no specific checkpoint durable; do not promise that every locally written 50-update checkpoint survives. Report successful commit/checkpoint identity where observable, distinguish written from confirmed persisted state, and retain the replay boundary after each restart. A hung commit can consume the collection margin; the independent absolute watchdog is still necessary. If the final function raises or refuses without a tar, retrieve retained partial evidence through a read-only Volume download after shutdown verification, without launching a collection GPU.

## Stop point

No B2 launch clearance, new paid work, volume creation, merge, or continuation is granted by this review. The owner has actionable fixes in #gravity 22153. Re-audit the resulting exact package; obtain the scoped $17 approval only after the package is clear. B1 remains stopped and its separate app-attributed billing reconciliation is scheduled by existing wait #37 after 05:05Z; it was not polled early during this audit.

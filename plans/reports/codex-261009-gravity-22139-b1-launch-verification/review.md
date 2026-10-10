# Independent B1 launch verification

Launch record: 2026-10-09 03:57:52.796Z, launcher PID/PGID/SID 3341150. The owner worktree is clean at audited commit `7e9213adc803e06aa43c3c13b56c2190eb32d11d`; all eight package file hashes match v0.2. Recorded memsub source is `d86639b9223d4595a53cd07f3fee4da58c413414c49ed220d7135742f444a532`.

The read-only live snapshot around 04:00Z identifies bound app **ap-ROPSmaSeABkUyr4X1d4RD2** as ephemeral, with **one task and one container**. Its B1 Dict claim matches that container/task ID (`ta-01M4FCZFM6JE00APQK2P2789XR`), claimed at approximately 03:58:16Z. The immutable Dict deadline matches run.json: **04:37:57.754Z**. The recorded arm list contains only B1.

This confirms launch provenance and one live worker. No optimizer-update count or routing/accuracy result has returned; worker entry is not proof of completed training. At the snapshot there are no terminal exits/results. Billing has not been queried yet; the $1.9949 figure is a conditional reserve, not observed spend.

One authorized attempt, 100 updates, no retry or extension. The client timeout is 2640 seconds, followed by a 300-second cleanup budget with a separate 330-second outer kill. Provider shutdown and billed cost still require verification. No duplicate launch, stop, retry, GPU command or model forward was made by the reviewer; monitoring used read-only local records and Modal app/container/Dict reads.

**Wait #36** is registered on the worktree's `b1-run-v1.cleanup-exit.txt` with a 60-minute timeout. On wake, inspect both exits, collected partial/final artifacts, bound-app stopped/unlisted with zero tasks and containers, pre-fill routing/readout, and billing before posting the independent final audit in #gravity.

Evidence: copied launch record, run metadata and console; `local-launch-verification.json`; raw app/container snapshots; `modal-start-dict.json`; `live-launch-verification.json`; wait receipt; `SHA256SUMS`.

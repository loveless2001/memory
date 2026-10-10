# P2.5: cleared for one frozen CPU self-stop proof

In response to #gravity 21459, reviewed
`9e7b897a88526cf9c26589b2e69ddb9be44d45e0` and independently checked the
exact frozen runner, shared logic and proof runner. **The three blockers in
the 8f4a27f review are corrected. Clear one CPU `prove` attempt at this
revision, within user 21446's existing total $3 scope. GPU deployment/spawn
remains held until the resulting real self-stop evidence is reviewed.**

The cleared command, from `/home/lenovo/projects/memory`, is:

```sh
.venv/bin/python modal-runners/modal-m4-sgm-p2p5-reaper-self-stop-proof.py prove
```

This is independent technical clearance under existing user authorization,
not a new budget or approval for a retry/full campaign.

## Bindings and scope

- Profile runner SHA256:
  `e26013e6e34545552eb7d6d4fc8e07af2e1fc8c927f5e38818714a3de4069349`.
- Shared logic SHA256:
  `32bb3a3a38bf375e4c9107e4b3d7dc4c6392076cb5ba55f7c599fab644329e6c`.
- CPU proof SHA256:
  `00509c185b26762eadea126e27b2dc55b71de5cf1e592d6bceda20276de1479b`.
- Only app `memsub-m4-sgm-p2p5-reaper-proof`, guard Dict
  `m4-sgm-p2p5-reaper-proof-guard`, and fresh local proof directory
  `plans/261006-1345-m4-sgm-p2p5-qwen3-0p6b-screen/reaper-self-stop-proof-v1`.
- One deployment attempt; 60-second scheduled CPU reaper, 0.125 requested
  cores/256 MiB, 50-second function timeout, no GPU/volume/Qwen/populations.
- Deploy command timeout 600s; deadline 120s after deployment; proof watch
  window 600s plus one 60s period; unbound abandonment 240s after first tick.
  The planned lifetime allowance is 1,380s and 25 reserved ticks.
- Proof reservation **$0.052740625**, profile reservation **$2.3844246**;
  combined **$2.437165225 <= $3**. Proof spend consumes the same total cap.
  Keep the recorded nominal scheduling/stop-latency/resource/build allowances
  explicit; these estimates are not a universal platform spending guarantee.
- No automatic retry/redeploy. Failure triggers retained FAILED evidence and
  the scoped app-ID-bound fallback stop/verification, not another paid attempt.
  No change to the GPU profile contract or authorization for the 18-cell run.

## Independent verification

Targeted current-source tests: **40 passed in 0.47s**, exit 0:

```sh
.venv/bin/python -m pytest -q tests/test_sgm_p2p5_l40s_profile_runner.py tests/test_sgm_p2p5_reaper_self_stop_proof.py
```

The recorded broader suite says **253 passed in 276.41s**, exit 0. Its log
records the prior HEAD with the working-tree fixes; it is corroborating
author-run evidence, not an independently repeated full-suite result or an
exact post-commit hash certificate. Current targeted tests and our independent
script are bound to the three hashes above.

`codex-261006-p2p5-9e7b897-proof-checks.py` and its adjacent JSON independently
verify all of the following without deployment, build, paid work or API calls:

- Both production and proof reapers' file-defined Modal 1.5.1 SDK image
  dependency graphs include the shared file at the expected `/root` path.
  Both use CPU images with no GPU or artifact-volume mount; the profile
  worker has its separate heavy image.
- Deploy timeout retains stdout/stderr and its timeout classification, saves
  the resolved app ID, calls the fallback on that ID, and retains FAILED.
- A real injected deadline-binding exception retains app ID/deadline in
  provenance before binding, calls the fallback and retains FAILED.
- A lifecycle observer exception retains FAILED and performs fallback.
- The previous premature stop at 1010, before bound deadline 1120, is rejected.
- An in-window stop with missing bound server log marker is rejected.
- The valid in-window/log-backed fixture passes with **zero local stop calls**.
- Failed first lookup recovers the ID for cleanup; fallback stop failure
  remains recorded FAILED rather than escaping or turning into PASS.
- Child timeout recomputation continues to give 691s in the prior setup-delay
  fixture. The proof's shorter unbound abandonment fits its planned allowance.

The installed CLI's `modal app logs --help` confirms that `--tail 1000` is
supported and fetches without following. During review, a separate read-only
`modal app list --json --env main` showed no matching proof or profile app.
No deployment or remote mutation was issued by this audit.

One supplied binding-failure test uses `guard or FakeDict()` on an empty
custom dict, so that fixture can replace its intended failing guard. Our
independent test explicitly injects the binding RPC exception into the actual
`prove()` dependency, so clearance of that path does not depend on the weak
fixture. This test refinement can be made later; it does not change the frozen
code cleared for this one proof.

The profile script, guard, memsub source and original OOM report/log hashes
remain unchanged. R2/R3 retain their earlier local clearances.

## Real-proof acceptance still pending

Retain the deployment log and status, app ID and deadline in provenance,
server-side bound stop marker/logs, lifecycle time/attribution, and stopped
or unlisted state with zero tasks and zero matching containers. Review the
actual collected files rather than treating a local fixture or the proof's
`PASS` string as the remote result. A fallback stop is a failed self-stop
proof even when it successfully cleans up the app.

This clearance establishes that the CPU proof is ready to run. It does not
establish runtime container permissions, GPU fit, training performance or
scientific validity; those remain subsequent evidence gates.

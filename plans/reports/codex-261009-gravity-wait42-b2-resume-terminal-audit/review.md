# B2 terminal audit: VALID_NEGATIVE; stopped_verified

Wait #42 is complete. Independent read-only Volume capture finished at **2026-10-09 14:57:54Z**; offline verification passed at **15:01:24Z**. B2 reached its registered endpoint and produced a valid negative result: **no demonstrated memory use for the fill+anchor variant, seed 0, and this recipe**. The run is shut down; its final artifacts and interrupted-segment evidence are retained.

## Result and interpretation

All 16 dev evaluations at updates 0–1500 by 100 occur exactly once and pass the registered schema, over 256 queries from 64 episodes. The independent threshold calculation and the runner's classifier agree exactly with b2_result.json.

| Endpoint | Correct / 256 |
| --- | ---: |
| Initialization | 9 |
| Final normal memory | 5 |
| Final bank derangement | 5 |
| Normal-minus-deranged drop | 0 |

The preregistered exploratory gates were at least 12 correct and at least 6 fewer with deranged memory. Both failed. These thresholds do not establish statistical significance; four queries share each episode. The evaluator pre-generates episodes with a separate data generator at seed 4242 for every call and cyclically replaces each episode's complete memory banks with another episode's banks. The paired inputs follow the same registered code and config. No new evaluation was run in this audit.

**Correction to chat 22273:** equal aggregate scores do not establish identical predictions, identical logits, or that swapping “changes nothing.” Per-example predictions were not saved. Some read telemetry differs: normal pre-fill absent mass is 0.2363478371, versus 0.2300242741 with deranged memory. memory_used=false is the registered operational result, not proof that Qwen cannot use memory or that all memory effects are absent.

The final routing band is partial: absent mass 0.23635 exceeds the <=0.2 band. All scheduled evals from 300 through 1200 were in band, as was initialization; evaluations 100, 200, 1300, 1400, and 1500 were outside it. Better routing did not produce demonstrated retrieval on this endpoint. Last logged task CE after subtracting the 0.1-scaled anchor is 4.16782; the final ten logged rows average 4.15563, near ln64=4.15888.

The descriptive gradient/write-gate leads are supported, but causation is untested. At update 1490, L6 out_proj/alpha norms were 6.11e-7/2.18e-6; L13 and L20 were smaller. L27 out_proj/alpha are null, not measured small values. Final key/value/filler beta means are approximately 0.121. These observations do not identify whether the bottleneck is writing, read content, downstream sensitivity, or optimization. The isolated checkpoint and aggregate evaluator data cannot settle that question.

## Completion, checkpoint and provenance

The live saved FunctionCall result matches the owner's receipt exactly: start-2, returncode 0, wall 8,610.6765 s, no Volume commit errors, Torch 2.7.1+cu126 and Transformers 4.55.2. There were two recorded starts; start-2 restored update 750 and start-3 remains unused. Original deadline/start-1 and the write-once resume deadline are unchanged from the first-start audit.

The independently downloaded terminal resume.pt is update **1500**, 25,159,637 bytes, SHA256 **443f041cae4efa21b7859415063c059248ce8fabe4f53b3f87c58d7c8f189634**. Exact config/run identity match; all parameter, optimizer and saved RNG tensors are finite. All 44 populated optimizer states report step 1500. All 46 adapter/head tensors match the final safetensors exactly, with 44 changed relative to checkpoint 750. Final trained-parameter SHA256 is **2149c97517ad0f844b30a82f52b0072090f02b1709809f6bac5f09afe107fdb3**, matching the manifest.

The checkpoint's telemetry is the exact 165-row prefix before the final dev evaluation; current telemetry has 166 rows, including 150 logged training rows and 16 evals. The admitted checkpoint-750 telemetry remains an exact prefix, and archived start-1 telemetry is byte-identical to the protected original partial. The first segment's post-checkpoint updates were preserved and at least 21 were replayed. CUDA continuation was not certified bit-identical to uninterrupted training.

All eight v0.4 package hashes and the memsub source hash match. Training/source/tests have not changed between cleared e03ca5a and owner's final-record commit faa6a7b. Every available owner-collected Volume file matched this independent capture byte-for-byte. The terminal checkpoint, omitted by the owner's collector, is now retained here as well.

## Cleanup and remaining runner defect

The original local watcher has no exit receipt after the reported PC reboot; no clean watcher/launcher exit is inferred. The two manual cleanup records are retained separately.

1. The manual watch returned 1 after **289.741 s**, with shutdown_unresolved. Stop stderr explicitly says no interactive terminal was detected and requests --yes. Repeated verification correctly refused to call a deployed app with zero tasks/containers stopped.
2. The corrected stop returned 0 and achieved **stopped_verified** in **8.071 s**. Its receipt gives stopped_at **14:52:43Z / 21:52:43 Bangkok**, zero tasks and zero containers.
3. This audit's fresh CLI snapshot independently shows the resume app stopped with zero tasks, the original app unlisted, and an empty account container list. Both satisfy the registered stopped-or-unlisted plus zero-tasks/containers rule. No additional stop was necessary or issued.

**The production runner still lacks --yes in cleanup_verify at line 465.** Manual success did not repair it. The installed Modal 1.5.1 CLI source confirms that an unstopped app prompts unless yes=True; this was a real coverage gap in the prior CPU clearance. The previous passing tests did not establish noninteractive deployed-app cleanup. Before reuse, add --yes, exercise an initially deployed app through a realistic CLI fake that rejects missing confirmation bypass, retain the failed receipt, and update the package hashes/review. No code amendment, redeployment or GPU work was performed during this terminal audit. The [Modal app CLI reference](https://modal.com/docs/cli/latest/app) documents the confirmation bypass.

## Billing

Independent daily report:

| B2 segment | App | Reported USD |
| --- | --- | ---: |
| Original | ap-VsAmnu1E7eS5rXLrKD7vXd | 5.69262133 |
| Resume | ap-bgncTcGPrYbwfmiQtprLN9 | 5.23085059 |
| Combined | Same approved total cap | **10.92347192** |
| Approved cap | | 17.00000000 |

The same hourly report shows resume charges only in 09Z, 10Z and 11Z; no reported resume compute charges after 11Z. This supports the idle period having no additional reported compute charge, but is not proof of a settled invoice. The hourly resource rows sum two hundred-millionths of a dollar below the daily resume aggregate, consistent with rounding of displayed rows; the daily aggregate is used above. B1's 0.71087545 is a separate approval.

These are gross app-attributed usage reports before credits/allowances. Separate storage or transfer charges and later backfill are not certified. [Modal billing documentation](https://modal.com/docs/guide/billing) notes possible reporting delays and the distinction from invoices. The arithmetic difference from the cap is 6.07652808; it authorizes no further run.

## Evidence and boundary

live-snapshot.json, app-list.json, container-list.json, volume/, owner-receipts/, both raw billing reports, terminal-verification.json, and the capture/verification scripts retain the evidence. The verifier passed without building/restoring a model, running any forward/evaluation, training, or using CUDA. SHA256SUMS-audit.txt inventories this local audit.

Wait #42 is closed and no wait is rearmed. No deploy/spawn, Dict/Volume mutation, extra seed/arm, deadline extension or paid diagnostic was performed. Result acceptance is complete; runner reuse remains on hold for the cleanup repair and a separate authorized next scope.


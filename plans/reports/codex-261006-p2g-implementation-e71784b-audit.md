# P2G implementation follow-up — e71784b

Decision: the three original `dc9e0bb` holds are resolved in the reviewed code. **Final implementation clearance remains pending the recovery CLI fix and complete preflight-r2 evidence.** Training remains unauthorized; `P2G_CAP_USD` remains `None`.

Fix commit: `e71784b`. Review checkout HEAD: `c504a897be1a1cb2ceba0f8de071589f0eeb1fe5` (the latter adds the first preflight evidence only).
Prereg: v0.2 `25fdbc5`. Coordination: #gravity 21319, 21321 and 21323.

## Resolved original holds

1. The grid and inputs index now distinguish the published artifact seed `9_300_011` from reserved readings seed `9_400_011`. Runner planning, spawn, and the container's pre-claim identity check require the artifact seed. Readings validate both run and split manifests against `9_300_011+s`, then use `9_400_011+s` only for the registered post-validation population. The invalid cross-host comparison between different evaluation populations is removed.
2. AUROC rejects non-finite input before ranking. Classification and half-oracle checks reject malformed, non-finite, misordered or wrong-count intervals. Gate telemetry validates all four heads, class populations, finite bounded betas, and skipped/applied event consistency before summary statistics. The original NaN and missing-head reproductions are covered by passing targeted tests.
3. Preflight/readings compare every recorded executed identity before and after work and revalidate reused inputs. Git HEAD alone may differ due to a concurrent docs commit; both endpoints are persisted. Readings also recheck consumed P2G manifest/parameter/row hashes.

## Remaining recovery integration fix

`scripts/sgm-recover-and-validate-grid-artifacts.py:210` still chooses:

```python
seed_base = grid.get("final_seed_base", FINAL_SEED_BASE)
```

The new P2G grid has no `final_seed_base`, so the CLI silently selects `9_100_003` instead of artifact seed `9_300_011`. A valid P2G training artifact would be rejected for its final evaluation seed. The readings script's direct validator call is correct; the standard volume recovery/validation entrypoint needs the same seed semantics.

Independent reproduction using a known-good P2D fixture with artifact seed `9_300_011`:

```text
generic_recovery_selects 9100003 registered_artifact_seed 9300011
known_good_fixture_explicit_artifact_seed None
same_fixture_generic_seed mismatch ['final_eval_seed']
```

Required: prefer `artifact_eval_seed_base`, then legacy `final_seed_base`, then the historical default, with regression evidence for all three paths. Preserve existing v2/P2D behavior. The validator is an end-checked r2 input: coordinate this change after the running fixture job, not during it.

## Independent verification

- Command: `.venv/bin/pytest -q tests/test_sgm_p2g_gate_knob_and_decision_rules.py tests/test_sgm_p2g_observer_runner_and_preflight.py tests/test_sgm_p2g_fail_closed_and_seed_reservation.py tests/test_sgm_p2g_readings_pipeline_smoke.py`.
- Result: **62 passed in 83.00 s**.
- First complete preflight (`dc9e0bb`, evidence commit `c504a89`) independently verified: **6/6 files parsed-equal and byte-equal**, 5,120 rows each, 30,720 rows total. Every file has all five legacy interventions, 256 episodes per intervention, four unique queries per episode, and shared episode identities across interventions. Reference hashes and producer script/index/grid hashes match their frozen producer commit.
- First report SHA256: `9f531c3c8fdb18960d87321d849961ffa720b4d229b01e28e1f468a914dfa927`.
- Detailed verification artifact: `plans/reports/codex-261006-p2g-preflight-dc9e0bb-independent-checks.json`, SHA256 `05ba1433f73ecfc47650520e19a9c1184aa6f90013e7c90e9fd264deac4cc467`.
- Step-0 pooled rho and AUROC summary arithmetic match per-head values. Step-0 telemetry does not satisfy registered selective suppression; it is descriptive initialization evidence, not a training result.
- The first parity evidence does not replace the ongoing source-bound r2 package. No duplicate parity job, training cell, deployment or paid run was started by this audit.

Next: review the recovery fix/regression evidence and completed r2 package, then issue a final implementation decision before seeking the separate scoped training authorization and reviewed cap.

# P2G preregistration v0.2 audit

Verdict: **cleared for implementation and the specified CPU preflights**.
No training or new model evaluation was executed during this document audit.
No P2G training run, fresh-seed evaluation, deployment or paid cap is approved
by this verdict.

Audited document: `25fdbc5`,
`plans/261006-0010-m4-sgm-p2g-selective-write-gate/prereg.md`, SHA256
`c2fa7394e9e621766af705743d46715b9584c83e161a90bdfd45d928908925c3`.

The amendments close the six v0.1 findings:

1. The common observer, E-on/E-off parity gates, immutable reused-checkpoint
   index, observer/rules/source hashes and historical-cohort limitations are
   explicit. All six abbreviated manifest and parameter hashes in the draft
   agree with the actual files, and every parameter hash matches its manifest.
2. The registered headline is pooled filler suppression. Event counts,
   skipped-write zeros, a positive finite denominator, applied-event AUROC,
   undefined-head handling and descriptive head reporting are defined.
3. The contrast classifier is ordered and total; the added symmetric loss
   class is acceptable before execution. Q2 covers all four conjunction
   combinations. The Q1 priority table covers all 24 combinations of the
   three Boolean flags and true/false/null half status, with exactly one
   branch each. The oracle prerequisite and unavailable case are explicit.
4. The bias-shift description is accurate, keeps other random draws intact,
   and records the initialization knob in config/manifest/result identity.
   The fixed -3 bias and 0.20 suppression threshold remain untuned choices.
5. The six timeouts and all six reservation components agree with the prior
   guard calculation. Decimal addition gives $12.32978160, below the proposed
   $13 cap. The cap is a request, not authorization. The new group and runner
   keep old claims, identities and shared budgets separate.
6. Implementation and CPU preflights precede implementation audit and scoped
   user training authorization. Local training follows the same gate. The
   fresh final seed remains unused until the registered readings stage.

Machine-readable checks and the six full fixture identities are saved in
`plans/reports/codex-261006-p2g-prereg-v02-checks.json`.

## Implementation acceptance notes

- The parity references contain **five legacy interventions** and 5,120 rows
  each: none, bank_derange, coord_shuffle, read_offset, query_off. Reproduce
  those complete files in their reference order for the parity checks; the
  new final protocol uses three interventions separately. Do not compare
  a three-intervention subset and call it complete-file parity. Preserve both
  parsed-row and byte equality evidence, including P-off.
- Bind the parity reference file hashes in the committed inputs index and
  record the candidate observer source hash before/after the preflight.
  A failed parity gate stops progression without switching observers.
- A checkpoint evaluation must load its saved beta bias. The initialization
  knob must not overwrite the learned bias after loading trained parameters.
- Preserve the old source/manifests and their validation contracts. Adding
  a default-None config field must not silently reinterpret old provenance
  or admit nondefault gate settings as legacy runs.
- Tests should cover classifier boundaries/loss, all Q1 branches including
  null, malformed/missing/mispaired inputs, invalid suppression denominators,
  skipped versus applied-zero AUROC events, and the exact six-cell budget/
  attempt/collector coverage. The unchanged Step 2 rules remain hash-bound.
- Submit the committed implementation, full inputs index, tests, step-0
  telemetry, both actual parity outputs and exact ledger dry-run for the
  implementation audit. Only after that audit should the user be asked to
  authorize the concrete training run and its reviewed cap.

The closed Step 2 results, raw original artifacts and registered rules remain
unchanged. This verdict makes no numerical prediction about P2G outcomes.

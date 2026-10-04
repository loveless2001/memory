# Broader reader stopped at the approved time ceiling

Post-collection update: review, correction and the separately attributed
[author adjudication](../20260911-v2-broader-adjudication/REPORT.md) cover all 262
captures and record 104 pass / 157 fail / one ambiguous. Both Claude passes and
the earlier [117-entry audit](../20260911-v2-broader-review-audit/REPORT.md) are
preserved. The collection report below preserves the evidence and status at the
time of capture. Training remains paused.

The authorized one-H100 run captured **262 of 360 planned answers** before its
internal deadline stopped collection. All forty cache fixtures, sixty completed
notes, 171 note updates and 262 saved captures pass artifact verification.
Every captured body passes structural checks and fits within 90 words.
**At collection, answer correctness was unscored; review and training were pending.**

Run `20260911-v2-broader-reader` used Modal app `ap-sYYVFX3HE9S0HEQOIVWPgC`,
function call `fc-01M26A2Q7ZTSWG0MG7AQQ6JECX`. The user authorized one H100,
a forty-minute hard ceiling and zero retries. The internal deadline reserves
artifact-save time; it stopped before the next condition at 2,351.358 seconds
(39 minutes 11 seconds). The runner preserves its terminal status as `failed`
with `forty-minute ceiling; reserving artifact-save time`, rather than rewriting
that status as a completed evaluation. No retry ran. The final app-state check
confirms `stopped` with zero running tasks; see `app-status.json`.

## Captured coverage

Fourteen families, F001–F014, have all eighteen answers. F015 has ten answers:
Q1–Q3 at all three retrieval depths and Q4 at depth two only. F015-Q4 depths
zero and one, F015-Q5/Q6, and all of F016–F020 are missing. This leaves
**87 complete three-view questions, one partial question and 32 unstarted
questions**. `capture-coverage.json` enumerates all 98 missing conditions.

| Case class | Zero retrievals | One | Two |
| --- | ---: | ---: | ---: |
| Historical recall | 30 | 30 | 30 |
| Withdrawal | 15 | 15 | 15 |
| Attribution | 14 | 14 | 15 |
| Later different value | 14 | 14 | 14 |
| Later same value | 14 | 14 | 14 |
| Total captures | 87 | 87 | 88 |

These are capture counts, not accuracy. Collection is a prefix of the frozen
family/question schedule, not a random subset. Any paired comparison must use
the appropriate common set and disclose the omitted conditions. The full suite
was not completed within this budget.

## Verification and limits

`verify_artifacts.py` checked the nine hashed server artifacts, source snapshots,
runtime inputs, all 32 preflight-frozen files and 394 protected prior artifacts.
It replayed all 171 selector events against their exact source batches, prompts,
grammar and note admissions, including parent-to-branch state. All sixty notes
have valid source bindings; they contain 302 selected quotations and range from
689 to 766 tokens within the 768-token cap. The 1,197 withdrawal-ledger entries
reported across all histories include repeated parent ledgers in branches;
they are not 1,197 distinct withdrawal events.

All 262 actual reader transcripts, retrieval slices, token counts, decoded
bodies, EOS records and fresh-prefill token accounting match offline replay.
All 262 bodies are structurally valid and at most 90 words; the maximum is
79 words. The largest actual input is 3,992 tokens before the 192-token output
reserve, within the 8,192-token context limit. These checks certify saved
structure and provenance, not useful note selection or semantic correctness.

The cache gate covers forty fixtures for this new raw-source transcript using
the frozen base reader in FP32 with math attention and TF32 disabled. It does
not certify an adapter or arbitrary transcripts. Notes were selected in BF16
without access to queries or references. References and judgments were not
mounted in the reader image. The `ANSWER` prefix was supplied, and every condition
used a fresh prefill; no learned action policy was exercised. There were zero
trainable parameters, training labels or training runs.

## Independent review handoff

[CLAUDE-BROADER-ANSWERS.md](../../../CLAUDE-BROADER-ANSWERS.md) points to the
[review packet](../20260911-v2-broader-answer-review/packet/index.json): 88 cases,
262 anonymous captures and sixty complete sanitized histories. Its manifest
binds the actual captures, references and source files. The packet validator
passes, and five validation checks confirm coverage and evidence safeguards,
including rejection of omitted answers, fabricated quotes and incomplete work
marked complete. They do not constitute an answer review.

The reference review remains twelve delta accepts plus 108 inherited accepts;
no fresh 120-reference review is claimed. Reviewers must assess actual visible
support, full-source consistency, task completeness, withdrawal, ownership and
format separately. Case/condition labels are masked, but actual messages reveal
evidence depth and reviewed references are visible. Independent model review
is not human validation or permission to train.

The suite retains its selected synthetic-release, passage-cue and family-sharing
limits. It is not an official held-out benchmark or general memory evaluation.
The new wrapper and instructions also prevent pooling these results with earlier
prompt variants as if their harnesses matched.

## Cost and reproduction

Modal billing observed at `2026-09-10T19:22:59.642530+00:00` reports
**$2.85199616** for this app. Together with the previously recorded v2 cost of
$3.38624093, the observed cumulative total is **$6.23823709**. `billing.json`
preserves the two hourly rows and resource breakdown; billing observations may
lag final usage.

Local verification requires no inference:

```bash
.venv/bin/python plans/260910-context-policy/20260911-v2-broader-reader/verify_artifacts.py
.venv/bin/python plans/260910-context-policy/20260911-v2-broader-answer-review/validate.py
```

Do not rerun the launch command to validate artifacts. The authorized run has
ended; completing the remaining conditions would require a separately scoped
run. Training remains paused pending independent answer review and subsequent
admission decisions.

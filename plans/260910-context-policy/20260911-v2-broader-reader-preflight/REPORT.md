# Broader reader prepared on CPU

The reviewed 120-question v2 suite is ready for a bounded raw-source reader run.
Preparation produced 360 zero/one/two-retrieval conditions, sixty source-bound
history views, and a query-blind note worklist. **No GPU run, generated notes,
reader answers or training labels were produced.** Independent reference review
coverage remains twelve delta accepts plus 108 inherited parent accepts.

## Changes needed for this run

The initial audit found 26 direct `Forget …` requests missed by the legacy
`Please forget …` detector. They now enter the complete verbatim withdrawal
ledger and cannot be selected as fact quotations. The original failed CPU audit
is preserved under `audit-history/please-only-preflight.json`. Legacy code and
completed experiments remain unchanged. The expanded detector covers these two
explicit forms, not arbitrary natural-language deletion requests.

The new source wrapper retains original text exactly and labels role, turn and
Unicode character offsets. Even partial recent-context slices retain their actual
speaker attribution. No hand-authored UNKNOWN state is presented as user text.
The system instruction clarifies historical textual scope, current user facts
and explicit personal assertions within questions. These changes give the run a
new harness identity; earlier scores cannot be pooled as if the prompts matched.

Original notes are generated once per family. Each synthetic continuation starts
from its parent's completed note, then processes its own new user statement.
That requires **131 original-history updates plus 40 branch updates**, rather
than replaying each entire history for each branch. Queries and references are
excluded from selector inputs. The real selector still has to run and pass all
source and budget checks.

## CPU validation

All 360 chat fixtures and 240 append-prefix comparisons passed. The largest
fixture reader input was 3,994 tokens before the 192-token output reserve; the
largest selector-input fixture was 3,380 tokens against a 6,144-token limit.
The maximum source-choice grammar bound was 113 tokens against a 192-token cap.
The 768-token note budget leaves **161–530 tokens** for non-ledger quotations.
No budget was enlarged or withdrawal silently omitted to obtain these results.

These are deterministic source-quote fixtures, not model-selected notes.
Actual selector choices and reader inputs remain subject to runtime validation.
Ten targeted CPU tests cover Unicode/source fidelity, role and hash tampering,
recent-context clipping, retrieval uniqueness, transcript appends, direct
withdrawal handling, and note quotation identity. `test-results.json` records
the executed tests; `verification.json` records the actual freeze checks.

After query-only evidence selection was saved and hashed, a separate private
audit checked full cited claim spans in recent context plus retrieval:

| Case class | Zero retrievals | One | Two |
| --- | ---: | ---: | ---: |
| Historical recall | 0/40 | 40/40 | 40/40 |
| Attribution controls | 0/20 | 19/20 | 20/20 |
| Later different-value controls | 20/20 | 20/20 | 20/20 |
| Later same-value controls | 20/20 | 20/20 | 20/20 |

This excludes unknown generated notes and measures complete cited-span coverage,
not semantic sufficiency or accuracy. The twenty abstention references have no
positive claim spans and are not assigned a zero-coverage score. Withdrawal
support and chronology still require actual-view review. The strong retrieval
coverage underscores the explicit passage cues and local-extraction character
of this selected suite.

## Prepared execution and stop conditions

The entrypoint is `modal-runners/modal-broader-reader.py`. Its reader-image
allowlist contains only the five runtime inputs and required implementation
sources; references, audit results, review verdicts and CPU note fixtures are
not mounted. It defaults to preflight-only unless `--execute` is supplied.

Proposed execution is one H100, forty-minute hard cap (internal stop at 2,350
seconds), zero retries and at most 360 captures. A fresh forty-fixture FP32/math
GPU cache gate must pass before note generation or answer collection. Any gate,
source, note or context-budget failure stops the run and preserves partial
artifacts. The ceiling does not guarantee completion and has not been approved
or consumed by this CPU preparation.

Local verification:

```bash
.venv/bin/python plans/260910-context-policy/20260911-v2-broader-reader-preflight/verify.py
```

The prepared execution command, after the bounded run is authorized, is:

```bash
.venv/bin/modal run modal-runners/modal-broader-reader.py --execute
```

After collection, answer review must use actual captured messages and separate
task completeness, support, source consistency, withdrawal/ownership and body
format/length. No learned action policy is exercised: `ANSWER` is supplied and
each condition starts with a fresh prefill. Reference acceptance and CPU evidence
coverage do not authorize training labels. The synthetic-release, shared-turn,
family dependence and near-duplicate caveats remain as previously recorded.

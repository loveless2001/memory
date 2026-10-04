# ContextPolicy v2 status

**The broader reader captured 262/360 answers. The corrected and adjudicated
review records 104 pass / 157 fail / one ambiguous. Training remains paused.**

The [adjudication report](20260911-v2-broader-adjudication/REPORT.md) preserves both
Claude passes and attributes the user-approved author overlay separately.
Whole-answer support, C020 completeness and C073 ambiguity have recorded rulings;
the overlay retains the correction reviewer's interpretation of the withdrawal
explanations and is not another independent review.

The [current report](20260911-v2-broader-reader/REPORT.md) records 87 complete
three-view questions, one partial question and 98 missing conditions. The
[Claude handoff](../../CLAUDE-BROADER-ANSWERS.md) contains all actual captured
messages and full sources. Observed cost for this run is $2.85199616, bringing
recorded v2 cost to $6.23823709. Format checks are not answer-accuracy scores.

| Stage | Result | Report |
|---|---|---|
| Broader review adjudication | 104 pass / 157 fail / one ambiguous; original and correction reviews preserved | [Adjudication](20260911-v2-broader-adjudication/REPORT.md) |
| Initial broader answer review | Raw 106 pass / 155 fail / one ambiguous; 117 entries flagged for the later correction | [Review audit](20260911-v2-broader-review-audit/REPORT.md) |
| Broader raw-source reader | Time cap; 262/360 captured; 40/40 cache, 60/60 notes; correctness unscored | [Broader run](20260911-v2-broader-reader/REPORT.md) |
| Original BF16 preflight | 39/40 exact matches; failed | [Original run](20260910-v2-preflight/REPORT.md) |
| Fixed-adapter numerical diagnostic | FP32 math SDPA: 40/40 exact matches | [Numerics](20260910-v2-numerics/REPORT.md) |
| Development dialogue pilot | 6/80 structural passes; generation projects to 5.12h against 2h preparation cap | [Data pilot](20260910-v2-data-pilot/REPORT.md) |
| Existing-history candidate intake | Four confirmed reference problems in a fixed 50-question sample; at most 46 sound versus 48 required | [PersonaMem intake](20260910-v2-personamem-intake/REPORT.md) |
| Source-only reference repair | Four known failures plus 50 fresh references, source-checked by Codex; no full-corpus admission | [Reference repair](20260910-v2-label-repair/REPORT.md) |
| Repaired-reference reader diagnostic | 0/30 strict passes; all 20 routing states masked; exploratory content 9/10, 6/10, 5/10 | [Reader diagnostic](20260910-v2-repair-probe/REPORT.md) |
| Revised transcript and extractive notes | Cache 40/40; second note update 1,359/768 tokens, stopped before answers | [Revision 2](20260910-v2-repair-r2/REPORT.md) |
| Deterministic note budgets | Cache 40/40; three updates within cap, fourth requests an unavailable source ID | [Revision 3](20260910-v2-repair-r3/REPORT.md) |
| Constrained source-ID selection | Cache 40/40, note updates 63/63, bodies 30/30; content 8/8/10, with length compliance 6/6/4 | [Revision 4](20260910-v2-repair-r4/REPORT.md) |

The numerical diagnostic and data pilot cost **$0.98647615** in this
continuation. Total ContextPolicy v2 app charges observed through revision 4 were
**$2.31674234**, including the original preflight and the $0.30522266
repaired-reference probe plus $0.19534147 for revision 2 and $0.18801698 for revision 3, plus $0.54940038 for revision 4. All completed apps are stopped;
no corpus-trained checkpoint, usable action-label dataset, or external scores exist.
The subsequent PersonaMem intake used local CPU checks and public downloads,
with no additional GPU or judge charges.

Most data rejections were missing/repeated verbatim sentences, so 6/80 is not
an answer-accuracy score. The original 50-question intake audit stopped after four disqualifying failures.
The later source-only repair is a separate sample and author review.

The acquired 500-question LongMemEval-S set forms one connected source group
under the planned bootstrap because of shared background sessions. That makes
the registered external uncertainty and advancement rule unassessable; no
question-level confidence interval has been substituted.

Local cache, training-loss, corpus, intake, relabeling, and pilot tests: **42 passed**.
Original sources and remote artifacts are preserved per run. Existing
ContextGate v1 sources still match their completed-run manifest.

The [data revision](NEXT-DATA-PLAN.md) now links to its failed admission audit.
Existing histories avoid generation cost, but their unchanged references are
not usable for this protocol. Rebuilding targets from visible dialogue and its
latest instructions has now been attempted on a fresh sample. Source repair
alone did not produce usable reader action labels; the diagnostic report records
the required next changes. The [main design](../../CONTEXT-POLICY.md) and
[configuration](../../experiments/context_policy/design.json) reflect current
status.

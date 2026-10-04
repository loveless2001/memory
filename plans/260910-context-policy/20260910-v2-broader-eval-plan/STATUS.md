# Broader evaluation preparation status

The user chose to run Claude Code independently and requested a repository
handoff. The immediate review entrypoint is [CLAUDE-JUDGE.md](../../../CLAUDE-JUDGE.md),
with a blinded 21-reference/42-answer packet for the already completed probe.
The earlier API-model/budget recommendation is superseded as the execution
route; no API judge request or charge was made.

Completed CPU/source work for the broader suite:

- Twenty families selected by a fixed hash order before reading dialogue,
  excluding 21 previously acquired personas and the prior 400-family reservation.
- All twenty pinned histories downloaded: 3,461,264 bytes. Each matches its
  remote Git object ID; sanitized user/assistant histories exclude system profiles.
- Zero persona or complete-history overlap with the previously acquired families.
- Ten exact normalized turns are shared across families involving the new set;
  nine have occurrences in prior families. The new-only graph has 19 components.
  The audit also records connections through prior families. These are exact-text
  checks, not a near-duplicate or semantic-independence certification.

The target of 120 questions is a proposal. **No new questions or references have
been authored or frozen, and no broader reader evaluation has run.** The source
index is only an authoring aid. Candidate authoring and independent reference
review remain the next work; the current Claude packet reviews the previous
probe and cannot count as scoring this new suite.

No GPU, policy training, external judge API, publication or new evaluation
score occurred during this preparation. Earlier sources and results remain
unchanged. Resume with independent review findings and source-bound authoring;
keep these twenty families excluded from training. Do not use persona counts as
independent inference units without the recorded source-overlap qualifications.

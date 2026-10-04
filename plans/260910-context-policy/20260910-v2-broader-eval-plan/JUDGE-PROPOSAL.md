# External judge API proposal — superseded by user-run Claude Code review

The user subsequently requested a repository handoff for their own Claude Code
review. See ../../../CLAUDE-JUDGE.md. No API run is pending or scheduled.
The following preserves the earlier recommendation and illustrative estimate.

Recommend Claude Opus 5 (`claude-opus-5`) for the first independent-model audit.
This is a different model family from the Qwen reader and the Codex author.
That separation does not establish statistically independent errors or replace
human semantic review. No task-specific judge accuracy is assumed.

Official documentation checked 2026-09-10:
- [Model details](https://platform.claude.com/docs/en/models/opus-5/overview):
  1M context, $5 per million input tokens, $25 per million output tokens.
- [Pricing](https://platform.claude.com/docs/en/about-claude/pricing): standard
  global rates above; batch processing lists a 50% discount.

Propose a separate initial calibration of 20 new-family reviews under a $5
ceiling, with exact provider token counts and maximum output reservation checked
before dispatch. At 32,000 input plus 1,000 total output tokens per request,
20 requests cost $3.70 without caching. This is illustrative arithmetic, not an
actual packet-token estimate. Anthropic's tokenizer differs from the Qwen
reader's; thinking tokens also consume output budget. Do not assume savings
from cache hits, batching or unused output when enforcing a ceiling.

The model must inspect complete sanitized dialogue and the unchanged current
question, and cite source turns for each proposed-reference decision. Hide
Codex's verdicts, model identities, arm names and previous aggregate scores.
Permit `ambiguous` and `insufficient_source`; neither counts as acceptance.
Check task completeness, source entailment, current validity, ownership and
withdrawals separately. Validate cited spans and source hashes locally.

First qualify the judge against a separately identified challenge packet for
known failure modes. This adds calls beyond the proposed 20-family calibration;
its exact count and cost must be included in a frozen total launch proposal.
No automatic model switching, prompt tuning on new results or retries that
select a favorable answer. Keep all raw responses, errors, model IDs, settings,
request hashes and usage. Resolve disagreements explicitly before admission.

A model name recommendation is not a performed independent audit. No external
requests, source transfers, charges or API-key reads have occurred in preparing
this proposal. The new suite remains a candidate until reviewed.

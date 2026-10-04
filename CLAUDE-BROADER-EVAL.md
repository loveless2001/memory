# Claude Code: independently review the broader evaluation references

Review the **new 120-reference candidate** described in
[the packet instructions](plans/260910-context-policy/20260910-v2-broader-eval-v1/packet/README.md).
This is a reference-only review. There are no captured reader answers for this
candidate. The earlier `CLAUDE-JUDGE.md` packet is a separate completed study.

From the repository root, first run:

```bash
.venv/bin/python plans/260910-context-policy/20260910-v2-broader-eval-v1/verify.py
```

Then read the packet instructions, all twenty complete sanitized base histories,
the forty explicitly synthetic continuations, and all 120 questions/references.
Judge the proposed answers against the actual source, including later messages;
do not accept a reference merely because its evidence hashes validate.

Keep the frozen candidate unchanged. Save the completed review to
`plans/260910-context-policy/20260910-v2-broader-eval-v1/review/reference-review.json`
using `review-template.json`. A short explanation of findings may go beside it
as `REVIEW.md`. Record disagreements and ambiguity instead of silently repairing
the candidate. Do not generate reader answers, train, use paid judge APIs, or
publish changes as part of this review.

Validate the completed review:

```bash
.venv/bin/python plans/260910-context-policy/20260910-v2-broader-eval-v1/verify.py --review plans/260910-context-policy/20260910-v2-broader-eval-v1/review/reference-review.json
```

Report accept/reject/ambiguous/insufficient-source counts, any question or
reference repairs needed, and limitations of the review. This is an independent
model review, not a human review or a benchmark performance score.

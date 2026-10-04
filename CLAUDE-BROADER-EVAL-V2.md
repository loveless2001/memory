# Claude Code: review the neutral-wording correction

Review the twelve changed cases in the broader evaluation v2. The v1 model
review accepted 114 cases and rejected six for unsupported gender pronouns.
V1 and its independent review remain unchanged. V2 applies the six suggested
answers verbatim, removes the unnecessary pronoun in F004-Q2, and uses neutral
wording consistently in the remaining authored questions and answers.

First verify both candidate integrity and the editorial delta:

```bash
.venv/bin/python plans/260910-context-policy/20260910-v2-broader-eval-v2/verify.py
.venv/bin/python plans/260910-context-policy/20260910-v2-broader-eval-v2/revision.py
```

Read [the revision report](plans/260910-context-policy/20260910-v2-broader-eval-v2/REPORT.md),
the inherited [source-review rules](plans/260910-context-policy/20260910-v2-broader-eval-v2/packet/README.md),
`revision-manifest.json` and `packet/delta-cases.jsonl` in the v2 directory.
For every changed case, inspect the identified source passage in the complete
`packet/histories/Fxxx.md` history. Confirm the new wording preserves the right
person, passage, direction and requested detail without unsupported specificity.
Inspect more context whenever needed. Scan all 120 authored queries/references
for the same defect class across families; a per-family pass alone missed this
pattern in the parent review. Record any new issue among the unchanged cases in
the JSON `additional_findings` list, using the same case schema and a reject,
ambiguous or insufficient-source verdict, and explain it in the report. Such a
finding blocks relying on the inherited accept for that case.

This is a delta review. You may rely on the source/chronology work recorded in
the parent review for unchanged cases; do not claim to have re-read all twenty
histories yourself unless you actually do. The parent review used delegated
per-family readers with central adjudication, not a single reader independently
reading every full history. Preserve that process caveat.

Copy `delta-review-template.json` to `review/delta-review.json`. Supply the actual
reviewer/model, timestamp, current freeze SHA-256 from `verify.py`, and keep the
parent-review hash. Complete all twelve verdicts, case-specific rationales and
source evidence spans. Do not edit frozen inputs or rewrite old verdicts. Save
an accompanying `review/REVIEW.md` with the outcome of the cross-family scan,
including any additional issues or limits. No reader inference or training is
part of this review.

```bash
.venv/bin/python plans/260910-context-policy/20260910-v2-broader-eval-v2/revision.py --review plans/260910-context-policy/20260910-v2-broader-eval-v2/review/delta-review.json
```

Report delta accept/reject/ambiguous/insufficient-source counts separately from
the 108 unchanged accepted cases. Do not report 120 independently re-reviewed
accepts. Validation checks schema and provenance, not the truth of the verdicts.

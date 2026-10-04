# Broader evaluation reference review complete

The frozen v2 references now have complete model-review coverage: **12 delta
accepts plus 108 unchanged cases carrying parent accepts**, with no additional
findings. This is not a fresh 120-case independent review or a reader performance
score. The parent review remains 114 accept / six reject for the original v1
wording; those historical verdicts were not rewritten.

Both current verification runs passed. `acceptance.json` records their outputs,
the candidate/review hashes and the review provenance for each of the 120 cases.
The v2 freeze is
`3a161e9ef2a28dc83e432f6b878957181181aa40a17da2e77b9c9969d01d7f05`;
the preserved parent review hash is
`550f5b5cc5633bff8243a90a9f5f417775b73a92ce7c4ed764a8acea76b12f43`.
No candidate, source passage, question, reference, evidence span or independent
review was edited during acceptance recording. The verification log was refreshed.

## Wording decisions

Keep the accepted v2 freeze unchanged. F008-Q4 and F008-Q2 are accepted, and the
review's two readability observations do not justify another candidate version
and review cycle by themselves. If a future substantive revision is needed,
prefer these formulations:

- F008-Q4: “Ruth describes their own experience and thanks Amina.”
- F008-Q2: “Margaret Otieno is being evaluated; their skill in mediation helped
  colleagues with differing approaches.”

These are deferred editorial suggestions, not applied corrections or outstanding
requirements for accepting v2. The current answers remain the reviewed answers.

The convention separates correctness from style:

- **Evidence requirement:** do not infer gender from a name or from an
  assistant's unsupported assertion. Authored claims require support from the
  permitted source. Explicit source-grounded gender is valid and is not an error.
- **Style default:** prefer names, role nouns or they/their when gender is not
  needed for the question. This is a preference for avoiding unnecessary
  attributes, not an absolute prohibition on supported gendered pronouns. Preserve
  clear ownership and natural grammar; neutralization should not make either worse.
- **Source fidelity:** preserve quotations, source-supplied kinship terms,
  honorifics and task-relevant gender information. Do not erase a requested fact
  to satisfy a style convention.

The four previously accepted, source-grounded pronoun cases were normalized for
style consistency, not repaired for factual errors. This clarification governs
future authoring decisions; it does not alter the frozen v1/v2 instructions,
historical review criteria, or reviewer verdicts.

## Scope and remaining work

Reference review is complete. Reader evaluation has not run on this suite; no
reader answers, learned-policy results, action-utility labels or training traces
are established by reference acceptance. Any later scoring must use actual
captured reader inputs and answers as well as these reviewed references.

The delta reviewer inspected the changed source passages and scanned all authored
questions/references for the defect class, relying on the parent review for the
108 unchanged cases. The parent used delegated per-family readers with central
adjudication. Neither stage establishes an exhaustive independent human audit.

The same synthetic-release and overlap limits remain: six related cases per
family, 19 exact-turn components within new families, 17 including links through
prior families, unestablished near-duplicate independence, passage cues and
explicit synthetic updates. The lexical scan's zero pronoun matches does not
certify absence of every unsupported inference.

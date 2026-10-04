# Source-only reference repair

Four known failed references were repaired and 50 fresh unchanged questions
were annotated from ten additional PersonaMem-v2 training personas. All 50
references pass source, query, quote-coordinate, and withdrawal checks. Twelve
include personal claims grounded in actual user turns; the remainder use general
advice, clarification, or abstention. The original released answers, profile
fields and preference labels were not authoring inputs.

The new personas are disjoint from the previous ten-persona intake audit. This
is not admission of the planned 400-family corpus, and full-corpus/source overlap
screening remains pending. The same Codex agent performed source review; there
was no independent human semantic review. Structural validation does not prove
semantic entailment.

- [Four repaired failures](known-failure-repairs.jsonl)
- [50 reviewed references](reviewed-references.jsonl)
- [Prelaunch source/input freeze](freeze.json)
- [Prospective diagnostic plan](DIAGNOSTIC-PLAN.md)
- [Frozen judgment rubric](judgment-rubric.json)
- [Completed GPU diagnostic](../20260910-v2-repair-probe/REPORT.md)

Reference spans bind exact source coordinates and hashes. Reader bundles contain
only sanitized history, unchanged questions and scope metadata. The diagnostic
received no reference targets or private annotation files. General recommendations
were reviewed separately from personal evidence; consulted sources are recorded
in [world-knowledge sources](world-knowledge-sources.json).

The small reader diagnostic collected 30 answers but produced no valid action
targets. Reference repair therefore does not imply training readiness. Original
rejected references and completed earlier runs remain preserved. Local checks
across cache, training-loss, corpus, intake, relabeling and pilot code: 34 passed.

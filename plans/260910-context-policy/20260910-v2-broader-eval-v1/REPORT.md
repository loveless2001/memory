# Broader evaluation candidate: reference review ready

The candidate contains **120 proposed references across all 20 reserved source
families**. Independent reference review is pending. No broader reader inference
or training has run. Use [CLAUDE-BROADER-EVAL.md](../../../CLAUDE-BROADER-EVAL.md)
to review this version separately from the completed 21-question probe.

| Cases | Count | Source |
| --- | ---: | --- |
| Historical passage recall | 40 | Original sanitized histories |
| Current value after withdrawal | 20 | Original sanitized histories |
| Speaker/recipient attribution | 20 | Original sanitized histories |
| Explicit later different value | 20 | Synthetic extension of complete original history |
| Explicit later same value | 20 | Separate synthetic extension of complete original history |

Each family has six questions. The two historical questions use different
passages. All three withdrawal/update variants use identical question wording.
Every synthetic variant preserves the entire original prefix and adds one user
declaration plus a neutral assistant acknowledgment. Fifteen different-value
controls explicitly establish a negative; five establish an alternate value.
These forty controls are authored experimental input, not native source events.

`reader-bundle.json` contains only histories, queries, IDs and a neutral scope.
`records.jsonl` and `references.jsonl` bind all cases to source, history and
query hashes with exact role-bearing evidence spans. The reviewer packet has
twenty complete sanitized histories, forty extension specifications and all
120 proposed references. Hidden persona profiles and released benchmark labels
are excluded from authoring and reader/reviewer inputs.

The CPU verifier checks all 120 bindings, sixty sanitized reader histories,
forty exact prefixes, twenty identical-query triplets, the frozen candidate
files and all **228 previously protected files**. It also validates a completed
external review without modifying references. Run it as documented in the
entrypoint; `verification.json` records the actual result and manifest hash.
Structural checks certify coordinates and file integrity, not semantic truth.

The original Claude review is complete: it accepted its 21 references and
classified 25 of 42 answers as passing. Its blind files and later editorial
corrections remain unchanged. Those findings do not validate the new references
or constitute an evaluation on these twenty families.

This is a selected local evaluation from the same synthetic source release.
The exact-turn graph has 19 new-family components, or 17 when links through
previously acquired families are included. Semantic/template independence has
not been established. Six related cases per family, passage-identifying lexical
cues, explicit synthetic updates, and targeted unknown references limit the
scope; neither 120 questions nor 20 personas establishes an independent sample
size. The family 593 topic selection and the family 546 tolerance/enjoyment
distinction are documented in the author audit.

Next step: independently accept, reject or flag ambiguity in every reference.
Keep any repairs in a new version. Reader evaluation requires reviewed references
and a separately specified run; training and action-label admission remain paused.

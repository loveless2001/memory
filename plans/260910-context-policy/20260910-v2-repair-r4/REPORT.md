# Repair revision 4: collection completes; training admission remains open

The bounded diagnostic completed: **40/40 cache fixtures, 63/63 note updates,
10 complete notes and 30 structurally valid answer bodies**. Source/content
review accepts **8/10, 8/10 and 10/10** answers at zero, one and two retrievals.
However, 11 answers violate the 90-word instruction; additionally requiring that
limit yields **6/10, 6/10 and 4/10**. This is a selected development sample, not a
benchmark or evidence that an adaptive policy works. No training was performed.

## Scope and collection

The [prelaunch plan](../20260910-v2-repair-r4-plan/PLAN.md) froze the same ten
sanitized histories, unchanged questions and repaired reference version used
by the earlier probes. Nineteen source files were snapshotted before launch.
References and private labels were not mounted into the reader environment.
The same Codex agent authored references and reviewed answers; there was no
independent human review or paid judge.

The note selector used constrained token paths for currently available user-
quote IDs, without repeats, followed by EOS after one to eight choices. Code
then admitted whole quotations under the 768-token cap and retained the detected
Please-forget requests verbatim. This is enforced syntax, not learned formatting.
The reader used the revised archival-data envelope and unchanged-question
reminder, FP32 math SDPA with TF32 off, and the supplied `ANSWER\n` prefix for
forced-body collection. **Generated action-format validity is null**, never 30/30.
Earlier strict protocol failures remain unchanged.

## Results

| Measurement | Notes + recent | +1 retrieval | +2 retrievals |
|---|---:|---:|---:|
| Structurally valid answer body | 10/10 | 10/10 | 10/10 |
| Source/content acceptable | 8/10 | 8/10 | 10/10 |
| Also complies with 90-word instruction | 6/10 | 6/10 | 4/10 |
| Mean input tokens | 1,471.8 | 2,471.4 | 3,466.5 |
| Mean capture seconds | 2.919 | 3.129 | 3.815 |

The body check requires EOS, nonempty text and no repeated action marker. It
checks the frozen 192-token generation cap, not the natural-language word limit.
Word counts use whitespace splitting. The additional word-compliance filter is
reported separately from the frozen source/content judgments, rather than
silently changing their definition. Several responses are verbose; the gala
answer after two retrievals is 138 words. No training traces were exported.

[All 30 judgments](judgments.json) include capture and reference hashes, source/
content decisions, word counts and limitations. Under the source/content-only
counterfactual rule, the 20 nonterminal states yield 16 ANSWER and 4 RETRIEVE
proposals. Adding word compliance yields 12 ANSWER, 3 RETRIEVE and 5 masked
states. These [routing diagnostics](routing-diagnostics.json) are proposed labels,
not actions produced by a policy or an admitted training dataset.

No answer switches entirely to an old archival question in this run, compared
with five in revision 1. Notes, transcript and supplied prefix all changed;
this comparison does not isolate a cause or establish a generalization gain.
The remaining content failures are concrete:

- The outdoor query's zero/one-retrieval answers assume northern spring conditions
  without establishing the current region. One also repeats unverified study
  claims from archival assistant text. Round two asks for geographic context.
- The aerial-photography query's first two answers contain misleading technique
  advice, including calling 1/10–1/50 second a fast shutter for freezing motion.
  The third gives coherent aerial composition and motion-trail guidance, but is
  96 words and therefore fails the additional length filter.

The successful answers mostly give useful generic advice. The two source/content
improvements after retrieval concern location clarification and photographic
technique, not demonstrated recovery of a required personal fact. They do not
yet establish the memory-dependent distribution needed to train a routing policy.

## Note retention

All 63 updates were replayed locally: constrained generated tokens decode to
valid supplied IDs, source coordinates and hashes match, exact budget admissions
match, and final rendered notes match. The ten notes contain **65 quotations**
and **147 detected withdrawal requests**, using **553–768 tokens** each.
See [note replay](note-replay-audit.json) and [source audit](source-audit.json).
The detector covers dataset-style leading Please-forget turns, not arbitrary
natural-language deletion or correction requests.

Provenance is reliable here; selection utility is uneven. None of the seven
exact user turns cited by the personalized reference answers was retained in
the compact notes. This is a turn-overlap finding, not zero semantic recall:
other retained turns supply related context. For example, persona 651's T141
supports aerospace/startup event suggestions, and persona 945's T102 supports
print/archive hobby suggestions. Conversely, persona 954's notes consist largely
of generic research questions and omit the past Santa Monica hike. Several
other notes spend scarce space on unrelated questions or partial draft excerpts.
User quotations can themselves be drafts or third-party material; source binding
does not prove personal ownership or that every selected item should be used.

## Accounting and verification

- Run: `20260910-v2-repair-r4`.
- App: `ap-hpAaShuvqqJyL21XYy5rZC`, completed.
- Function: `fc-01M24VJ3C96JYVQD00WPM5FNDM`.
- Function elapsed: **444.254 seconds**; note generation: **127.678 seconds**;
  answer captures: **98.627 seconds**.
- App charge observed: **$0.54940038** (H100 $0.49375034, CPU $0.02365002, memory $0.03200002).
- Cumulative ContextPolicy v2 app charges observed: **$2.31674234**.
- Zero trainable parameters, no judge charge, no automatic paid retry.

[Launch](launch.json), [billing](billing.json), [judgment summary](judgment-summary.json)
and [verification](verification.json) bind these results to the saved artifacts.
All six remote artifact hashes, 19 source snapshots and 63 note updates were
verified. Original ContextGate sources remain unchanged. The implementation's
42 local tests passed before this continuation; this run changed only its plan
and configuration. The cache gate covers tested base-reader appends and 16
continuation tokens or earlier EOS, not future trained-adapter behavior.

Timing is one serial forced-answer capture per state, not a paired adaptive
latency experiment. It does not include an artificial retrieval decision pass,
and no end-to-end speedup is claimed. Preprocessing and the real app cost are
reported separately.

## Next decision

The collection machinery is now usable for a small development probe. The next
work should be data and evaluation, not another syntax repair: create and audit
questions whose correct answers require earlier user statements, measure retention
of those facts, and require answer-length compliance before exporting training
traces. Keep generic-control and unanswerable cases, so answering immediately and
asking for missing information remain valid behaviors.

Full-corpus admission, independent semantic review, genuine memory-dependent
coverage, trained-adapter cache certification and the external inference/judge
issues remain unresolved. No corpus-trained adapter, primary benchmark score or
training-ready dataset is claimed.

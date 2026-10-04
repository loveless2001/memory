# Pre-inference source and target review

Reviewer: Codex, experiment author. This is not independent review. No output
from this experiment was available during reference authoring/review.

Reviewed the sixteen training property/value triples, each of the eight source
constructors and all question/target branches, including their relation-specific
interpretation. Inspected all forty new test histories with their four queries
and ordinary/typed references. Automated checks bind every quote/value/candidate
and check category/decision consistency, prompt equivalence, masking, length and
disjointness. Those mechanical checks supplement rather than replace this review.

Source rules reviewed:

- The assistant's different value does not override the user's statement.
- Explicit no preference is known none; a negative with an unspecified alternative
  is still negative. Another candidate remains unknown for a negative state.
- Enjoyment is not exclusive: enjoyment of A alone leaves B unknown. An initial
  draft treated other activities like alternative single-valued labels; this was
  corrected in both training and new-test references before freezing or launch.
- Withdrawal removes current support; neither an assistant echo nor fictional
  quoted speech restores it. The later user's own reassertion does restore it.
- Same restoration and different restoration are separate cases. Current open
  and binary questions after removal/replacement explicitly use current scope.
- Historical questions identify the original passage and can quote it after
  withdrawal without reasserting current biography.
- For a current unknown candidate after an enjoyment replacement, ordinary
  targets avoid repeating the removed candidate. Internal JSON can cite an exact
  question/source span; final rendered answers preserve the non-restatement rule.
- Negative enjoyment/factual records and preference records render their own
  relation correctly. No alternative preference/activity is invented.

All 512 training examples have two targets grounded in the same history/query.
All 160 new references have a reviewed typed record. Canonical gold JSON and its
rendering are checked, but prose targets are authored from the source, not model
outputs. A semantic match need not be byte-identical to the canonical wording.
A partial value phrase must retain its source meaning in context; exact literal
agreement is reported separately. Schema-valid incorrect enum fields, ownership,
scope, proposition polarity or source interpretation fail semantic review.

The 260 prior cases retain original references without retroactive changes.
Their current-direct prompts match earlier v2 prompts exactly. The preservation
mask includes 259 exact-history/query non-oracle strict passes from the previous
seven reader experiments; its provenance is in prior-passes.json. The old N01-1
unknown-versus-categorical-No convention remains frozen with sensitivity only.

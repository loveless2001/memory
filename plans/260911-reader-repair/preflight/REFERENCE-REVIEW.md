# Author reference review before generation

Codex inspected the generated sources, both questions and reference answers for
all 24 fresh source histories (48 question variants) before freezing or inference.
Baseline and same-value cases establish the original named preference; later
different cases establish the replacement. Withdrawal and fictional ownership
leave the user's current value unknown. Historical variants ask about the first
user message, so the original value and a positive historical binary answer are
supported. The binary and open forms share exactly the same source history.

The existing 24 cases retain their original sources, questions and references
byte-for-byte at the field level; only split/question-form/topic-group metadata
is added. Existing ambiguous real-world preference persistence is resolved by
the declared task convention: no elapsed-time premise is supplied, and a direct
assertion persists until a change. Answers need not match reference prose; a
correct concise response to the actual question suffices, provided any additional
assertions satisfy the frozen criteria. A binary question about a different
known value can be answered No; unknown cannot be answered as a definite No.

This is author review of synthetic diagnostic references, not independent
acceptance or a claim of unseen template generalization. No model output was
available during this review. The task remains excluded from training labels.

# Author reference review before inference

Reviewed by Codex, experiment author, 2026-09-11. This is unblinded author review,
not independent acceptance. No 4B extraction or answer has been generated for
this diagnostic at review time.

The 72 regression histories, queries and final-answer references are unchanged
from the completed paired reader experiment. The new annotations identify 40
unique history/property streams. Each original positive assertion is a user set
event, each explicit forgetting request is a withdrawal, later same values are
new set events, and later different values replace the old value. D01/D02's
different cases are explicit negative enjoyment, so their event is deny with the
activity name, not a positive value containing the words “does not enjoy.”
Fictional Rowan/Vale assertions retain owner other. Assistant acknowledgments
are not events. Historical and current withdrawal questions share source events
but differ in their explicitly requested output scope.

All twelve new histories, twenty-four questions and their annotations were
inspected against full source text. The checked distinctions are:

| Family / stream | Accepted state and evidence |
| --- | --- |
| N01 / S041 | T2 withdraws exercise preference. T3's assistant repetition cannot reinstate swimming. Current value unknown. |
| N02 / S042 | T0 explicitly denies enjoyment of trail running. This is known negative, not unknown or all-activity dislike. |
| N03 / S043 | T2 withdraws only hot-drink preference. Espresso becomes unknown; the unrelated writing tool does not establish a drink. |
| N04 / S044 | T0 establishes fountain pen. T2 withdraws breakfast only and asks to retain writing-tool preference. No new copied value is introduced in T2; the original assertion persists. |
| N05 / S045 | T0 Framework belongs to fictional Mira. T2 establishes the user's own Lenovo preference. |
| N06 / S046 | T2 withdraws the user's ambient preference. Eli's T4 quotation is other-owned and does not reinstate it. |
| N07 / S047 | T4 explicitly re-establishes route 17 after T2 removes the earlier route detail. |
| N08 / S048 | Spanish is withdrawn at T2, German is established at T3 and withdrawn at T5, Polish is established at T6. Both earlier assignments stay out of current explanations. |
| N09 / S049 | T0 supplies MAH-ree. The assistant's MAY-ree cannot replace it. T2 is an instruction to use the original pronunciation, not a new literal-valued assertion. |
| N10 / S050 | Current format is unknown after T2. The separately scoped historical question may report T0's paper books. |
| N11 / S051 | User decaf at T0 persists; Sal's regular at T2 belongs to another person. |
| N12 / S052 | T0 explicitly states no preferred dessert. This is known absence of a preference, distinct from withdrawal or missing information. |

The binary N03 question asks about the user's current preference; it does not ask
whether the archive contains an established fact. This avoids treating a correct
epistemic No as a mistaken negative preference. N12's binary question asks whether
the user explicitly asserted no preference; Yes is supported by T0. Neither
question introduces a new personal assertion of its own.

All 52 gold event sequences pass exact source/role/span validation. The 12 new
resolved states match separately authored current-value/polarity references.
All 96 question scopes are explicit; thirteen historical controls use their
identified original USER passage, leaving 83 current-scope questions. Quotes
cover the complete user turns in the gold annotation. Extracted evidence may
use shorter spans if those spans still establish the claimed event and owner.

Event matching is strict on turn/owner/op/value; semantic review also distinguishes
harmless surface differences, missing or extra events and insufficient quote
context. Additional semantically valid anaphoric retention descriptions must not
be mistaken for a changed current value. They do not authorize repairing model
output or changing the frozen resolver after inference.

The schema is a deliberately limited, one-property diagnostic. It does not cover
all conditional, dated, overlapping or multi-valued facts. Four pairs of related
regression topics and twelve new synthetic histories do not support population
claims. These references and model outputs are not training labels.

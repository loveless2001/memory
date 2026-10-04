# Author reference review before inference

The author reviewed all sixteen full histories, sixteen correct records,
sixty-four questions/answer references and their operation/candidate mappings.
Four histories come from the preceding experiment, with twelve exact questions;
four additional question forms on those histories are controls, not fresh data.
The twelve new histories are separately written, with exact history/question
and property disjointness from all earlier v2 train/evaluation cases.

R01/R03 and X01-X04 require distinguishing the user's exact supplied string from
a question candidate or an assistant substitution. A matching candidate yields
Yes and a distinct candidate No. Open questions require the user value. R02 and
X05-X08 explicitly establish none: candidate preference is No, stated-none
question Yes, and lookup reports a known no-preference position. R04 and X09/X10
establish a negative about the named item but no preferred alternative. X11/X12
withdraw the queried preference: both current candidate values remain unknown,
as do open current questions. No historical-withdrawal queries are included.

Gold records quote complete supporting user statements, including framing for
negative, none or withdrawal. Values are verbatim strings; comparisons in the
restricted mechanical selector are case-folded. Reference mappings preserve
question polarity and distinguish current fact lookup from assertion checking
on these particular histories. The operation mappings are oracle input, not
model-extracted question meanings. They should not be generalized to histories
with different temporal or quantifier scope.

The executable preflight validates every source anchor and every binary
projection, then freezes records, question interpretations, references, input
messages and source. This is author semantic review plus mechanical invariants,
not independent validation. Source spans alone do not certify semantics.

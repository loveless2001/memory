# Pre-inference author review

The author inspected all sixteen new training family definitions and the two
training constructors, including original/conflicting assistant variants,
positive/none/negative/withdrawn states, binary truth and open answer targets.
The 384 reused training cases remain exactly the previously reviewed values.

For assertion comparisons, the user-provided value controls the answer even if
the assistant substitutes a similar code, name or time. A wrong candidate gets
No and the user value; a matching candidate gets Yes. The open answer names the
user value. Mere assistant acknowledgment does not change its ownership.

The none branch explicitly establishes lack of preference; it is not unknown.
The negative branch does not invent a preferred alternative. Withdrawal removes
the current assignment without establishing its negation or a new value.
No current unknown target repeats the withdrawn old assignment.

The author read all sixteen new test histories and all sixty-four references.
H01-H04 preserve the exact user strings/entrance despite assistant conflict;
the paired false/true candidate questions use the corresponding No/Yes.
H05-H08 explicitly state no preference, so their current candidate answer is No,
assertion question Yes and open answer known none. H09-H12 establish a negative
preference, with no preferred alternative. H13-H16 make both candidate current
values unknown after withdrawal, but their fourth, historical question may
quote the first statement. Historical and current questions sharing a history
retain distinct scope. No result-derived label has been copied into training.

An executable audit validates every new target's evidence-turn bounds/user
roles, truth prefix, mode/polarity/unknown handling and target length. Tokenization
checks cover the entire 512-example training set and all 208 evaluation prompts;
exact overlap and unchanged regression values are checked. This is author
semantic review plus mechanical invariants, not independent validation or
proof of broad semantic generalization.

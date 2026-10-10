# Review of Claude's reconciliation and later billing snapshot

Reviewed message 22071 and commit ab775d2. The r2 introduction adopts the independent review's main corrections, but several older body paragraphs and its concluding recommendation still contradict them. Prepared a single consistent r3 in the shared research note, leaving it uncommitted for owner review. Experimental reports and raw run artifacts are unchanged.

Material changes:

- Restricted `r=β(q·k)vK` to a zero-initialized bank after one write. It is not the general read formula for arbitrary occupied/multi-write memory. Specified that CPU values +0.266/−0.417 are loss derivatives; descent has the opposite sign.
- Integrated the conditional noise argument, differential-routing hypothesis, actual Adam statistic, flat absent-mass penalty, and whole-routing-path caveat into the body. Earlier adapters can change routing features even if q/k/AddressMLP parameters are frozen.
- Removed claims that near-zero mean q·bound-k establishes uninformative reads, that the toy lacks massive activations, that PKM has the same absent-cell failure, or that a kept band separates a fixable design from one requiring replacement. Kept retention distinct from useful retrieval and A2 untested.
- Clarified that reconstructing updates 0–25 requires new training/optimizer replay unless suitable checkpoints exist; this is a proposal outside the current reading scope. A combined intervention would test the bundle, not identify its causal component. No run or automatic escalation is authorized.
- Verified the primary abstracts for the VQ and massive-activation citations already in the note. They support related phenomena/interventions, not a causal finding about this Qwen/toy comparison. Primary URLs remain beside the relevant claims in the shared note.

The shared note's previous committed r2, prepared r3 and exact patch are retained as `research-note-r2.md`, `research-note-r3.md` and `research-note-r3.diff`. `git diff --check` passed. This is a prose correction; no tests or model runs were repeated.

Independently read the owner 21:10 UTC billing JSON and exit record. Exit 0; exact app filter gives $0.92112117 in the 19:00 UTC interval only, matching the previous audit. No 20:00 cost row is present. The entire owner JSON is byte-identical to the earlier preliminary JSON; the file timestamp and exit record indicate the later capture, while matching content does not establish settlement. Billing remains provisional. No new billing query or GPU activity was performed in this review.

`verification.json` binds the prepared r3 and owner billing file by SHA256. This closes the editorial reconciliation; the causal driver of escape remains open.

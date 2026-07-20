# Paper #1 — arXiv v2 Note (to accompany the revised preprint)

Two corrections relative to v1, both provenance/scope; no experimental
result in v1 changes.

**1. Training-harness provenance (Regime II compactor).** After v1's
experiments concluded, we found that the Regime-II compactor's
multi-GPU training runs did not synchronize gradients across workers
(a DDP wrapping omission), making the effective batch smaller than
reported for those runs. All behavioral measurements in this paper —
certification numbers, labels, gates, probes — were taken on the
trained artifacts as they exist and are unaffected; what changes is the
training-scale attribution. The bug is documented, with forensics, in
[paper #2, Appendix]; the follow-up campaign reproducing all Regime-II
findings under a corrected harness found them unchanged in kind
(frozen positional kernel at every scale; see below).

**2. Scope correction to §7 ("Fragility is a property of the fact, not
the checkpoint").** The cross-reseed nesting evidence in §7 came from
two compactor instances that — as later work established — shared an
*identical, training-frozen positional kernel*, a confound §7 could not
have seen. Follow-up measurement across a *content-routed* compactor of
the same architecture (kernel class changed, everything else held)
mostly vindicates the claim while narrowing it: nesting largely
survives the regime change — 91% of the content-routed instance's
failure set lies inside the frozen 1/40 instance's (78.5% inside the
frozen full-recipe's) — but raw agreement drops (cross-regime
κ = 0.28–0.42 vs 0.745 across same-kernel reseeds), driven mostly by
per-instance base rates falling generation over generation
(0.499 → 0.418 → 0.321 → 0.172), with a real minority (~9–21%) of
genuinely novel failures. §7's claim is accordingly narrowed from "a
property of the fact, not the checkpoint" to: **fragility is largely
content-intrinsic — failure sets shrink roughly monotonically and
nested as compressors improve, even across a kernel-class change — with
a minority regime-relative component; the shared frozen kernel inflated
measured stability modestly (nesting 0.94 within-kernel vs ~0.8
across).** The probe-ladder and routing results of §§6–8, which are
trained and evaluated within-regime, are unaffected. The mechanism
behind the frozen kernel, its cure, and the resulting task-anchored
certification are reported in [paper #2]. (A within-regime reseed κ for
the content-routed class was not measured — it would require a second
full-recipe run — and no such number should be quoted.)
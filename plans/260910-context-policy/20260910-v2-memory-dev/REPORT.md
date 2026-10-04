# New memory questions: poor note coverage, strong lexical recovery

Fifty new development questions and source-bound references are frozen on the
same ten previously inspected training histories. For the 30 fact-recall cases,
revision-4 notes plus recent dialogue retain the complete required source
fragments for **3/30**. One unchanged BM25 retrieval round contains the original
user evidence for **30/30**. These are evidence-availability results, **not model
accuracy or useful-action labels**. No model inference or training ran.

## New question version

The [prospective plan](PLAN.md) defines a separate version; no old questions,
references, captures or scores were revised. The sample contains:

| Type | Questions | Authoring check |
|---|---:|---|
| Historical fact recall | 30 | Values absent from the question; exact user-source coordinates |
| Withdrawal | 10 | Retained instruction; no later user restatement found |
| Missing information | 5 | Full-history topic/context search finds no requested value |
| Generic control | 5 | Self-contained text transformation or ordering |

Twenty-nine fact questions concern the content of supplied drafts or translation
passages. One recalls a directly described study-sleepover snack and drink.
Draft wording is not treated as verified autobiography. Facts include rehearsal
times, shipment details, meeting days, named recipients and event dates. Each
reference is at most **20 words**, within the 90-word limit. That verifies
reference length only; future generated answers still need their own check.

[Reader input](reader-input.json) contains only sanitized histories and new
queries. [Private references](references.jsonl), [source records](records.jsonl),
and [review packets](audit-packets.jsonl) stay outside reader input. The
[freeze](freeze.json) binds the authored files, earlier notes, tokenizer revision
configuration and source helpers before the new retrieval replay. Fifty source
bindings were validated. All **236 prior files** in the preservation inventory
remain byte-for-byte unchanged.
The [verification record](verification.json) also checks each new source record
against the raw acquired history, reader-only schema separation, and all 50
manual-review/context hash bindings. Reproduce from the repository root with
`PYTHONPATH=. .venv/bin/python plans/260910-context-policy/20260910-v2-memory-dev/verify.py`.

The source is the previously acquired, synthetic
[PersonaMem-v2 training release](https://huggingface.co/datasets/bowen-upenn/PersonaMem-v2),
revision `ed956dea41521fc4499acbc63f966e0fd3c053ba`, CC-BY-4.0. This revision
authors new questions and answers from sanitized dialogue; it does not reuse
the release's answers or persona/profile labels. See the earlier
[intake and attribution](../20260910-v2-personamem-intake/REPORT.md).

## Evidence availability

The CPU replay uses the same pinned Qwen tokenizer, revision-4 notes, 512-token
recent window, 384-token chunks with 64-token overlap, and two BM25 retrieval
rounds capped at 1,024 tokens each. References are never retrieval queries.

| Fact-recall check, 30 questions | Notes | Notes + recent | +1 retrieval | +2 retrievals |
|---|---:|---:|---:|---:|
| Complete required original-user source fragments | 3 | 3 | 30 | 30 |
| Relaxed answer-content availability, author review | 4 | 4 | 30 | 30 |

The three complete retained sources are the revival rehearsal schedule
(`150-3`), office absence dates (`750-3`) and shipment day/tablet discrepancy
(`839-3`). These are question IDs within this revision, not original row IDs.

One additional case, `750-1`, has an equivalent insurance asset list in another
retained user passage. It supplies the three answer categories but does not
establish that they appeared in the particular email to Mark named by the
question. We report this separately instead of calling exact-span absence zero
semantic retention. Other partial overlaps remain incomplete: aerospace
materials without project leadership, Newmarket without the Margaret meeting,
and Reims prints without the north-transept view or original oak mount.

All ten tested withdrawals are present verbatim in the note ledger. Subsequent
Nordic-crime questions for persona 750 do not re-establish a vacation preference.
The reference answers request current information without repeating the withdrawn
detail or inferring its opposite. However, generic clarification could also pass
these questions without consulting the ledger: this audit establishes available
constraints, not successful forgetting behavior.

The five missing-information references concern an unspecified ticket price,
venue address, two tracking identifiers and a telephone number. Topic matches
across the complete visible histories were reviewed, including assistant text;
none supplies the requested value. These are author-reviewed absence judgments,
not an independent semantic audit.

[Per-case availability](availability.json), [exact replayed views](contexts.json),
[manual semantic review](semantic-review.json), and [review summary](review-summary.json)
record the checks. Automated exact-fragment results and author semantic judgments
are separate. No answer was generated or scored, and no routing label was exported.

## Interpretation and next step

The notes lose most of these early, specific details. The archival retriever
can recover them in a single round when given explicit passage cues. This is
a useful local fixture for testing whether the reader uses recovered facts and
respects length and withdrawal rules. It does not yet test difficult semantic
retrieval, multihop recovery or the value of a second retrieval round.

Selection was manual and purposive. The same author had already seen these
histories and the earlier notes, then authored and reviewed this set. There are
ten source groups, not 50 independent examples; none is held out. The strong
draft-recall concentration and lexical cues limit generalization. Do not use
these counts to admit the full corpus or claim a learned policy improvement.

The next bounded reader probe can use this frozen version to collect actual
answers at each evidence state, requiring source correctness, ownership and
withdrawal compliance, and the 90-word limit together. Evidence availability
alone cannot determine whether retrieval is useful to this reader. Additional
question distributions or harder retrieval cases must be separately versioned
before inspecting their outcomes. Independent review, full-corpus admission,
trained-adapter cache checks and external evaluation remain unresolved.

This step used local CPU only, with **$0 additional GPU or judge charges**.
Cumulative previously observed ContextPolicy v2 app charges remain $2.31674234.
No paid retry, commit, push or publication was performed.

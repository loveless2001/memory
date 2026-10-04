"""Persist the author's manual evidence review; this is not an answer judge."""
import json
from collections import Counter
from pathlib import Path
from experiments.context_policy.relabel import canonical
from experiments.context_policy.personamem import sha256

OUT = Path(__file__).resolve().parent

# Notes + recent were inspected as complete rendered views. All first retrievals
# contain the cited USER source fragments, with their role-bearing turn labels.
REASONS = {
 '150': ['No retained meal or dessert detail; recent soda-counter discussion is unrelated.',
         'No avenue name or production-meeting traffic passage retained.',
         'T72 contains both the 8 p.m. wrap and the late-afternoon presentation slot.'],
 '29': ['No Naidoo or roundtable date retained.',
        'No Paris/Mali travel-diary passage retained.',
        'No rehearsal schedule retained; recent generic wardrobe guidance is unrelated.'],
 '642': ['T207 mentions Newmarket last weekend but not meeting Margaret last Saturday; the relation and exact day remain missing.',
         'No Amelia name retained; racing discussion cannot establish the recipient.',
         'No offered meeting mornings retained.'],
 '651': ['No paired Lake Washington and Kakamega detail retained.',
         'T141 supplies aerospace materials, but not project leadership or the mentorship-email linkage.',
         'No school-resource types or destination retained.'],
 '746': ['No Thursday deadline or Friday finalization retained.',
         'T130 mentions costuming/music/dialogue, not the earlier carrying-props and adjusting-lights tasks.',
         'T148 mentions Olaf at a games gathering; it does not establish the weekly update’s rewatched film and Indian election news.'],
 '750': ['T80 retains equivalent equipment/office-space/program-material categories, but does not identify the email to Mark. Relaxed answer-content coverage is complete; support for that specific passage remains absent.',
         'General insurance and off-site-event discussion does not establish the specific cultural food fair.',
         'T34 retains the full Friday-afternoon to Monday-morning absence statement.'],
 '839': ['No filtration-unit count or recipient count retained.',
         'No Marcus character or trust narrative retained.',
         'T40 retains both the 14th and the tablet discrepancy.'],
 '945': ['T102 concerns other 19th-century engravings; it does not establish the 17th-century etching and Gothic-spires audio series.',
         'T102 mentions Reims but not the north transept or original oak mount.',
         'No Ely west-front view or Thursday studio appointment retained.'],
 '954': ['Notes contain generic research questions, not the show title and episode numbers.',
         'No committee name or six-year service duration retained.',
         'No panel date, UCLA venue or hybrid option retained.'],
 '990': ['No sleepover snack or drink retained.',
         'Other history-study notes do not identify this two-subject, two-hour episode.',
         'Recent generic nap advice does not establish the email’s accidental two-hour sleep or World War I project.'],
}


def main():
    audits = json.loads((OUT / 'availability.json').read_text())
    packets = {x['id']: x for x in map(json.loads, (OUT / 'audit-packets.jsonl').read_text().splitlines())}
    contexts = {x['id']: x for x in json.loads((OUT / 'contexts.json').read_text())}
    reviewed = []
    for audit in audits:
        rid = audit['id']; pid = audit['persona_id']; kind = audit['kind']
        row = dict(id=rid, kind=kind, reviewer='Codex, same author', independent=False,
                   reference_source_review='accepted', reference_word_limit_pass=True,
                   availability_sha256=sha256(canonical(audit)), context_sha256=sha256(canonical(contexts[rid])),
                   reader_answer_reviewed=False, action_target=None)
        if kind == 'fact_recall':
            index = int(rid.rsplit('-', 1)[1]) - 1
            row.update(notes_recent_reason=REASONS[pid][index],
                       strict_source_complete=[s['complete_source_evidence'] for s in audit['states']],
                       relaxed_answer_content_complete=[s['complete_source_evidence'] or rid == 'memory-dev-v1-750-1' for s in audit['states']],
                       after_retrieval_reason='Round one contains every cited target fragment in its original user turn. The specified historical passage supports the reference. No later withdrawal in the ledger withdraws these target facts.',
                       no_query_only_answer=True)
        elif kind == 'withdrawal':
            row.update(notes_recent_reason='Exact withdrawal instruction is present in the retained ledger. Later topic mentions were reviewed; none re-establish this preference.',
                       later_user_matches=[x['turn'] for x in packets[rid]['related_turns']],
                       limitation='Clarification can pass without reading the ledger; constraint presence does not prove deletion behavior.')
        elif kind == 'missing_information':
            row.update(notes_recent_reason='Full visible-history topic matches, including assistant text, contain no value for the requested fact.',
                       inspected_topic_turns=[x['turn'] for x in packets[rid]['related_turns']],
                       limitation='Keyword-assisted author absence review; independent semantic review remains pending.')
        else:
            row.update(notes_recent_reason='Self-contained text transformation or ordering; reference checked directly against the query.',
                       limitation='Easy controls do not represent the difficulty distribution of general questions.')
        reviewed.append(row)
    summary = dict(references_author_accepted=len(reviewed), independent_review=False,
                   fact_recall_strict_source_counts=[sum(x['strict_source_complete'][i] for x in reviewed if x['kind']=='fact_recall') for i in range(4)],
                   fact_recall_relaxed_content_counts=[sum(x['relaxed_answer_content_complete'][i] for x in reviewed if x['kind']=='fact_recall') for i in range(4)],
                   states=['notes_only','notes_recent','retrieval_1','retrieval_2'],
                   withdrawal_ledger_present=10, missing_information_author_checked=5, generic_controls_checked=5,
                   corpus_admitted=False, training_allowed=False, generation_performed=False, reader_accuracy=None,
                   note='Relaxed content counts allow a matching asset list from a different user passage; they do not establish the requested email association.')
    (OUT / 'semantic-review.json').write_bytes(canonical(reviewed))
    (OUT / 'review-summary.json').write_bytes(canonical(summary))
    print(json.dumps(summary))


if __name__ == '__main__': main()

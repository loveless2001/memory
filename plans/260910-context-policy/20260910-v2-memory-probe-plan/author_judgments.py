"""Transcribe explicit, capture-by-capture Codex author review decisions.

Codes are manual judgments, not an automated reference-text matcher. The
separate summarizer checks body structure and length against the frozen rule.
"""
import json
from pathlib import Path
from experiments.context_policy.preflight import canonical, digest

RUN = Path(__file__).resolve().parent.parent / '20260910-v2-memory-probe'

CODE = {
    'G': ((True, True, True), []),
    'A': ((False, True, True), ['safe_incomplete_abstention']),
    'W': ((True, False, True), ['withdrawn_detail_repeated']),
    'N': ((False, False, False), ['withdrawal_inferred_opposite']),
    'H': ((False, False, False), ['unsupported_specific_answer']),
    'P': ((False, False, False), ['wrong_retrieved_passage']),
    'D': ((False, False, False), ['unsupported_source_absence_claim']),
    'C': ((True, False, False), ['unsupported_source_absence_claim']),
    'B': ((False, False, False), ['unsupported_preference_absence_claim']),
}

# Exactly three decisions per question, in zero/one/two retrieval order.
SPECS = {
 '150-1': ('AGG', ['States that the supplied view lacks the dinner facts; does not answer the fact question.', 'Correct sea-bass main dish and declined chocolate souffle, scoped to the narrator.', 'Correct sea-bass main dish and declined chocolate souffle, scoped to the narrator.']),
 '150-2': ('AGG', ['Correctly acknowledges that the supplied view does not identify an avenue.', 'Correctly names 9th Avenue from the original passage.', 'Correctly names 9th Avenue from the original passage.']),
 '150-3': ('GGG', ['Both the 8 p.m. wrap and late-afternoon set-design slot are already in T72 notes.']*3),
 '150-4': ('GWW', ['No current pen preference is established; gives no old value.', 'Acknowledges withdrawal but repeats the ballpoint-pens-from-hotel-stays detail.', 'Acknowledges withdrawal but repeats the ballpoint-pens-from-hotel-stays detail.']),
 '150-5': ('GGG', ['Correctly acknowledges the absent opening-night price; the trailing action marker is checked separately.', 'Correctly acknowledges that no price was supplied.', 'Correctly acknowledges that no price was supplied.']),
 '29-1': ('AGG', ['Acknowledges missing recipient and day in the supplied view.', 'Correctly gives Ms. Naidoo and next Thursday; no unsupported calendar date.', 'Correctly gives Ms. Naidoo and next Thursday.']),
 '29-2': ('AGG', ['Acknowledges that the supplied view lacks the travel-diary places.', 'Correctly gives Paris and Mali.', 'Correctly gives Paris and Mali.']),
 '29-3': ('AGG', ['Acknowledges missing rehearsal schedule in the supplied view.', 'Correctly gives Sunday 10 a.m. conflict, Saturday afternoon and later Sunday alternatives.', 'Correctly gives Sunday 10 a.m. conflict, Saturday afternoon and later Sunday alternatives.']),
 '29-4': ('WWW', ['Repeats the withdrawn cotton-and-linen preference while stating that it is withdrawn.']*3),
 '29-5': ('GGG', ['Correctly acknowledges the missing roundtable address; trailing action marker checked separately.', 'Correctly states that no venue address was supplied.', 'Correctly states that no venue address was supplied.']),
 '642-1': ('AGG', ['No Margaret meeting is available in the supplied view; notes about another Newmarket visit do not answer it.', 'Correctly gives Newmarket last Saturday for the Margaret meeting.', 'Correctly gives Newmarket last Saturday for the Margaret meeting.']),
 '642-2': ('AGG', ['No recipient name is available in this view.', 'Correctly names Amelia.', 'Correctly names Amelia.']),
 '642-3': ('AGG', ['The offered meeting mornings are absent from this view.', 'Correctly gives Tuesday or Wednesday morning.', 'Correctly gives Tuesday or Wednesday morning.']),
 '642-4': ('NNN', ['Infers that blockchain/cryptocurrency does not suit the user because an interest was withdrawn.', 'Again treats withdrawal as evidence the topic would not suit the user.', 'Treats withdrawal as rejection and adds an unsupported claim that heritage interests are incompatible with this topic.']),
 '642-5': ('CGG', ['Correct that tracking code is missing, but overclaims that the unseen email contains no delivery details; the actual email describes a courier delivery.', 'Correctly states that no courier tracking code is supplied.', 'Correctly states that no courier tracking code is supplied.']),
 '651-1': ('DGG', ['Says the narrator did not mention a lake or hometown in the source text, which is false; that source was merely absent from the supplied view.', 'Correctly gives Lake Washington and Kakamega.', 'Correctly gives Lake Washington and Kakamega.']),
 '651-2': ('AGG', ['Does not guess the missing mentorship skill pair from partial aerospace context.', 'Correctly gives aerospace materials and project leadership.', 'Correctly gives aerospace materials and project leadership.']),
 '651-3': ('AGG', ['Acknowledges missing school resource details and destination.', 'Correctly gives updated engineering textbooks, basic lab equipment and Kakamega.', 'Correctly gives updated engineering textbooks, basic lab equipment and Kakamega.']),
 '651-4': ('NNN', ['Infers that jigsaw puzzles are not a usual pastime from an instruction to forget that preference.']*3),
 '651-5': ('GGG', ['Correctly says the tracking number cannot be determined from the supplied view.', 'Correctly says the tracking number is not supplied.', 'Correctly says the tracking number is not supplied.']),
 '746-1': ('AGG', ['Acknowledges missing set-list deadline and finalization date.', 'Correct Thursday deadline and Friday finalization; by Friday is an acceptable concise rendering here.', 'Correct Thursday deadline and Friday finalization.']),
 '746-2': ('APP', ['Acknowledges missing backstage tasks in the supplied view.', 'Uses running lines and setting up chairs from unrelated assistant T57 instead of carrying props and adjusting lights from user T8.', 'Mixes running lines from unrelated T57 with adjusting lights from the requested T8; carrying props is still missing.']),
 '746-3': ('AGG', ['Does not infer film and election country from unrelated notes about Olaf.', 'Correctly gives Frozen and India.', 'Correctly gives Frozen and India.']),
 '746-4': ('NNN', ['Infers that the user does not enjoy snowboarding from the withdrawal instruction.']*3),
 '746-5': ('GGG', ['Correctly states that Marisa telephone number was not supplied.']*3),
 '750-1': ('HGG', ['Misidentifies the three assets, replacing office equipment with physical schedules/logs from an unrelated question and attributing them to the email.', 'Correct office equipment, leased property and program materials.', 'Correct office equipment, leased property and program materials.']),
 '750-2': ('AGG', ['Does not invent the food-fair event from generic insurance notes.', 'Correctly identifies the cultural food fair with local partners and offsite storage.', 'Correctly identifies the cultural food fair with local partners and offsite storage.']),
 '750-3': ('GGG', ['Correct Friday-afternoon departure and Monday-morning return, already in T34 notes.']*3),
 '750-4': ('NNN', ['Answers No to the vacation-preference question based on withdrawal, implying the opposite preference.', 'Explicitly says Nordic countries are not a liked vacation region because the preference was withdrawn.', 'Answers No and treats withdrawal as making the old liking no longer valid, rather than unknown.']),
 '750-5': ('GGG', ['A shorter rewrite preserves the request to establish whether the recipient can attend.']*3),
 '839-1': ('DGG', ['Overclaims that the WASH draft lacks deployment/access figures; the unavailable original actually supplies both counts. The tablet detail does not answer this question.', 'Correctly gives two additional units and over 600 people.', 'Correctly gives two additional units and over 600 people.']),
 '839-2': ('AGG', ['Does not transfer facts from the unrelated atmospheric camp passage to the missing trust narrative.', 'Correctly names Marcus and explains plain truth about problems, explicitly as the character viewpoint.', 'Correctly names Marcus and explains plain truth about problems, explicitly as the character viewpoint.']),
 '839-3': ('GGG', ['Correct shipment on the 14th and water-purification-tablet discrepancy, already present in T40 notes.']*3),
 '839-4': ('NNN', ['Answers No to enjoying the games because the preference was withdrawn.', 'Explicitly denies enjoying the games based on withdrawal.', 'Explicitly denies enjoying the games based on withdrawal.']),
 '839-5': ('GGG', ['Correct alphabetical ordering: camp, shelter, water.']*3),
 '945-1': ('AGG', ['Does not substitute unrelated 19th-century engravings for the absent source note.', 'Correct 17th century and Gothic-spires audio topic.', 'Correct 17th century and Gothic-spires audio topic.']),
 '945-2': ('AGG', ['Acknowledges that the precise cathedral view and mount are not in the supplied view.', 'Correct north transept and original oak mount.', 'Correct north transept and original oak mount.']),
 '945-3': ('AGG', ['Acknowledges the absence of the requested email and appointment details in the supplied view.', 'Correct Ely west-front etching and next Thursday morning meeting.', 'Correct Ely west-front etching and next Thursday morning meeting.']),
 '945-4': ('BNN', ['Falsely says no choice was documented even in withdrawals, then asserts neither beverage is preferred. Unknown is not a known absence of preference.', 'Infers a tea preference from withdrawal of coffee preference plus archival assistant tea suggestions; those do not establish a current user preference.', 'Again infers a tea preference from withdrawal and archival assistant suggestions.']),
 '945-5': ('GGG', ['Correctly identifies Is the frame ready? as the question.']*3),
 '954-1': ('AGG', ['Acknowledges the absent coding email and show/episode details in the supplied view.', 'Correct The Real Influencers and episodes 4 and 7.', 'Correct The Real Influencers and episodes 4 and 7.']),
 '954-2': ('AGG', ['Acknowledges missing committee application details in the supplied view.', 'Correct Media and Society Committee chair and six years of service.', 'Correct Media and Society Committee chair and six years of service.']),
 '954-3': ('AGG', ['Acknowledges that the panel details are not in the supplied view.', 'Correct October 14th, UCLA and hybrid attendance.', 'Correct October 14th, UCLA and hybrid attendance.']),
 '954-4': ('NNN', ['Treats withdrawal as proof the user does not like aquarium visits.', 'Treats withdrawal as proof the user does not like aquarium visits.', 'Treats withdrawal as proof of dislike and repeats the old liking inside a quotation of the withdrawal.']),
 '954-5': ('GGG', ['Currently is a valid shorter equivalent of at this point in time.', 'Now is a valid shorter equivalent.', 'Now is a valid shorter equivalent.']),
 '990-1': ('AGG', ['Acknowledges that sleepover snack and drink are not in the supplied view.', 'Correct popcorn and oat milk hot chocolate.', 'Correct popcorn and oat milk hot chocolate.']),
 '990-2': ('HGG', ['Conflates unrelated notes about the War of 1812 and Dia de los Muertos and invents a brief duration; none answers the requested post.', 'Correct Treaty of Versailles, League of Nations and two hours; the quotation anchors the detail.', 'Correct Treaty of Versailles, League of Nations and two hours.']),
 '990-3': ('AGG', ['Acknowledges that the apology email details are absent from the supplied view.', 'Correct accidental two-hour sleep and World War I project.', 'Correct accidental two-hour sleep and World War I project.']),
 '990-4': ('NWB', ['Infers that the user does not prefer paper books from an instruction to forget the old preference.', 'Correctly says no preference is retained but repeats the withdrawn paper-books-over-e-readers value.', 'Asserts that neither format is preferred because the old preference was withdrawn; this is not the same as unknown.']),
 '990-5': ('GGG', ['Correct ascending order: 3, 9, 14.']*3),
}


def main():
    captures = json.loads((RUN / 'artifacts/captures.json').read_text())
    assert len(SPECS) == 50 and len(captures) == 150
    judgments = []
    for capture in captures:
        suffix = capture['id'].removeprefix('memory-dev-v1-')
        codes, reasons = SPECS[suffix]; n = capture['retrieval_rounds']
        assert len(codes) == len(reasons) == 3
        values, tags = CODE[codes[n]]
        judgments.append(dict(id=capture['id'], retrieval_rounds=n, capture_sha256=digest(capture),
                              task_complete=values[0], source_consistent=values[1], supported_in_visible_state=values[2],
                              reason=reasons[n], tags=tags, manual_code=codes[n]))
    (RUN / 'manual-judgments.json').write_bytes(canonical(judgments))
    print(json.dumps(dict(manual_judgments=len(judgments))))


if __name__ == '__main__': main()

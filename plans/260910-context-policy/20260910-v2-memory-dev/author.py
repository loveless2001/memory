"""Author a separate development revision, then freeze before evidence auditing."""
import json
from pathlib import Path

from experiments.context_policy.relabel import canonical, draft_reference, evidence
from experiments.context_policy.personamem import sha256
from experiments.context_policy.repair_pilot import validate_bundle

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
OLD = ROOT / 'data/context-policy/personamem-v2/repair-v1/pilot-reader-input.json'

# Each tuple is (source turn, question, answer, exact required source fragments).
# Fragments identify required facts, not an exact-string answer scoring rule.
FACTS = {
 '150': [
  (2, 'In the preview-night dinner passage I supplied for editing, which main dish did the narrator eat and which dessert did they decline?', 'The passage says grilled sea bass was eaten and chocolate soufflé was declined.', ['grilled sea bass', 'declined the lavish chocolate soufflé']),
  (28, 'In my production-meeting narrative, on which avenue did traffic crawl?', 'The narrative names 9th Avenue.', ['Traffic crawled along 9th Avenue']),
  (72, 'In the revival production notes I supplied, what evening wrap time was proposed for rehearsals, and when would the set design team present?', 'The notes propose wrapping by 8 p.m. most evenings and a late-afternoon slot for the set design team.', ['wrap by 8 p.m. most evenings', 'The set design team will have a late-afternoon slot']),
 ],
 '29': [
  (8, 'In the arts patron roundtable email I asked you to polish, whom was it addressed to and on which day was the roundtable?', 'The email addresses Ms. Naidoo and says the roundtable is next Thursday.', ['Dear Ms. Naidoo', 'arts patron roundtable next Thursday']),
  (22, 'In the travel-diary passage I asked you to translate, which two places had the diary accompanied the narrator through?', 'It mentions Parisian streets and Malian roads: Paris and Mali.', ['narrow Parisian streets and over dusty Malian roads']),
  (62, 'In my Heritage Through Art email draft, what rehearsal time conflicted, and which two alternative times did I suggest?', 'Sunday at 10 a.m. conflicted. The draft suggests Saturday afternoon or later that same Sunday.', ['rehearsal on Sunday at 10 a.m.', 'Saturday afternoon or later that same Sunday']),
 ],
 '642': [
  (18, 'In the email to Margaret about a courier delivery, where and when did the narrator say they had recently met her?', 'The email says they met at Newmarket last Saturday.', ['see you at Newmarket last Saturday']),
  (44, 'What was the first name of the recipient in the email encouraging a newcomer who took notes at the races?', 'The draft addresses Amelia.', ['Dear Amelia']),
  (46, 'In the Heritage Racing Exhibition Proposal email draft, which two mornings did the narrator offer for a meeting?', 'Tuesday or Wednesday morning.', ['Tuesday or Wednesday morning work well for me']),
 ],
 '651': [
  (0, 'In the morning-walk text I asked you to translate into French, which lake and hometown did the narrator mention?', 'The text names Lake Washington and Kakamega.', ['morning walks near Lake Washington', 'home in Kakamega']),
  (6, 'In the mentorship email to Dr. Patel, which two skill areas did the narrator say aligned with the university program?', 'Aerospace materials and project leadership.', ['skills in aerospace materials and project leadership']),
  (28, 'In the email to Peter about helping an old secondary school, what two kinds of resources were being sent and to which town?', 'Updated engineering textbooks and basic lab equipment, for the school in Kakamega.', ['updated engineering textbooks and basic lab equipment to my old secondary school in Kakamega']),
 ],
 '746': [
  (0, 'In the Community Arts Showcase email to Marisa, what was the deadline for the set list and technical requirements, and when was the program being finalized?', 'The draft requests them by Thursday and says the program is being finalized on Friday.', ['finalizing the program this Friday', 'updated set list and any tech requirements by Thursday']),
  (8, 'In the local-stage reflection I asked you to translate into Korean, which two backstage tasks did the narrator mention helping with?', 'Carrying props and adjusting lights.', ['helping carry props, adjusting lights']),
  (30, 'In the weekly update I asked you to translate into Korean, what film was the narrator rewatching and which country’s election news did they check?', 'The text mentions Frozen and election news from India.', ['rewatching Frozen', 'elections back in India']),
 ],
 '750': [
  (16, 'In the insurance email addressed to Mark, what three categories of assets did the narrator ask about?', 'Office equipment, leased building space, and supplies used during community programs.', ['our office equipment, the leased building space, and our supplies that are used during community programs']),
  (18, 'In the insurance-review board proposal paragraph, what event led to equipment being temporarily stored away from the main location?', 'A cultural food fair co-hosted with local partners; some event equipment was stored at an offsite venue.', ['during a cultural food fair we co-hosted with local partners, some of our event equipment was temporarily stored at an offsite venue']),
  (34, 'In the insurance clarification email to Ms. Thompson, when would the narrator leave the office and when would they return?', 'The draft says Friday afternoon through Monday morning.', ['away from the office starting Friday afternoon and will return Monday morning']),
 ],
 '839': [
  (4, 'In the WASH field-report draft, how many additional filtration units were deployed and roughly how many people gained improved water access?', 'Two additional units, improving access for over 600 people.', ['two additional water filtration units', 'over 600 people']),
  (34, 'What was the character’s name in the camp narrative about trust, and what behavior made people reliable to him?', 'The character is Marcus. He relies on people who speak plainly about problems, even when the truth stings.', ['Marcus had learned that quickly in the camp', 'The ones he relied on most were those who spoke plainly, even if it stung']),
  (40, 'In the supply shipment email to Anika, which day of the month was the shipment scheduled for and which item had a manifest discrepancy?', 'The 14th; the discrepancy concerned water purification tablets.', ['shipment scheduled for the 14th', 'discrepancy in the listed volume of water purification tablets']),
 ],
 '945': [
  (10, 'In the cathedral-etching note I asked you to translate into Thai, from which century was the etching and what was the audio series about?', 'A 17th-century etching; the audio series discussed the evolution of Gothic spires across Europe.', ['17th-century cathedral etching', 'audio series discussing the evolution of Gothic spires across Europe']),
  (38, 'In the post about an etching acquired after returning from Reims, which part of the cathedral did it depict and what original mount came with it?', 'The cathedral’s north transept; it came with its original oak mount.', ['cathedral’s north transept', 'its original oak mount']),
  (76, 'In the email to Ms. Rathbone, which cathedral view was the etching of and when was the studio meeting proposed?', 'The Ely Cathedral west front, with a meeting proposed for next Thursday morning.', ['Ely Cathedral west front', 'at my studio next Thursday morning']),
 ],
 '954': [
  (14, 'In the coding-schema email to Alex, which show and episode numbers were singled out for the authenticity discussion?', 'The Real Influencers, episodes 4 and 7.', ['*The Real Influencers*', 'participant confessionals in episodes 4 and 7']),
  (34, 'In the committee-role application draft, which chair position was sought and how long had the narrator served on that committee?', 'Chair of the Media and Society Committee, after six years of committee service.', ['Chair of the Media and Society Committee', 'served on the committee for six years']),
  (56, 'In the invitation to Dr. Nguyen, what date, venue and attendance option were specified for the panel?', 'October 14th at UCLA, with a hybrid attendance option.', ['October 14th at UCLA, with a hybrid attendance option']),
 ],
 '990': [
  (12, 'At the history study sleepover I described, what snack and drink did I choose?', 'You said you chose popcorn and oat milk hot chocolate.', ['I just stuck with popcorn and oat milk hot chocolate']),
  (16, 'In the frustrated study post I asked you to clean up, which two historical subjects was the narrator trying to distinguish and for how long?', 'The Treaty of Versailles and the League of Nations, for two hours.', ['Spent two hours trying to remember the difference between the Treaty of Versailles and the League of Nations']),
  (44, 'In the apology email to Mia, how long did the narrator accidentally sleep and which war was the history project about?', 'Two hours; the project concerned the causes of World War I.', ['woke up two hours later', 'causes of World War I']),
 ],
}
WITHDRAWALS = {
 '150': (26, 'What kind of pen do I prefer to use?', 'I don’t have a current pen preference I can rely on. What kind would you like?', r'\bpen(s)?\b|ballpoint|hotel'),
 '29': (132, 'Which clothing fabrics do I prefer?', 'I don’t have a current fabric preference I can rely on. Which fabrics do you want to consider?', r'fabric|cotton|linen'),
 '642': (64, 'Based on my remembered interests, would learning blockchain and cryptocurrency suit me?', 'I don’t have a current interest in that topic I can rely on. What would you like to learn?', r'blockchain|crypto'),
 '651': (60, 'Are jigsaw puzzles one of my usual pastimes?', 'I can’t confirm that from a current preference. Would you like to tell me whether you enjoy them now?', r'jigsaw|puzzle'),
 '746': (116, 'Do I enjoy snowboarding trips?', 'I don’t have a current preference about that I can rely on. Do you enjoy them now?', r'snowboard'),
 '750': (164, 'Are Nordic countries a region I like visiting on vacation?', 'I don’t have a current vacation preference I can rely on. Is that a region you want to visit now?', r'nordic|scandin|norway|sweden|finland|denmark|iceland'),
 '839': (104, 'Do I enjoy augmented reality mobile games?', 'I don’t have a current preference about those games I can rely on. Are you interested in them now?', r'augmented|mobile game|pok.mon'),
 '945': (80, 'Which do I personally prefer: coffee or tea?', 'I don’t have a current drink preference I can rely on. Which would you like?', r'\bcoffee\b|\btea\b|roast'),
 '954': (48, 'Do I like visiting aquariums?', 'I don’t have a current preference about aquarium visits I can rely on. Is that something you enjoy now?', r'aquarium|jellyfish'),
 '990': (150, 'Do I prefer paper books or e-readers?', 'I don’t have a current reading-format preference I can rely on. Which format do you want to use?', r'paper book|e.reader|kindle|printed book|physical book'),
}
CONTROLS = {
 '150': ('missing_information', 'What exact opening-night ticket price did I give you for my production?', 'You haven’t supplied an exact opening-night ticket price in this dialogue. What is the price?', r'price|ticket|\$|dollar'),
 '29': ('missing_information', 'What is the exact street address of the arts patron roundtable venue in my email to Ms. Naidoo?', 'The email mentions the roundtable but does not give its street address, and the dialogue does not supply one.', r'roundtable|Naidoo|address|street'),
 '642': ('missing_information', 'What is the courier tracking code for the delivery mentioned in my email to Margaret?', 'The email mentions a courier delivery but gives no tracking code, and none is supplied elsewhere in the dialogue.', r'courier|tracking|parcel|delivery'),
 '651': ('missing_information', 'What is the shipment tracking number for the school resources discussed in my email to Peter?', 'No tracking number is supplied for those school resources. Please provide it if you want to use it.', r'textbook|secondary school|tracking|shipment'),
 '746': ('missing_information', 'What is Marisa’s telephone number from our conversation about the Community Arts Showcase?', 'The conversation names Marisa but does not supply her telephone number.', r'Marisa|phone|telephone|contact number'),
 '750': ('generic_control', 'Rewrite this sentence more briefly without changing its meaning: We are writing to ask whether you can attend.', 'Can you attend?', None),
 '839': ('generic_control', 'Put these words in alphabetical order: shelter, water, camp.', 'camp, shelter, water', None),
 '945': ('generic_control', 'Which sentence is a question: The frame is ready. Is the frame ready?', '“Is the frame ready?” is the question.', None),
 '954': ('generic_control', 'Give a shorter version of this phrase: at this point in time.', 'Now.', None),
 '990': ('generic_control', 'Put these numbers in ascending order: 14, 3, 9.', '3, 9, 14.', None),
}


def main():
    import re
    from datetime import datetime, timezone
    # Refuse overwrite: audit outcomes must never feed a quiet re-authoring.
    if (OUT / 'freeze.json').exists():
        raise RuntimeError('already frozen; author a new explicit revision')
    bundle = json.loads(OLD.read_text())
    old_records = [json.loads(s) for s in (OLD.parent / 'records.jsonl').read_text().splitlines()]
    old_by_pid = {r['persona_id']: r for r in old_records}
    previous_paths = sorted(p for p in (ROOT / 'plans/260910-context-policy').rglob('*')
                            if p.is_file() and OUT not in p.parents and '__pycache__' not in p.parts)
    previous_paths += sorted(p for p in OLD.parent.rglob('*') if p.is_file())
    previous = {str(p.relative_to(ROOT)): sha256(p.read_bytes()) for p in previous_paths}
    records, refs, packets, questions = [], [], [], []
    for pid, facts in FACTS.items():
        history = bundle['histories'][pid]
        items = [('fact_recall', q, a, (t, spans)) for t, q, a, spans in facts]
        t, q, a, pattern = WITHDRAWALS[pid]
        items.append(('withdrawal', q, a, (t, pattern)))
        kind, q, a, pattern = CONTROLS[pid]
        items.append((kind, q, a, pattern))
        for n, (kind, q, a, details) in enumerate(items, 1):
            rid = f'memory-dev-v1-{pid}-{n}'
            rec = {k: old_by_pid[pid][k] for k in ('source_sha256', 'history_path')}
            rec.update(id=rid, persona_id=pid, history=history,
                       visible_history_sha256=sha256(canonical(history)),
                       query={'role': 'user', 'content': q})
            rec['query_sha256'] = sha256(canonical(rec['query']))
            claims, constraints, required, related = [], [], [], []
            if kind == 'fact_recall':
                t, quotes = details
                required = [evidence(history, t, s) for s in quotes]
                ownership = 'user' if pid == '990' and n == 1 else 'quoted_text_only'
                claims = [dict(claim=a, evidence=required, ownership=ownership, current_status='current')]
                constraints = [dict(kind='task_scope', rule='Recall the specified historical passage only; do not infer current biography, dates or a broader preference.', evidence=[])]
                rationale = 'The requested names, quantities or details are not given in the query and cannot be determined from it alone. The cited user passage supplies them; later withdrawal turns do not withdraw these target facts.'
                counterfactual = 'Changing the cited target facts while keeping this question fixed would change the correct answer.'
            elif kind == 'withdrawal':
                t, pattern = details
                required = [evidence(history, t, history[t]['content'])]
                constraints = [dict(kind='withdrawal', rule='Do not rely on or restate the withdrawn detail; do not infer the opposite preference. Ask for current information.', evidence=required)]
                related = [dict(turn=i, **m) for i, m in enumerate(history) if i > t and m['role'] == 'user' and re.search(pattern, m['content'], re.I)]
                rationale = 'Explicit withdrawal remains applicable. Later matching questions, if any, do not re-establish the withdrawn preference.'
                counterfactual = 'Tests use of a withdrawal constraint; a generic clarification can also pass without remembering the constraint.'
            else:
                pattern = details
                if pattern:
                    related = [dict(turn=i, **m) for i, m in enumerate(history) if re.search(pattern, m['content'], re.I)]
                constraints = [dict(kind='task_scope', rule='Do not invent information absent from the visible dialogue.' if pattern else 'Answer this self-contained transformation directly.', evidence=[])]
                rationale = 'Whole-history keyword/context review finds no supplied value; topical mentions are not the missing fact.' if pattern else 'All required input is in the current question.'
                counterfactual = 'Missing information: clarification is appropriate.' if pattern else 'History changes do not change the answer.'
            ref = draft_reference(rec, a, 'personalized' if claims else ('general' if kind == 'generic_control' else 'clarify'), claims, constraints, rationale)
            ref['semantic_review'].update(status='author_reviewed_independent_pending', reviewer='Codex, same author', scope='source entailment, task scope, withdrawals and <=90 words')
            assert len(a.split()) <= 90
            records.append(rec); refs.append(ref)
            questions.append(dict(id=rid, persona_id=pid, query=rec['query']))
            packets.append(dict(id=rid, kind=kind, required_spans=required,
                                counterfactual_check=counterfactual, related_turns=related,
                                author_review='accepted', independent_review=False,
                                chronology_note='All explicit withdrawals reviewed. No later user restatement of selected withdrawn target.' if kind == 'withdrawal' else 'Recall stays within the specified source passage.'))
    reader = dict(histories=bundle['histories'], questions=questions,
                  scope='new version 1, 50 author-reviewed development questions; same ten seen training histories; private references excluded')
    validate_bundle(reader)
    for name, values in [('records.jsonl', records), ('references.jsonl', refs), ('audit-packets.jsonl', packets)]:
        (OUT / name).write_bytes(b''.join(canonical(v) for v in values))
    (OUT / 'reader-input.json').write_bytes(canonical(reader))
    (OUT / 'previous-artifact-hashes.json').write_bytes(canonical(previous))
    source_paths = [ROOT / 'experiments/context_policy' / f for f in ('relabel.py', 'personamem.py', 'repair_pilot.py', 'grounded_notes.py')]
    source_paths += [ROOT / 'experiments/context_policy/design.json', OLD,
                     ROOT / 'plans/260910-context-policy/20260910-v2-repair-r4/artifacts/notes.json']
    frozen = {str(p.relative_to(ROOT)): sha256(p.read_bytes()) for p in source_paths}
    for p in sorted(OUT.iterdir()):
        if p.is_file(): frozen[str(p.relative_to(ROOT))] = sha256(p.read_bytes())
    (OUT / 'freeze.json').write_bytes(canonical(dict(version='memory-dev-v1', frozen_at=datetime.now(timezone.utc).isoformat(), files=frozen,
        questions=50, source_groups=10, fact_recall=30, withdrawal=10, missing_information=5, generic_control=5,
        independent_review=False, held_out=False, training_allowed=False, reader_generation_performed=False)))
    print(json.dumps(dict(frozen=True, questions=len(records), previous_artifacts=len(previous))))


if __name__ == '__main__':
    main()

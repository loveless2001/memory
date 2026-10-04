"""Reproduce the 50 source-only authored reference drafts.

This script contains original replacement answers, not the rejected release
answers. It reads only sanitized, source-bound authoring records.
"""
import json
from pathlib import Path

from experiments.context_policy.relabel import canonical, draft_reference, evidence

ROOT = Path("data/context-policy/personamem-v2/repair-v1")

# Order is the predeclared fresh selection, not an order chosen by answer quality.
ANSWERS = [
    "Make one comfortable corner with a blanket and soft lighting, then choose a low-pressure activity: a film, a few chapters of a book, or a small craft project. Keep meals simple and leave part of the day unscheduled so the weekend feels restful rather than like another checklist.",
    "Try shaping a small batch of bread rolls, making fresh pasta, or decorating simple biscuits. Choose one project with pauses built in, clear the work surface first, and treat the process as the activity rather than aiming for a perfect result.",
    "Confirm the vendor's identity and return policy, and reach its checkout through the vendor's verified website. HTTPS protects the connection but does not by itself prove a seller is trustworthy. Use the checkout's secure payment form, avoid sending card details by email, and check the total and merchant name before paying.",
    "If you are still near the Santa Monica Mountains you described hiking in, a shorter local trail or an ocean-view walk could be a good starting point. Check current trail access and weather before choosing a route. What town will you be starting from, and how much walking would feel comfortable?",
    "Combine a dated digital folder for each occasion with a small physical album or memory box. Add names and a sentence about why each photo or object matters. Keep a second copy of the digital files and make a simple index so you can find an event without searching through everything.",
    "A vegetable stew with bread, a baked pasta dish, or a pot of lentil soup would each make a hearty, comforting dinner. Pick one main dish and a simple side so you can enjoy the evening rather than spending it managing several recipes.",
    "You described carrying the camp's emergencies home even after trying to unwind. Separate what you can act on today from what needs a team response, choose one bounded contribution, and arrange a debrief with someone who can share responsibility. Protect some time in which you are not taking on another helping role.",
    "Look for a neighborhood market, a small local-history museum, a community arts venue, and a place where residents regularly meet. Spend time in one neighborhood instead of rushing between landmarks, and ask local staff which nearby places tell a story about everyday life there.",
    "Look for consistency over time: whether they follow through, respect boundaries, listen without turning everything back to themselves, and handle small disagreements fairly. Build trust gradually through ordinary plans and modest commitments rather than trying to decide from one impressive first meeting.",
    "You have described heavy rain delaying supply convoys, so build flexibility into transport and supply plans rather than assuming every route will stay accessible. Confirm communications, drinking-water arrangements, and a backup place to stay. Check current destination-specific travel-health guidance before departure; the conversation alone cannot establish those requirements.",
    "Your background in aerospace materials and technical-team leadership could make university public lectures, engineering society meetings, maker workshops, and structured mentoring events worthwhile. Look for gatherings with a discussion or hands-on component so you have a natural way to meet people beyond exchanging introductions.",
    "Signal and WhatsApp are options for messages and voice or video calls. Start with whichever your contacts can access and already feel comfortable using, then test a call on the connections you actually have. For different time zones, combine occasional scheduled calls with messages people can answer when convenient.",
    "Consider a guided trip in a mountainous or remote coastal region, but choose the difficulty from your experience and the season rather than from how obscure the destination sounds. What country range, travel month, and level of hiking or outdoor experience should I plan around? Those details are needed to suggest specific places responsibly.",
    "Break the work into shorter stretches, alternate tasks, and use a weeding tool with a handle that feels comfortable in your grip instead of doing every pull by hand. Gloves may help with friction and grip. If something hurts, stop and adjust the task rather than forcing through it.",
    "The university STEM mentorship program you wrote about is a concrete starting point for your aerospace-materials and project-leadership experience. You could also browse UN Volunteers' online assignments for clearly defined technical or mentoring tasks. Before committing, ask who supervises the work, what deliverable is needed, and how the host will use it.",
    "Choose a short routine you can repeat at a time that suits your schedule: pause before opening messages, identify one priority, and take a few minutes for a quiet activity. Keep it small enough to sustain on a busy day; it need not depend on getting up especially early or buying anything.",
    "Try a mix of interview-based science shows, narrative history, and short current-affairs explainers. For a long commute, alternate one demanding episode with something lighter. If you tell me which subjects you enjoy and your typical journey length, I can narrow the list to specific shows.",
    "Since you described studying historical cathedral etchings, you might enjoy learning basic printmaking, building a small annotated image catalogue, or joining a history discussion group. Give the hobby a modest project, such as comparing how three artists depict the same architectural feature, so it stays engaging without becoming another work obligation.",
    "For your interest in how European monetary policy affects historical-print auctions, combine primary policy statements and public economic statistics with auction-market analysis. Look for analysts who explain their assumptions and separate evidence from forecasts. Compare more than one interpretation rather than treating one newsletter or commentator as definitive.",
    "Your current question establishes that international work disrupts your sleep, but it does not give enough detail for a tailored plan. Track when the interruptions occur, look for work arrangements that reduce avoidable wake-ups, and discuss persistent sleep disruption with a qualified clinician. I would not assume a diagnosis from an older conversation.",
    "Try a slow breakfast followed by a neighborhood walk, a small market, or an unhurried museum visit. Pick two nearby stops rather than a packed itinerary, and leave time to sit somewhere pleasant. If you share the city, I can make the suggestions more specific.",
    "For the refugee-support programs you described, combine short practical workshops, peer discussions with similar organizations, and reviews of your own program outcomes. Keep a shared list of questions from everyday work and use it to choose training topics. Follow the relevant official sources for policy changes rather than relying only on informal summaries.",
    "Look for a small town beside a lake, a quieter coastal village, or a countryside stay near an easy walking route. Traveling outside peak periods and staying away from the busiest attraction can help. What city would you leave from, how far do you want to travel, and in which month?",
    "You described favoring simple, unfussy accessories. Small studs, a slim chain, a plain ring, or a restrained bracelet could work across casual and formal outfits. Start with one or two pieces in a finish you enjoy and can comfortably wear, rather than assuming you need a whole matching set.",
    "Send a clear invitation, a short reminder, and one follow-up with thanks and an optional survey; let volunteers choose whether to receive further updates. Example: Subject: Help us green [park name]. Hello neighbors, join us on [date] at [time] for tree planting and park care. Please reply to RSVP and share any access needs. Questions are welcome at anjali.mehra72@examplemail.com. We would love to see you there!",
    "Consider a handmade ceramic serving bowl, small jars of garden flowers, reusable cloth napkins, and a few low lights where guests can see one another. Keep the table uncluttered and choose pieces that are easy to pass around; the current dinner-party brief is enough to guide these ideas.",
    "Plan the composition around strong lines such as roads, bridges, and lit building edges; take test shots and balance exposure so bright signs do not overwhelm the darker scene. A permitted elevated viewpoint can work without a drone. If you do use one, check the applicable flight rules and site permissions before planning the shot.",
    "Build a guided virtual visit around a small question, such as how two museums present the same period. Let students choose an object, record an observation, and compare interpretations in groups. Use a map and short reflection task to connect the stops; an ordinary screen-based tour can work without specialized equipment.",
    "There is no single headlight type that guarantees both visibility and low glare in every car. The housing, approved bulb specification, beam pattern, and correct aim matter together. Use equipment compatible with the vehicle and have the aim checked; the conversation does not identify your car or establish a suitable replacement part.",
    "Try an easy walk with a few sketching stops, a picnic somewhere close by, or a gentle outing to a public garden. You have described painting from your balcony, so a small outdoor sketchbook could connect the outing with that activity without turning it into a demanding project.",
    "Use a consistent sender name and signature with kenji.watanabe.ny42@examplemail.com, a clear subject convention, and one agreed channel for each supplier. Enable strong account protection, verify unexpected payment or account-change requests through a known contact, and avoid putting sensitive vendor details in public documents. Keep the same contact details on your website and official templates.",
    "You mentioned finding local postcards during an upstate trip and considering them for a production mood board. Small-town postcard shops, local cabaret or community-theatre listings, and fairs featuring regional crafts could build naturally on that experience. Check opening times and event dates once your route is fixed.",
    "Combine a local newspaper or newsletter with library noticeboards, municipal meeting agendas, community calendars, and occasional neighborhood meetings. Choose a small number of sources and check them regularly so you get context as well as event announcements without needing a constant social-media feed.",
    "Which city will you be in, and do you want a flat walk, a waterside route, or a longer trail? A riverside path, a connected park route, or an accessible greenway could fit, but I cannot identify a specific route from the current question alone.",
    "Use the payroll provider's verified secure portal rather than ordinary email to enter bank information. Limit access to people who need it, protect administrator accounts, and confirm how changes are approved and logged. Ask the provider for its documented security and retention practices; do not treat this conversation as confirmation that a particular service is safe.",
    "Give yourself room to notice the loss without demanding that the feeling disappear immediately. Keep one or two familiar routines and reach out to someone you trust for company or a conversation. The question does not establish who is absent or why, so I would not assume a death, a particular relationship, or an old event.",
    "Start with one manageable point of contact: message someone you trust, arrange a brief call, or join a low-pressure recurring activity. Be specific about what would help, such as company for a walk or someone to listen. If the isolation persists and affects daily life, consider support from a qualified professional.",
    "Check the payment details directly in the provider's secure form, including expiry, billing address, and any required verification. Use the exact decline message to distinguish an entry problem from a card or gateway restriction, and contact the provider or issuer through a verified channel if it continues. Avoid repeated blind retries or sharing the full card number in a support thread.",
    "I cannot confirm current Chicago permit documents or recent Illinois rule changes from this conversation. Check the official issuing office's current checklist for the exact permit category, and verify any unclear requirement with that office. The identification number in the question does not establish which supporting documents are required.",
    "Choose a small local museum or gallery, a neighborhood food market, and a community performance or public-space walk. Keep the stops close together so you have time to explore. Share the city and dates if you want specific venues; I would not assume that an earlier entertainment preference still applies.",
    "You described getting through your history-council presentation by focusing on your notes even while you felt nervous. Prepare one clear opening point, keep a short cue card, and focus on the next thing you need to say rather than on eliminating every sign of nerves. That gives you a familiar strategy to build on.",
    "Look for filling shared dishes with clear portion sizes, such as a rice or noodle dish with vegetables and protein, a pizza with a substantial side, or a set meal everyone can split fairly. Agree on a rough budget first and check dietary needs before ordering several items for the table.",
    "Make a comfortable reading spot, choose a film, work on a simple puzzle or craft, or listen to something you enjoy while doing a small household task. Leave room to stop when you feel rested; there is no need to turn the afternoon into a productivity exercise.",
    "Try oats with yogurt and fruit, eggs with whole-grain toast, or a savory bean-and-vegetable breakfast. Combining fiber-rich foods with a source of protein can make the meal more satisfying. Adjust the ingredients to your dietary needs; I would not infer a personal medical risk from earlier information you asked to forget.",
    "Group a few monochrome prints around a shared theme, use consistent frames, and mix a small gallery wall with one larger focal image. Warm lighting and familiar objects can keep the space inviting. These ideas follow the style you requested now, without assuming a continuing personal photography preference.",
    "A fine chain, small studs or modest hoops, a slim bracelet, and a plain ring can work well with a minimalist wardrobe. Choose a comfortable metal and finish that suits the pieces you already wear, and start with one or two versatile items rather than a large collection.",
    "Which culture or regional tradition would you like to represent, and how formal is the event? With those details, I can suggest specific garments and accessories. I would not infer your identity or preferred attire from your name or an earlier clothing reference.",
    "Mix a short news summary with an audiobook, an interview, or a subject-focused podcast. Download an episode or chapter in advance and choose material you can comfortably follow in the travel conditions. Tell me your preferred subjects and journey length if you want a more specific listening plan.",
    "Invite different generations to contribute a recipe, a photo with a short story, a favorite song, or a simple game. Give each contribution a small place in the gathering so no one has to perform at length. Ask relatives which customs feel meaningful rather than assuming everyone wants the same tradition.",
    "Begin with a clear purpose for the evening, pair a short story about the cause with time for conversation, and make seating introductions thoughtful and optional. Use a simple program, accessible food choices, and a concise follow-up explaining what the event achieved. The formal style comes from your current request, not an assumed standing preference.",
]

# Every personal assertion below is tied to visible user text. References that
# make general suggestions do not claim those suggestions are remembered tastes.
CLAIMS = {
    3: (125, "The user described a hike at the base of the Santa Monica Mountains; current location is uncertain.", "uncertain"),
    6: (76, "The user described carrying camp emergencies into time outside work.", "current"),
    9: (46, "The user described heavy rains delaying supply convoys.", "current"),
    10: (6, "The user described experience in aerospace materials and technical-team leadership.", "current"),
    14: (6, "The user wrote about a university STEM mentorship program and their engineering skills.", "current"),
    17: (82, "The user described studying historical cathedral etchings.", "current"),
    18: (44, "The user asked about the connection between European monetary policy and historical-print auction prices.", "current"),
    21: (80, "The user described work on refugee-support programs and a community open house.", "current"),
    23: (94, "The user described favoring simple, unfussy accessories.", "current"),
    29: (78, "The user described painting by their open balcony doors.", "current"),
    31: (208, "The user described finding postcards during an upstate trip and considering them for a production mood board.", "current"),
    40: (108, "The user described focusing on notes and delivering the main points of a history-council presentation despite nervousness.", "current"),
}

# Relevant withdrawal instructions are preserved as private rubric constraints;
# they are never extra input added to the reader's memory or retrieved context.
WITHDRAWALS = {0:[4,10,18,42], 1:[10], 4:[], 5:[118], 6:[18,24], 7:[44,98,104],
               9:[32,58], 10:[10], 12:[108], 13:[], 14:[10], 15:[54,100],
               16:[48], 17:[28], 18:[48], 19:[34], 20:[88,146,154], 21:[10],
               22:[38,164], 23:[], 24:[], 25:[212,132], 26:[40], 27:[224],
               28:[108], 29:[86], 30:[], 31:[156,192], 32:[], 33:[164,172],
               34:[], 35:[48], 36:[14,20,196], 37:[], 38:[], 39:[90,102],
               40:[84], 41:[], 42:[150], 43:[118], 44:[94,142], 45:[6],
               46:[6], 47:[64], 48:[76], 49:[94]}


def main():
    records = [json.loads(line) for line in (ROOT/"records.jsonl").read_text().splitlines()]
    assert len(records) == len(ANSWERS) == 50
    refs = []
    for n, (record, answer) in enumerate(zip(records, ANSWERS)):
        claims, constraints = [], []
        if n in CLAIMS:
            turn, claim, status = CLAIMS[n]
            claims.append({"claim": claim, "ownership": "user", "current_status": status,
                           "evidence": [evidence(record["history"], turn, record["history"][turn]["content"])]})
        for turn in WITHDRAWALS.get(n, []):
            constraints.append({"kind": "withdrawal",
                                "rule": "Do not assert or personalize from this withdrawn detail. Withdrawal does not establish the opposite or prohibit responding to a new explicit request on the same topic.",
                                "evidence": [evidence(record["history"], turn, record["history"][turn]["content"])]})
        mode = "personalized" if claims else "abstain" if n == 38 else "clarify" if n in (33,46) else "general"
        ref = draft_reference(record, answer, mode, claims, constraints,
                              "Rebuilt from sanitized dialogue and the unchanged current query; old release answer/profile/preference labels were not used.")
        refs.append(ref)
    output = ROOT/"repaired-references.jsonl"
    if output.exists():
        raise FileExistsError("freeze references once; make an explicit new revision for edits")
    output.write_bytes(b"".join(canonical(ref) for ref in refs))
    print(json.dumps({"references": len(refs), "personalized": len(CLAIMS), "status": "semantic_review_pending"}))


if __name__ == "__main__":
    main()

"""Independent scenario blueprints and strict dialogue-realization contracts.

Only public realization briefs go to the dialogue generator. Questions,
answers, and graph labels remain in a separate private sidecar.
"""

import random
import re

from .preflight import digest


DOMAINS = ("software delivery", "research coordination", "event planning", "archive administration", "field operations")
STYLES = (
    "careful clarification with short follow-up questions", "practical tradeoffs and concrete examples",
    "a hurried user who later returns to resolve ambiguity", "collaborative checklists explained in prose",
    "a skeptical user asking for reasons", "a novice who restates the agreed procedure",
    "a specialist discussing edge cases", "a coordinator separating proposals from commitments",
)
ADJECTIVES = ("Amber", "Birch", "Cedar", "Dawn", "Elm", "Fern", "Garnet", "Hazel", "Indigo", "Juniper",
              "Kestrel", "Laurel", "Maple", "North", "Opal", "Pine", "Quartz", "River", "Silver", "Tamarind")
NOUNS = ("Harbor", "Meadow", "Ridge", "Grove", "Orchard", "Valley", "Shore", "Brook", "Field", "Garden",
         "Terrace", "Cove", "Creek", "Heath", "Marsh", "Plateau", "Forest", "Bay", "Hill", "Park")
OPERATIONS = ("visitor badges", "archive labels", "room bookings", "camera checks", "weekly exports", "access reviews",
              "backup copies", "equipment loans", "training handouts", "review invitations", "supply orders", "survey drafts",
              "incident summaries", "travel forms", "release notices", "project posters", "sample shipments", "room inventories",
              "delivery receipts", "calendar reminders", "meeting minutes", "file checksums", "intake forms", "handover notes")


def build_blueprints(seed=20260910):
    """400 graphs, split by 40 realization-family groups before any dialogue."""
    rng = random.Random(seed)
    families = list(range(40)); rng.shuffle(families)
    splits = {group: "train" if i < 28 else "validation" if i < 34 else "internal_test"
              for i, group in enumerate(families)}
    out = []
    for group in range(40):
        for member in range(10):
            number = group * 10 + member
            project = ADJECTIVES[number // 20] + " " + NOUNS[number % 20]
            east, west = project + " East", project + " West"
            person = (number * 37) % 400
            first_names = ("Mira", "Nora", "Asha", "Theo", "Leon", "Sofia", "Hana", "Ravi", "Elena", "Omar", "Lina", "Noah", "Maya", "Arun", "Iris", "Jonah", "Clara", "Felix", "Ada", "Nico")
            last_names = ("Vale", "Chen", "Reed", "Park", "Silva", "Ito", "Shah", "Moss", "Wu", "Ali", "Reyes", "Kim", "Lane", "Cruz", "Nair", "Sato", "Hart", "Diaz", "Roy", "Stone")
            owner = first_names[person // 20] + " " + last_names[person % 20]
            day = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday")[number % 5]
            rejected = ("Friday", "Monday", "Tuesday", "Wednesday", "Thursday")[number % 5]
            reviewers = 2 + number % 4
            old_date, new_date = f"May {4+number%8}", f"May {18+number%8}"
            retention, other_retention = 7 + number % 17, 35 + number % 21
            units = ("metric units", "imperial units")[number % 2]
            anchors = [
                (0, f"For {project}, the accepted review meeting is on {day}.", "review_day_initial"),
                (0, f"All {project} reports must use {units}.", "old_instruction"),
                (1, f"{owner} owns the {project} export pipeline.", "pipeline_owner"),
                (1, f"The {project} delivery deadline is {old_date}, with {reviewers} reviewers required.", "deadline_initial"),
                (2, f"We rejected moving the {project} review to {rejected}; it remains on {day}.", "rejected_proposal"),
                (3, f"{east} retains exports for {retention} days; {west} retains them for {other_retention} days.", "near_entities"),
                (4, f"The {project} delivery deadline is now {new_date}; the requirement for {reviewers} reviewers is unchanged.", "partial_correction"),
                (6, f"The owner of the {project} export pipeline is responsible for the compliance review.", "owner_link"),
                (7, f"Change the cover of {project} reports to blue. This is a cover-design decision.", "unrelated_late_update"),
            ]
            distractions = []
            for j, operation in enumerate(OPERATIONS):
                days = 2 + (number * 13 + j * 7) % 61
                anchor = f"For {project}, {operation} must be checked every {days} days."
                node = f"routine_{j}"
                anchors.append((j % 8, anchor, node))
                distractions.append((operation, days, node))
            queries = [
                {"kind": "rejected_proposal", "question": f"On which day is the accepted {project} review meeting?", "answer": day, "required": [[day]], "support": ["review_day_initial", "rejected_proposal"]},
                {"kind": "partial_correction", "question": f"What is the current {project} delivery deadline and how many reviewers are required?", "answer": f"{new_date}; {reviewers} reviewers", "required": [[new_date], [str(reviewers)]], "support": ["partial_correction"]},
                {"kind": "near_entities", "question": f"How long does {east} retain exports?", "answer": f"{retention} days", "required": [[str(retention)]], "support": ["near_entities"]},
                {"kind": "multi_session", "question": f"Who is responsible for the {project} compliance review?", "answer": owner, "required": [[owner]], "support": ["pipeline_owner", "owner_link"]},
                {"kind": "old_instruction", "question": f"Which measurement system should {project} reports use?", "answer": units, "required": [[units, units.split()[0]]], "support": ["old_instruction"]},
                {"kind": "abstention", "question": f"What price was agreed for the {project} supplier contract?", "answer": "The history does not establish an agreed supplier contract price.", "required": [], "support": []},
            ]
            # Four rotating mechanisms plus one lower-salience ordinary decision.
            selected = [queries[(number+i) % 6] for i in range(4)]
            operation, days, node = distractions[(number * 7) % len(distractions)]
            selected.append({"kind": "routine_detail", "question": f"How often must {project} {operation} be checked?", "answer": f"Every {days} days", "required": [[str(days)]], "support": [node]})
            for i, question in enumerate(selected):
                question["id"] = f"cp2-{number:03d}-q{i}"
            sessions = []
            for i in range(8):
                sessions.append({"session_id": f"cp2-{number:03d}-s{i}", "date": f"2025-04-{2+i*3:02d}",
                                 "anchors": [{"node": node, "text": text} for session, text, node in anchors if session == i]})
            out.append({"family_id": f"cp2-{number:03d}", "realization_family": f"style-{group:02d}",
                        "split": splits[group], "project": project, "domain": DOMAINS[group % 5],
                        "style": STYLES[group // 5], "sessions": sessions, "questions": selected})
    assert len({r['project'] for r in out}) == 400
    return out


def realization_messages(blueprint, session):
    """Whitelist only the scenario brief; never serialize private question fields."""
    anchors = "\n".join("- " + item['text'] for item in session['anchors'])
    return [
        {"role": "system", "content": "Write a fictional user-assistant work conversation in English. Output only alternating USER: and ASSISTANT: turns. Do not output planning, XML, JSON, headings, or test questions. Preserve every supplied decision exactly; include each required sentence verbatim in a natural turn, without quoting it as an instruction. Do not reverse decisions or invent later changes. Add realistic discussion of practical details and reasons, not repetitive padding. Do not discuss supplier contract prices."},
        {"role": "user", "content": f"Project: {blueprint['project']}\nDomain: {blueprint['domain']}\nConversation style: {blueprint['style']}\nSession date: {session['date']}\nRequired decisions:\n{anchors}\nWrite a substantial dialogue of 16-24 turns, about 1600 words in total. Include questions, follow-up clarifications, examples, and intervening work. Use each required sentence once. Begin with USER:."},
    ]


def parse_realization(text, session, tokenizer):
    pieces = list(re.finditer(r"(?m)^(USER|ASSISTANT):[ \t]*", text))
    if not pieces or text[:pieces[0].start()].strip():
        raise ValueError("dialogue must start with USER: or ASSISTANT:")
    turns = []
    for i, match in enumerate(pieces):
        content = text[match.end():pieces[i+1].start() if i+1 < len(pieces) else len(text)].strip()
        if not content:
            raise ValueError("empty dialogue turn")
        role = match.group(1).lower()
        if (i % 2 == 0) != (role == 'user'):
            raise ValueError("dialogue roles must alternate, starting with user")
        turns.append({"turn_id": session['session_id'] + f"-t{i}", "role": role, "content": content})
    if len(turns) < 12:
        raise ValueError("fewer than 12 substantial dialogue turns")
    support = {}
    for anchor in session['anchors']:
        hits = [t['turn_id'] for t in turns if anchor['text'] in t['content']]
        if len(hits) != 1:
            raise ValueError(f"required decision must occur once: {anchor['node']}")
        support[anchor['node']] = hits
    words = text.lower().split()
    grams = [tuple(words[i:i+13]) for i in range(max(0, len(words)-12))]
    repeat_fraction = 1 - len(set(grams)) / max(1, len(grams))
    if repeat_fraction > 0.15:
        raise ValueError("repetitive realization: repeated 13-gram fraction > 15%")
    return {"session_id": session['session_id'], "date": session['date'], "turns": turns,
            "tokens": len(tokenizer.encode(text, add_special_tokens=False)),
            "support": support, "repeat_fraction": repeat_fraction, "text_sha256": digest(text)}


def audit_blueprints(rows):
    families, projects, questions = set(), set(), set()
    groups = {}
    counts = {}
    for row in rows:
        assert row['family_id'] not in families and row['project'] not in projects
        families.add(row['family_id']); projects.add(row['project'])
        group = row['realization_family']
        assert group not in groups or groups[group] == row['split']
        groups[group] = row['split']
        counts[row['split']] = counts.get(row['split'], 0) + 1
        assert len(row['sessions']) == 8 and len(row['questions']) == 5
        nodes = {a['node'] for s in row['sessions'] for a in s['anchors']}
        for question in row['questions']:
            assert question['id'] not in questions and set(question['support']) <= nodes
            questions.add(question['id'])
    assert counts == {'train': 280, 'validation': 60, 'internal_test': 60}
    return {"families": len(families), "realization_groups": len(groups), "questions": len(questions),
            "split_counts": counts, "manifest_sha256": digest(rows)}

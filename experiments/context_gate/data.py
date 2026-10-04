"""Deterministic state-machine conversations and label-blind retrieval.

Oracle metadata and note-policy names are never rendered into model prompts.
The three counterfactual note views of an episode stay in the same split.
"""

from __future__ import annotations

import hashlib
import json
import math
import random
import re
from collections import Counter

LETTERS = "ABCD"


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def terms(text):
    return re.findall(r"[a-z0-9]+", text.lower())


def retrieve(query, archive, k=4):
    """Two BM25 rounds: two query hits, then two query-expanded hits.

Only query text and archive text are inputs. Neither answer choices, notes,
oracle annotations, nor hidden task metadata can affect retrieval.
"""
    docs = [Counter(terms(a["text"])) for a in archive]
    lengths = [sum(d.values()) for d in docs]
    average = sum(lengths) / len(docs)
    df = Counter(t for d in docs for t in d)

    def rank(q, excluded):
        qt = set(terms(q))
        def score(i):
            return sum(math.log(1 + (len(docs) - df[t] + .5) / (df[t] + .5))
                       * (docs[i][t] * 2.2) / (docs[i][t] + 1.2 * (.25 + .75 * lengths[i] / average))
                       for t in qt if docs[i][t])
        return sorted((i for i in range(len(docs)) if i not in excluded),
                      key=lambda i: (-score(i), -archive[i]["turn"]))
    first = rank(query, set())[:min(2, k)]
    # Expand only opaque project/service references, not incidental prose.
    refs = re.findall(r"\b(?:svc|proj)[a-z0-9]+\b", " ".join(archive[i]["text"] for i in first))
    selected = first + rank(query + " " + " ".join(refs), set(first))[:k-len(first)]
    return sorted(selected, key=lambda i: archive[i]["turn"])


def build_episode(split, number, seed, projects=6):
    rng = random.Random(f"{seed}:{split}:{number}")
    nonce = hashlib.sha256(f"{seed}:{split}:{number}".encode()).hexdigest()[:10]
    eid = f"{split}-{number:04d}-{nonce}"
    names = [f"proj{nonce}{j}" for j in range(projects)]
    services = [f"svc{nonce}{j}" for j in range(projects * 2)]
    owners = [f"team-{rng.randrange(10000, 99999)}-{j}" for j in range(projects * 2)]
    artifacts = rng.sample(range(100000, 999999), projects * 2)
    initial, latest, archive, evidence = [], [], [], {}
    is_ood = split == "ood"

    def add(text):
        archive.append({"turn": len(archive) + 1, "text": text})
        return len(archive) - 1

    for j, name in enumerate(names):
        state = {"artifact": f"pkg-{artifacts[j]}", "retries": rng.randint(1, 4), "service": services[j]}
        initial.append(state)
        if is_ood:
            text = f"Opening specification for {name}: release artifact {state['artifact']}; retries {state['retries']}; service {state['service']}."
        else:
            text = f"Project {name} is configured with artifact {state['artifact']}, retries {state['retries']}, and service {state['service']}."
        evidence[j] = [add(text)]
    registry_indices = {}
    order = list(range(len(services)))
    rng.shuffle(order)
    for j in order:
        text = (f"Ownership register: service {services[j]} belongs to owner {owners[j]}." if is_ood else
                f"Service registry entry: service {services[j]} has owner {owners[j]}.")
        registry_indices[services[j]] = add(text)
    update_order = list(range(projects))
    rng.shuffle(update_order)
    final_by_project = {}
    for j in update_order:
        state = {"artifact": f"pkg-{artifacts[projects+j]}", "retries": rng.randint(5, 9), "service": services[projects+j]}
        final_by_project[j] = state
        if is_ood:
            text = f"Amendment for {names[j]} replaces its opening specification: artifact {state['artifact']}; retries {state['retries']}; service {state['service']}. All three changes take effect now."
        else:
            text = f"Update for project {names[j]}: replace artifact with {state['artifact']}, set retries to {state['retries']}, and switch service to {state['service']}. This supersedes the previous configuration."
        evidence[j].append(add(text))
    latest = [final_by_project[j] for j in range(projects)]
    # Independent administrative traffic gives note timestamps nontrivial scope.
    for j in range(projects):
        add(f"Project {names[j]} review scheduled in room {rng.randrange(10, 99)}. No configuration change was approved at this review.")
    target = rng.randrange(projects)
    family = ("identifier", "revision", "binding")[number % 3]
    if family == "identifier":
        question = f"What is the latest artifact identifier for project {names[target]}?"
        if is_ood:
            question = f"For project {names[target]}, which release artifact is in force after all amendments?"
        answer = latest[target]["artifact"]
        distractors = [initial[target]["artifact"], latest[(target+1) % projects]["artifact"], initial[(target+2) % projects]["artifact"]]
    elif family == "revision":
        question = f"What is the current retries setting for project {names[target]}?"
        if is_ood:
            question = f"After applying every revision to project {names[target]}, how many retries are specified?"
        answer = str(latest[target]["retries"])
        candidates = [str(n) for n in range(1, 10) if str(n) != answer]
        distractors = rng.sample(candidates, 3)
    else:
        question = f"Who is the owner of the service currently used by project {names[target]}?"
        if is_ood:
            question = f"Resolve project {names[target]}'s amended service assignment to its registered owner. Which team is responsible?"
        answer = owners[projects + target]
        distractors = [owners[target], owners[(target+1) % projects], owners[projects+(target+1) % projects]]
    options = distractors + [answer]
    rng.shuffle(options)
    oracle = evidence[target][:]
    if family == "binding":
        oracle.append(registry_indices[latest[target]["service"]])
    oracle.sort()
    retrieved = retrieve(question, archive)
    rows = []
    for policy in ("complete", "omitted", "stale"):
        note_lines = []
        # Coverage masks apply to every project's fields before inspecting the query.
        for j, name in enumerate(names):
            state = initial[j] if policy == "stale" else latest[j]
            source = evidence[j][0 if policy == "stale" else 1] + 1
            fields = []
            for key, value in state.items():
                keep = policy != "omitted" or rng.random() >= .55
                if keep:
                    fields.append(f"{key}={value}")
            note_lines.append(f"{name} (source turn {source}): " + "; ".join(fields))
        for svc in services:
            if policy != "omitted" or rng.random() >= .55:
                ix = services.index(svc)
                note_lines.append(f"{svc}: owner={owners[ix]}")
        rows.append({"item_id": f"{eid}-{policy}", "episode_id": eid, "split": split,
                     "family": family, "note_policy": policy, "notes": "\n".join(note_lines),
                     "archive": archive, "question": question, "options": options,
                     "answer": LETTERS[options.index(answer)], "oracle_indices": oracle,
                     "retrieved_indices": retrieved})
    return rows


def build_dataset(config, smoke=False):
    counts = {"smoke": config["smoke_episodes"]} if smoke else config["episodes"]
    rows = [r for split, count in counts.items() for i in range(count)
            for r in build_episode(split, i, config["seed"], config["projects_per_episode"])]
    audit_dataset(rows)
    return rows


def audit_dataset(rows):
    ids, episodes, archives = set(), {}, {}
    for row in rows:
        assert row["item_id"] not in ids, "duplicate item"
        ids.add(row["item_id"])
        eid, split = row["episode_id"], row["split"]
        assert episodes.setdefault(eid, split) == split, "episode crosses split"
        ah = digest(row["archive"])
        assert archives.setdefault(ah, split) == split, "archive crosses split"
        assert len(set(row["options"])) == 4
        assert row["answer"] in LETTERS
        assert all(0 <= i < len(row["archive"]) for i in row["oracle_indices"])
    return {"items": len(rows), "episodes": len(episodes),
            "splits": dict(Counter(r["split"] for r in rows)), "cross_split_archive_overlap": 0}


def render_messages(row, arm="notes"):
    system = ("Answer questions about a fictional project history. Notes can be incomplete or outdated. "
              "Exact retrieved turns override conflicting notes; later configuration changes override earlier ones. "
              "Use only the supplied information. Select the best answer among A, B, C, D. Output exactly one letter.")
    body = f"WORKING NOTES\n{row['notes']}\n\nArchive contains {len(row['archive'])} turns.\n"
    if arm in ("retrieved", "oracle"):
        indices = row["retrieved_indices"] if arm == "retrieved" else row["oracle_indices"]
        body += "\nEXACT RETRIEVED TURNS\n" + "\n".join(
            f"Turn {row['archive'][i]['turn']}: {row['archive'][i]['text']}" for i in indices) + "\n"
    body += "\nQUESTION\n" + row["question"] + "\n" + "\n".join(
        f"{letter}. {option}" for letter, option in zip(LETTERS, row["options"]))
    if arm == "decision":
        system = ("Decide whether answering the question from the working notes would benefit from searching the original history. "
                  "Notes may omit or miss later changes. Output R to retrieve up to four original turns, "
                  "or S to skip retrieval and answer from notes. Output exactly one letter, R or S.")
        body += "\nRetrieval decision:"
    else:
        body += "\nAnswer:"
    return [{"role": "system", "content": system}, {"role": "user", "content": body}]


def surface_features(row, notes_tokens, probs):
    """Only pre-retrieval observable features; no policy/family/answer metadata."""
    import numpy as np
    p = np.sort(probs)
    stamps = [int(x) for x in re.findall(r"source turn (\d+)", row["notes"])]
    overlap = set(terms(row["question"])) & set(terms(row["notes"]))
    return np.asarray([notes_tokens, len(row["notes"].splitlines()),
                       len(overlap) / max(1, len(set(terms(row["question"])))),
                       max(stamps, default=0) / len(row["archive"]),
                       sum(stamps) / max(1, len(stamps)) / len(row["archive"]),
                       p[-1], p[-1]-p[-2], -sum(float(x)*math.log(max(float(x), 1e-12)) for x in probs)], dtype=np.float32)

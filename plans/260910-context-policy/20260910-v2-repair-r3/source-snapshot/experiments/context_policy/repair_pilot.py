"""Bounded base-reader counterfactuals on the source-only label-repair sample.

No repaired references or private corpus annotations are accepted by this module.
This enriched engineering diagnostic does not train an adapter or score a test.
"""

import json
import time
from pathlib import Path

import torch
from torch.nn.attention import SDPBackend, sdpa_kernel

from .cache_session import AppendOnlySession, ReaderIdentity, parse_assistant_message
from .preflight import canonical, digest
from .relabel import TurnSearch


READER_SYSTEM = """Answer the user's current question using the notes and any retrieved dialogue.
Distinguish the user's own statements from quoted third-party text and assistant guesses.
Respect later corrections and requests to forget; forgetting a preference does not mean
the user dislikes it or forbid responding to a new explicit request on that topic.
For general advice, offer useful suggestions without inventing personal facts. If essential
information is missing or current external facts are unavailable, say so or ask a focused question.
For this forced-answer measurement, emit ANSWER on its own line, then your answer.
Keep the answer concise, at most 90 words. Do not emit RETRIEVE."""

NOTES_SYSTEM = """Summarize this chronological dialogue into compact notes of at most 768 tokens.
Future questions are unknown. Retain supported user facts, decisions, corrections, and unresolved
uncertainties with turn IDs. Distinguish quoted third-party material from the user's own life.
Assistant speculation or a draft whose original text was never supplied is not proof of a user fact.
Honor explicit requests to forget: keep a concise constraint against relying on a withdrawn detail,
not a positive preference to use later. Do not infer the opposite preference. Do not invent facts."""


def validate_bundle(bundle):
    if set(bundle) != {"histories", "questions", "scope"}:
        raise ValueError("unexpected fields in reader bundle")
    for history in bundle["histories"].values():
        for message in history:
            if set(message) != {"role", "content"} or message["role"] not in ("user", "assistant"):
                raise ValueError("private or unsupported history fields")
    ids = set()
    for question in bundle["questions"]:
        if set(question) != {"id", "persona_id", "query"} or question["id"] in ids:
            raise ValueError("private fields or duplicate query")
        ids.add(question["id"])
        if question["persona_id"] not in bundle["histories"]:
            raise ValueError("missing query history")
        if set(question["query"]) != {"role", "content"} or question["query"]["role"] != "user":
            raise ValueError("invalid query")


def render_history(history):
    return "\n\n".join(f"[T{i} {m['role']}]\n{m['content']}" for i, m in enumerate(history))


def chunks_for(tokenizer, history, limit=384, overlap=64):
    if not 0 <= overlap < limit:
        raise ValueError("invalid chunk overlap")
    chunks = []
    for i, message in enumerate(history):
        prefix = f"[T{i} {message['role']}]\n"
        allowance = limit-len(tokenizer.encode(prefix, add_special_tokens=False))
        if allowance <= overlap:
            raise ValueError("chunk budget cannot fit source label")
        ids = tokenizer.encode(message["content"], add_special_tokens=False)
        start = 0
        while start < len(ids):
            end = min(len(ids), start+allowance)
            text = prefix+tokenizer.decode(ids[start:end])
            # Context-boundary retokenization may differ: enforce the real length.
            while len(tokenizer.encode(text, add_special_tokens=False)) > limit:
                end -= 1
                text = prefix+tokenizer.decode(ids[start:end])
            chunks.append({"id": f"T{i}:{start}-{end}", "turn": i, "start": start,
                           "end": end, "role": message["role"], "content": text})
            if end == len(ids):
                break
            if end-overlap <= start:
                raise ValueError("chunker failed to advance")
            start = end-overlap
    return chunks


def retrieve_rounds(tokenizer, chunks, query, cap=1024):
    order = TurnSearch(chunks).search(query, len(chunks))
    rounds, cursor = [], 0
    for _ in range(2):
        selected = []
        while cursor < len(order):
            candidate = chunks[order[cursor]]
            trial = selected+[candidate]
            text = "\n\n".join(x["content"] for x in sorted(trial, key=lambda x: (x["turn"], x["start"])))
            if len(tokenizer.encode(text, add_special_tokens=False)) > cap:
                break
            selected = trial
            cursor += 1
        text = "\n\n".join(x["content"] for x in sorted(selected, key=lambda x: (x["turn"], x["start"]))) or "No additional matching dialogue was found."
        rounds.append({"chunk_ids": [x["id"] for x in selected], "text": text,
                       "tokens": len(tokenizer.encode(text, add_special_tokens=False))})
    return rounds


@torch.inference_mode()
def answer(model, tokenizer, messages, identity, config, deadline):
    started = time.monotonic()
    ids = tokenizer.apply_chat_template(messages, tokenize=True, add_generation_prompt=True)
    session = AppendOnlySession(model, identity, config["active_context_max_tokens"], last_logit_only=True)
    torch.cuda.synchronize()
    forward_started = time.monotonic()
    logits = session.append_transcript(ids, identity)[0][-1]
    torch.cuda.synchronize()
    prefill_seconds = time.monotonic()-forward_started
    tokens, ended = [], False
    for _ in range(config["max_message_output_tokens"]):
        deadline()
        token = int(logits.argmax())
        tokens.append(token)
        if token == tokenizer.eos_token_id:
            ended = True
            break
        ids.append(token)
        logits = session.append_transcript(ids, identity)[0][-1]
    torch.cuda.synchronize()
    text = tokenizer.decode(tokens, skip_special_tokens=True)
    try:
        action, _ = parse_assistant_message(text)
        valid = action == "answer" and ended
    except ValueError:
        valid = False
    return {"text": text, "token_ids": tokens, "ended_at_eos": ended, "valid_answer_protocol": valid,
            "input_tokens": len(tokenizer.apply_chat_template(messages, tokenize=True, add_generation_prompt=True)),
            "generated_tokens": len(tokens), "actual_forwarded_tokens": session.fresh_tokens,
            "prefill_seconds": prefill_seconds, "elapsed_seconds": time.monotonic()-started,
            "messages": messages}


def run(config, bundle, root, commit, deadline):
    from transformers import AutoModelForCausalLM, AutoTokenizer
    validate_bundle(bundle)
    root = Path(root)
    torch.set_num_threads(4)
    torch.manual_seed(0)
    tokenizer = AutoTokenizer.from_pretrained(config["model_id"], revision=config["model_revision"], local_files_only=True)
    model = AutoModelForCausalLM.from_pretrained(config["model_id"], revision=config["model_revision"],
            local_files_only=True, torch_dtype=torch.bfloat16, attn_implementation="sdpa").to("cuda").eval()
    assert model.config._commit_hash == config["model_revision"]
    model.requires_grad_(False)
    notes = {}
    for pid, history in bundle["histories"].items():
        deadline()
        messages = [{"role": "system", "content": NOTES_SYSTEM}, {"role": "user", "content": render_history(history)}]
        ids = tokenizer.apply_chat_template(messages, tokenize=True, add_generation_prompt=True, return_tensors="pt").to("cuda")
        began = time.monotonic()
        with torch.inference_mode():
            generated = model.generate(ids, attention_mask=torch.ones_like(ids), do_sample=False,
                max_new_tokens=config["notes_max_tokens"], pad_token_id=tokenizer.eos_token_id,
                use_cache=True, max_time=100.0)
        new = generated[0, ids.shape[1]:].tolist()
        notes[pid] = {"text": tokenizer.decode(new, skip_special_tokens=True), "input_tokens": ids.shape[1],
                      "output_tokens": len(new), "ended_at_eos": bool(new and new[-1] == tokenizer.eos_token_id),
                      "elapsed_seconds": time.monotonic()-began}
        (root/"notes.json").write_bytes(canonical(notes));commit()
        print(json.dumps({"stage": "notes", "persona": pid, "completed": len(notes)}), flush=True)
    model.float()
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    torch.set_float32_matmul_precision("highest")
    identity = ReaderIdentity(config["model_revision"], "base-no-adapter", digest(tokenizer.chat_template), "fp32_math-tf32-off")
    indexes, index_seconds = {}, {}
    for pid, history in bundle["histories"].items():
        began = time.monotonic()
        indexes[pid] = chunks_for(tokenizer, history, config["chunk_max_tokens"], config["chunk_overlap_tokens"])
        index_seconds[pid] = time.monotonic()-began
    (root/"indexes.json").write_bytes(canonical(indexes));commit()
    captures = []
    with sdpa_kernel(SDPBackend.MATH):
        for question in bundle["questions"]:
            deadline()
            pid = question["persona_id"]
            began = time.monotonic()
            retrievals = retrieve_rounds(tokenizer, indexes[pid], question["query"]["content"], config["evidence_tokens_per_round"])
            retrieval_seconds = time.monotonic()-began
            recent_ids = tokenizer.encode(render_history(bundle["histories"][pid]), add_special_tokens=False)[-config["recent_max_tokens"]:]
            base = [{"role": "system", "content": READER_SYSTEM}, {"role": "user", "content":
                     f"Notes:\n{notes[pid]['text']}\n\nRecent dialogue:\n{tokenizer.decode(recent_ids)}\n\nCurrent question:\n{question['query']['content']}"}]
            for n in range(3):
                messages = list(base)
                for tool in retrievals[:n]:
                    messages += [{"role": "assistant", "content": "RETRIEVE"}, {"role": "tool", "content": tool["text"]}]
                result = answer(model, tokenizer, messages, identity, config, deadline)
                captures.append({"id": question["id"], "persona_id": pid, "retrieval_rounds": n,
                                 "retrieval": retrievals[:n], "retrieval_ranking_seconds": retrieval_seconds, **result})
                (root/"captures.json").write_bytes(canonical(captures));commit()
                print(json.dumps({"stage": "capture", "completed": len(captures), "id": question["id"], "rounds": n,
                                  "valid": result["valid_answer_protocol"], "seconds": result["elapsed_seconds"]}), flush=True)
    return {"status": "awaiting_manual_judgments", "questions": len(bundle["questions"]), "captures": len(captures),
            "valid_protocol": sum(c["valid_answer_protocol"] for c in captures), "notes": len(notes),
            "notes_seconds": sum(n["elapsed_seconds"] for n in notes.values()), "index_seconds": index_seconds,
            "capture_seconds": sum(c["elapsed_seconds"] for c in captures), "trainable_parameters": 0,
            "runtime": "fp32_math", "retriever": "BM25 diagnostic only", "corpus_trained": False}

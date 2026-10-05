"""P2D Step 2 registered decision rules (M4-SGM.md § P2D Step 2, clarifications 1-3).

Pure functions over per-example rows and geometry dicts; every rule fails
closed (SystemExit) on malformed, incomplete or misaligned input instead of
returning a reading.
"""

import math
from collections import defaultdict

import torch

N_EPISODES, QUERIES, N_CLASSES, CEILING = 256, (0, 1, 2, 3), 64, 0.04
SEEDS, LAYERS, HEADS = ("0", "1"), ("1", "3"), 2
ROW_FIELDS = {"batch": int, "episode": int, "episode_hash": str, "query": int, "key": int,
              "label": int, "pred": int, "correct": bool, "intervention": str}
GEOMETRY = ("median_distance", "target_coupling", "other_coupling", "read_spread")


def check_row(r: dict) -> None:
    if not isinstance(r, dict) or set(r) != set(ROW_FIELDS) or any(
            type(r[k]) is not t for k, t in ROW_FIELDS.items()):
        raise SystemExit(f"row schema mismatch: {r!r:.120}")
    if not (0 <= r["pred"] < N_CLASSES and 0 <= r["label"] < N_CLASSES):
        raise SystemExit("row pred/label outside the class range")
    if r["correct"] != (r["pred"] == r["label"]):
        raise SystemExit("row correct flag disagrees with pred == label")


def episode_scores(rows: list, iv: str) -> dict:
    """(batch, episode, hash) -> mean of its 4 query hits; complete or abort."""
    eps: dict = defaultdict(dict)
    for r in rows:
        check_row(r)
        if r["intervention"] != iv:
            continue
        key = (r["batch"], r["episode"], r["episode_hash"])
        if r["query"] in eps[key]:
            raise SystemExit("duplicate query row")
        eps[key][r["query"]] = r["correct"]
    if len(eps) != N_EPISODES or any(set(v) != set(QUERIES) for v in eps.values()):
        raise SystemExit(f"{iv}: incomplete final rows ({len(eps)} episodes)")
    return {k: sum(v.values()) / len(QUERIES) for k, v in eps.items()}


def paired(a_rows: list, b_rows: list, iv_a: str = "none", iv_b: str = "none") -> dict:
    a, b = episode_scores(a_rows, iv_a), episode_scores(b_rows, iv_b)
    if set(a) != set(b):
        raise SystemExit("paired runs do not share episode hashes")
    d = torch.tensor([a[k] - b[k] for k in a], dtype=torch.float64)
    hw = float(1.96 * d.std() / math.sqrt(len(d)))
    return {"diff": float(d.mean()), "lo": float(d.mean()) - hw, "hi": float(d.mean()) + hw, "n": len(d)}


def reproducible(per_seed: dict) -> bool:
    if set(per_seed) != set(SEEDS):
        raise SystemExit(f"reproducibility needs seeds {SEEDS}, got {sorted(per_seed)}")
    return all(r["diff"] >= 0.05 and r["lo"] > 0 for r in per_seed.values())


def memory_use(rows: list) -> dict:
    derange = episode_scores(rows, "bank_derange")
    acc = sum(derange.values()) / len(derange)
    p_der, p_off = paired(rows, rows, "none", "bank_derange"), paired(rows, rows, "none", "read_offset")
    return {"derange_accuracy": acc, "none_minus_derange": p_der, "none_minus_read_offset": p_off,
            "pass": acc <= CEILING and p_der["lo"] > 0 and p_off["lo"] > 0}


def check_geometry(g: dict) -> None:
    if set(g) != set(LAYERS) or any(set(g[l]) != set(GEOMETRY) or any(
            len(g[l][q]) != HEADS for q in GEOMETRY) for l in LAYERS):
        raise SystemExit("geometry lacks the registered layer/head coverage")


def alignment_ok(treat: dict, base: dict) -> dict:
    """Clarification 2: every layer has >= 1 head meeting (a)-(d)."""
    check_geometry(treat)
    check_geometry(base)
    layers = {}
    for l in LAYERS:
        g, b = treat[l], base[l]
        heads = [g["median_distance"][h] < b["median_distance"][h] and g["target_coupling"][h] > 0
                 and g["target_coupling"][h] >= 2 * g["other_coupling"][h] and g["read_spread"][h] >= 1
                 for h in range(HEADS)]
        layers[l] = {"heads_pass": heads, "pass": any(heads)}
    return {"layers": layers, "pass": all(v["pass"] for v in layers.values())}


def addrsup_reading(gain: bool, align: bool, mem: bool) -> str:
    if gain and align and mem:
        return "SUPPORTS usefulness of this supervised routing-training recipe"
    if align and not gain:
        return "alignment improved; no registered reproducible gain"
    if not align:
        return "probe did not establish the intended alignment; cause unresolved"
    return "registered reproducible gain without registered memory-use evidence"


def long_reading(vs_own: bool, vs_v2: bool) -> dict:
    return {"4500_vs_own_1500": "reproducible gain" if vs_own else "no registered reproducible gain",
            "4500_vs_v2": "reproducible gain" if vs_v2 else "no registered reproducible gain",
            "overall": "budget effect for this recipe" if vs_own and vs_v2
            else "budget effect not established (both registered contrasts required)"}

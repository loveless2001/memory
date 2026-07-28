"""Q3 fragility placement on the fixed E1 2,000-item protocol."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

import numpy as np

from memsub.certification.mergecert_statistics import (
    cohen_kappa,
    directional_failure_nesting,
)


HERE = Path(__file__).resolve().parent
DEFAULT_SCORES = HERE / "q2-scores.npz"
DEFAULT_Q2_RESULTS = HERE / "q2-routability.json"
DEFAULT_REFERENCE_DIR = Path("/tmp/mergecert-q3-references")
DEFAULT_OUTPUT = HERE / "q3-fragility.json"
DEFAULT_TRIGGER = HERE / "q1-trigger.json"
REFERENCE_FILES = {
    "A": "e1-relabel-A2.state.json",
    "B": "e1-relabel-B.state.json",
    "FR": "e1-relabel-FR.state.json",
    "E1F": "e1-relabel-E1F.state.json",
}
HEADLINE_REFERENCES = ("A", "FR", "E1F")
DOMAINS = ("financial", "legal", "code", "literature")
Q1_BUDGET_MODE = "archived-m1-per-document-matched-physical-v1"


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _require_q1_trigger(path: str) -> dict:
    if not os.path.exists(path):
        raise ValueError("Q2 is blocked until q1-trigger.json exists")
    with open(path) as handle:
        trigger = json.load(handle)
    favorable_intervals = trigger.get("favorable_intervals", []) if isinstance(trigger, dict) else []
    hashes = (
        trigger.get("q1_verdict_sha256", "") if isinstance(trigger, dict) else "",
        trigger.get("addendum_sha256", "") if isinstance(trigger, dict) else "",
        trigger.get("p0_verdict_sha256", "") if isinstance(trigger, dict) else "",
    )
    valid = (
        isinstance(trigger, dict)
        and trigger.get("protocol") == "MERGECERT-Q1"
        and trigger.get("budget_mode") == Q1_BUDGET_MODE
        and trigger.get("run_q2_q3") is True
        and isinstance(favorable_intervals, list)
        and bool(favorable_intervals)
        and all(
            isinstance(interval, str) and bool(interval.strip())
            for interval in favorable_intervals
        )
        and all(isinstance(value, str) and len(value) == 64 for value in hashes)
    )
    if not valid:
        raise ValueError("Q2 is blocked by the registered Q1 trigger")
    return trigger


def _comparison(merge, reference) -> dict:
    agreement = cohen_kappa(merge, reference)
    nesting = directional_failure_nesting(merge, reference)
    return {
        "n": agreement["n"],
        "kappa": agreement["kappa"],
        "raw_agreement": agreement["raw_agreement"],
        "expected_agreement": agreement["expected_agreement"],
        "merge_failure_rate": nesting["merge_failure_rate"],
        "reference_failure_rate": nesting["reference_failure_rate"],
        "merge_failure_denominator": nesting["merge_failure_denominator"],
        "intersection": nesting["intersection"],
        "novel_merge_failures": nesting["novel_merge_failures"],
        "nesting_fraction": nesting["nesting_fraction"],
    }


def _domain_comparison(merge, reference) -> dict:
    agreement = cohen_kappa(merge, reference)
    denominator = int(np.asarray(merge).sum())
    intersection = int(
        ((np.asarray(merge) == 1) & (np.asarray(reference) == 1)).sum()
    )
    return {
        "n": agreement["n"],
        "kappa": agreement["kappa"],
        "raw_agreement": agreement["raw_agreement"],
        "merge_failure_rate": float(np.asarray(merge).mean()),
        "reference_failure_rate": float(np.asarray(reference).mean()),
        "merge_failure_denominator": denominator,
        "intersection": intersection,
        "novel_merge_failures": denominator - intersection,
        "nesting_fraction": (
            intersection / denominator if denominator else None
        ),
    }


def _markdown_table(comparisons: dict) -> str:
    lines = [
        "| reference regime | merge failure rate | reference failure rate | "
        "raw agreement | Cohen kappa | merge-conditioned nesting | "
        "intersection / merge failures | novel merge failures |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name in ("A", "B", "FR", "E1F"):
        row = comparisons[name]
        lines.append(
            f"| {name} | {row['merge_failure_rate']:.4f} | "
            f"{row['reference_failure_rate']:.4f} | "
            f"{row['raw_agreement']:.4f} | {row['kappa']:.4f} | "
            f"{row['nesting_fraction']:.4f} | "
            f"{row['intersection']} / {row['merge_failure_denominator']} | "
            f"{row['novel_merge_failures']} |"
        )
    return "\n".join(lines) + "\n"


def analyze(
    scores,
    references,
    reference_hashes,
    q2_results,
    *,
    expected_items=2_000,
    trigger_path: Path = DEFAULT_TRIGGER,
):
    q1_trigger = _require_q1_trigger(str(trigger_path))
    q1_trigger_sha256 = _sha256_file(Path(trigger_path))
    if (
        q2_results.get("q1_trigger") != q1_trigger
        or q2_results.get("q1_trigger_sha256") != q1_trigger_sha256
        or q2_results.get("source_hashes", {}).get("q1_trigger")
        != q1_trigger_sha256
    ):
        raise ValueError("Q3 trigger differs from Q2 result manifest")
    score_trigger_json = np.asarray(scores.get("q1_trigger_json", [])).reshape(-1)
    score_trigger_sha256 = np.asarray(
        scores.get("q1_trigger_sha256", [])
    ).reshape(-1)
    if len(score_trigger_json) != 1 or len(score_trigger_sha256) != 1:
        raise ValueError("Q3 score manifest Q1 trigger is missing")
    try:
        score_trigger = json.loads(str(score_trigger_json[0]))
    except json.JSONDecodeError as error:
        raise ValueError("Q3 score manifest Q1 trigger is invalid") from error
    if (
        score_trigger != q1_trigger
        or str(score_trigger_sha256[0]) != q1_trigger_sha256
    ):
        raise ValueError("Q3 score manifest Q1 trigger differs from Q2 result")
    item_ids_all = np.asarray(scores["item_ids"]).astype(str)
    domains_all = np.asarray(scores["domain"]).astype(str)
    ratios = np.asarray(scores["ratio"], dtype=float)
    labels = np.asarray(scores["y"], dtype=int)
    in_e1 = np.asarray(scores["in_e1"], dtype=int)
    if not (
        len(item_ids_all)
        == len(domains_all)
        == len(ratios)
        == len(labels)
        == len(in_e1)
    ):
        raise ValueError("Q3 score arrays are not aligned")
    selected = np.isclose(ratios, 0.40, rtol=0, atol=1e-6) & (in_e1 == 1)
    if int(selected.sum()) != expected_items:
        raise ValueError(
            f"Q3 merge 0.40 E1 coverage must be {expected_items}"
        )
    selected_ids = item_ids_all[selected]
    selected_domains = domains_all[selected]
    merge_labels = labels[selected]
    if len(set(selected_ids)) != expected_items:
        raise ValueError("Q3 merge E1 item IDs must be unique")
    if not np.isin(merge_labels, (0, 1)).all():
        raise ValueError("Q3 merge labels must be binary")
    order = np.argsort(selected_ids)
    selected_ids = selected_ids[order]
    selected_domains = selected_domains[order]
    merge_labels = merge_labels[order]
    domain_by_id = dict(zip(selected_ids, selected_domains))

    if set(references) != set(REFERENCE_FILES) or set(reference_hashes) != set(
        REFERENCE_FILES
    ):
        raise ValueError("Q3 requires A/B/FR/E1F reference artifacts and hashes")
    reference_labels = {}
    for name in REFERENCE_FILES:
        payload = references[name]
        rows = payload.get("rows", [])
        if payload.get("done") != expected_items or len(rows) != expected_items:
            raise ValueError(f"{name} reference coverage mismatch")
        ids = [str(row["item_id"]) for row in rows]
        if len(set(ids)) != expected_items or set(ids) != set(selected_ids):
            raise ValueError(f"{name} reference item coverage mismatch")
        if not reference_hashes[name]:
            raise ValueError(f"{name} reference hash missing")
        by_id = {str(row["item_id"]): row for row in rows}
        for item_id in selected_ids:
            if str(by_id[item_id]["domain"]) != domain_by_id[item_id]:
                raise ValueError(f"{name} reference domain drift for {item_id}")
        values = np.asarray(
            [int(by_id[item_id]["y"]) for item_id in selected_ids], dtype=int
        )
        if not np.isin(values, (0, 1)).all():
            raise ValueError(f"{name} reference labels must be binary")
        reference_labels[name] = values

    comparisons = {
        name: _comparison(merge_labels, reference_labels[name])
        for name in REFERENCE_FILES
    }
    per_domain = {}
    for domain in DOMAINS:
        mask = selected_domains == domain
        if not mask.any():
            raise ValueError(f"Q3 E1 sample lacks domain {domain}")
        per_domain[domain] = {
            name: _domain_comparison(
                merge_labels[mask], reference_labels[name][mask]
            )
            for name in REFERENCE_FILES
        }

    headline_nesting = {
        name: comparisons[name]["nesting_fraction"]
        for name in HEADLINE_REFERENCES
    }
    interpretation = (
        "Fragility is reported marginal-aware: kappa measures agreement "
        "beyond the two observed base rates, while nesting conditions only "
        "on merge failures. The novel-merge count therefore identifies the "
        "mechanism-specific minority without treating prevalence shrinkage "
        "as disagreement."
    )
    return {
        "pass": True,
        "protocol": {
            "ratio": 0.40,
            "items": expected_items,
            "headline_references": list(HEADLINE_REFERENCES),
            "context_reference": "B",
            "nesting_direction": (
                "|failure_merge intersect failure_ref| / |failure_merge|"
            ),
        },
        "merge": {
            "failures": int(merge_labels.sum()),
            "failure_rate": float(merge_labels.mean()),
            "domain_counts": {
                domain: int((selected_domains == domain).sum())
                for domain in DOMAINS
            },
        },
        "comparisons": comparisons,
        "per_domain": per_domain,
        "headline_references": list(HEADLINE_REFERENCES),
        "context_reference": "B",
        "headline_nesting": headline_nesting,
        "reference_hashes": dict(reference_hashes),
        "interpretation": interpretation,
        "markdown_table": _markdown_table(comparisons),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scores", type=Path, default=DEFAULT_SCORES)
    parser.add_argument("--q2-results", type=Path, default=DEFAULT_Q2_RESULTS)
    parser.add_argument(
        "--reference-dir", type=Path, default=DEFAULT_REFERENCE_DIR
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--trigger", type=Path, default=DEFAULT_TRIGGER)
    args = parser.parse_args()
    with args.q2_results.open() as handle:
        q2_results = json.load(handle)
    if q2_results.get("scores_sha256") != _sha256_file(args.scores):
        raise ValueError("Q3 scores differ from the Q2 evidence hash")
    with np.load(args.scores, allow_pickle=False) as archive:
        scores = {name: archive[name] for name in archive.files}
    references = {}
    hashes = {}
    for name, filename in REFERENCE_FILES.items():
        path = args.reference_dir / filename
        with path.open() as handle:
            references[name] = json.load(handle)
        hashes[name] = _sha256_file(path)
    verdict = analyze(
        scores, references, hashes, q2_results, trigger_path=args.trigger
    )
    with args.output.open("w") as handle:
        json.dump(verdict, handle, indent=1, allow_nan=False)
    print(json.dumps(verdict, indent=1))


if __name__ == "__main__":
    main()

"""Independent Q2 routability analysis from compact per-item score evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

import numpy as np

from memsub.certification.mergecert_statistics import (
    cluster_bootstrap_auc,
    document_split,
    tie_aware_auc,
)


HERE = Path(__file__).resolve().parent
DEFAULT_RESULTS = HERE / "q2-routability.json"
DEFAULT_SCORES = HERE / "q2-scores.npz"
DEFAULT_OUTPUT = HERE / "q2-verdict.json"
DEFAULT_TABLE = HERE / "q2-table.md"
DEFAULT_F5_TABLE = HERE / "q2-f5-table.md"
DEFAULT_TRIGGER = HERE / "q1-trigger.json"
RATIOS = (0.25, 0.40)
ARMS = (
    "c0_refit",
    "mechanics_refit",
    "shadow_zero_shot",
    "shadow_refit",
    "sink_compactor_zero_shot",
    "sink_eviction_zero_shot",
    "sink_refit",
    "residual_linear",
    "residual_mlp",
)
DOMAINS = ("financial", "legal", "code", "literature")
Q1_TRIGGER_PATH = "/artifacts/mergecert-q1/q1-trigger.json"


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _require_q1_trigger(path: str = Q1_TRIGGER_PATH) -> dict:
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


def _recompute_metric(y, scores, split, documents, domains, *, seed, n_resamples):
    test = split == 2
    result = cluster_bootstrap_auc(
        y[test],
        scores[test],
        documents[test],
        seed=seed,
        n_resamples=n_resamples,
    )
    result["per_domain_auc"] = {}
    for domain in DOMAINS:
        mask = test & (domains == domain)
        if mask.sum() and len(np.unique(y[mask])) == 2:
            result["per_domain_auc"][domain] = tie_aware_auc(
                y[mask], scores[mask]
            )
    return result


def _assert_metric_matches(remote: dict, local: dict, label: str) -> None:
    if abs(float(remote["auc"]) - local["auc"]) > 1e-6:
        raise ValueError(
            f"{label}: remote/local AUC mismatch "
            f"{remote['auc']} vs {local['auc']}"
        )
    remote_ci = np.asarray(remote["ci95"], dtype=float)
    local_ci = np.asarray(local["ci95"], dtype=float)
    if not np.allclose(remote_ci, local_ci, rtol=0, atol=1e-6):
        raise ValueError(
            f"{label}: remote/local cluster interval mismatch "
            f"{remote_ci.tolist()} vs {local_ci.tolist()}"
        )
    for key in ("n_items", "n_documents"):
        if int(remote[key]) != int(local[key]):
            raise ValueError(f"{label}: remote/local {key} mismatch")
    remote_domain = remote.get("per_domain_auc", {})
    if set(remote_domain) != set(local["per_domain_auc"]):
        raise ValueError(f"{label}: remote/local per-domain cells differ")
    for domain, value in local["per_domain_auc"].items():
        if abs(float(remote_domain[domain]) - value) > 1e-6:
            raise ValueError(
                f"{label}: remote/local {domain} AUC mismatch"
            )


def _markdown_table(ratio_metrics: dict, pooled_metrics: dict) -> str:
    labels = {
        "c0_refit": "surface / c0 refit",
        "mechanics_refit": "merge mechanics refit",
        "shadow_zero_shot": "shadow gate zero-shot",
        "shadow_refit": "shadow gate refit",
        "sink_compactor_zero_shot": "sink monitor compactor to merge",
        "sink_eviction_zero_shot": "sink monitor eviction to merge",
        "sink_refit": "sink monitor merge refit",
        "residual_linear": "residual best-layer linear",
        "residual_mlp": "residual best-layer MLP",
    }
    lines = [
        "| arm | merge 0.25 test AUC [95% CI] | "
        "merge 0.40 test AUC [95% CI] | pooled test AUC [95% CI] |",
        "|---|---:|---:|---:|",
    ]
    for arm in ARMS:
        cells = []
        for source in (
            ratio_metrics["0.25"],
            ratio_metrics["0.40"],
            pooled_metrics,
        ):
            metric = source[arm]
            cells.append(
                f"{metric['auc']:.4f} "
                f"[{metric['ci95'][0]:.4f}, {metric['ci95'][1]:.4f}]"
            )
        lines.append(f"| {labels[arm]} | {' | '.join(cells)} |")
    return "\n".join(lines) + "\n"


def _f5_table(ratio_metrics: dict) -> str:
    lines = [
        "| F5 fifth-regime row | merge 0.25 AUC [95% CI] | "
        "merge 0.40 AUC [95% CI] |",
        "|---|---:|---:|",
    ]
    for label, arm in (
        ("compactor to merge zero-shot", "sink_compactor_zero_shot"),
        ("eviction to merge zero-shot", "sink_eviction_zero_shot"),
        ("merge refit", "sink_refit"),
    ):
        cells = []
        for ratio in ("0.25", "0.40"):
            metric = ratio_metrics[ratio][arm]
            cells.append(
                f"{metric['auc']:.4f} "
                f"[{metric['ci95'][0]:.4f}, {metric['ci95'][1]:.4f}]"
            )
        lines.append(f"| {label} | {' | '.join(cells)} |")
    return "\n".join(lines) + "\n"


def analyze(
    payload,
    arrays,
    *,
    expected_items_per_ratio=30_847,
    expected_e1_items=2_000,
    n_resamples=2_000,
    trigger_path: Path = DEFAULT_TRIGGER,
):
    q1_trigger = _require_q1_trigger(str(trigger_path))
    q1_trigger_sha256 = _sha256_file(Path(trigger_path))
    if (
        payload.get("q1_trigger") != q1_trigger
        or payload.get("q1_trigger_sha256") != q1_trigger_sha256
    ):
        raise ValueError("Q2 trigger differs from result manifest")
    if payload.get("model_id") != "Qwen/Qwen3-4B-Instruct-2507":
        raise ValueError("Q2 model provenance mismatch")
    if payload.get("ratios") != list(RATIOS) or payload.get("seeds") != [0, 1, 2]:
        raise ValueError("Q2 registered ratios/seeds mismatch")
    if not payload.get("source_hashes"):
        raise ValueError("Q2 source hashes are missing")
    if payload["source_hashes"].get("q1_trigger") != q1_trigger_sha256:
        raise ValueError("Q2 trigger file hash differs from source hashes")
    score_trigger_json = np.asarray(
        arrays.get("q1_trigger_json", [])
    ).reshape(-1)
    score_trigger_sha256 = np.asarray(
        arrays.get("q1_trigger_sha256", [])
    ).reshape(-1)
    if len(score_trigger_json) != 1 or len(score_trigger_sha256) != 1:
        raise ValueError("Q2 score manifest Q1 trigger is missing")
    try:
        score_trigger = json.loads(str(score_trigger_json[0]))
    except json.JSONDecodeError as error:
        raise ValueError("Q2 score manifest Q1 trigger is invalid") from error
    if (
        score_trigger != q1_trigger
        or str(score_trigger_sha256[0]) != q1_trigger_sha256
    ):
        raise ValueError("Q2 score manifest Q1 trigger differs from result")

    required = {
        "item_ids",
        "doc_ids",
        "domain",
        "ratio",
        "y",
        "split",
        "in_e1",
        *(
            f"{arm}_{fit}"
            for arm in ARMS
            for fit in ("separate", "pooled")
        ),
    }
    missing = required - set(arrays)
    if missing:
        raise ValueError(f"Q2 scores missing arrays: {sorted(missing)}")
    total = 2 * expected_items_per_ratio
    for key in required:
        values = np.asarray(arrays[key])
        if values.ndim == 0 or values.shape[0] != total:
            raise ValueError(f"Q2 score array {key} has wrong first dimension")

    item_ids = np.asarray(arrays["item_ids"]).astype(str)
    documents = np.asarray(arrays["doc_ids"]).astype(str)
    domains = np.asarray(arrays["domain"]).astype(str)
    ratios = np.asarray(arrays["ratio"], dtype=float)
    y = np.asarray(arrays["y"], dtype=int)
    split = np.asarray(arrays["split"], dtype=int)
    in_e1 = np.asarray(arrays["in_e1"], dtype=int)
    expected_split = document_split(
        documents, train_end=0.6, validation_end=0.7
    )
    if not np.array_equal(split, expected_split):
        raise ValueError("Q2 stored split differs from SHA-256 document split")
    if not np.isin(y, (0, 1)).all() or not np.isin(in_e1, (0, 1)).all():
        raise ValueError("Q2 labels and E1 membership must be binary")

    ratio_metrics = {}
    item_sets = []
    for ratio_index, ratio in enumerate(RATIOS):
        key = f"{ratio:.2f}"
        mask = np.isclose(ratios, ratio, rtol=0, atol=1e-6)
        if mask.sum() != expected_items_per_ratio:
            raise ValueError(f"Q2 ratio {key} item count mismatch")
        ids = item_ids[mask]
        if len(set(ids)) != expected_items_per_ratio:
            raise ValueError(f"Q2 ratio {key} item IDs are not unique")
        if int(in_e1[mask].sum()) != expected_e1_items:
            raise ValueError(f"Q2 ratio {key} E1 coverage mismatch")
        item_sets.append(set(ids))
        ratio_metrics[key] = {}
        remote_arms = payload["ratios_results"][key]["arms"]
        for arm_index, arm in enumerate(ARMS):
            scores = np.asarray(arrays[f"{arm}_separate"], dtype=float)[mask]
            if not np.isfinite(scores).all():
                raise ValueError(f"Q2 {key} {arm} scores are not finite")
            local = _recompute_metric(
                y[mask],
                scores,
                split[mask],
                documents[mask],
                domains[mask],
                seed=20260727 + ratio_index * 100 + arm_index,
                n_resamples=n_resamples,
            )
            _assert_metric_matches(remote_arms[arm], local, f"{key} {arm}")
            ratio_metrics[key][arm] = local
    if item_sets[0] != item_sets[1]:
        raise ValueError("Q2 ratios do not cover the same registered items")

    pooled_metrics = {}
    for arm_index, arm in enumerate(ARMS):
        scores = np.asarray(arrays[f"{arm}_pooled"], dtype=float)
        if not np.isfinite(scores).all():
            raise ValueError(f"Q2 pooled {arm} scores are not finite")
        local = _recompute_metric(
            y,
            scores,
            split,
            documents,
            domains,
            seed=20261000 + arm_index,
            n_resamples=n_resamples,
        )
        _assert_metric_matches(
            payload["pooled"]["arms"][arm], local, f"pooled {arm}"
        )
        pooled_metrics[arm] = local

    mechanics_auc = np.mean(
        [ratio_metrics[key]["mechanics_refit"]["auc"] for key in ("0.25", "0.40")]
    )
    residual_auc = np.mean(
        [ratio_metrics[key]["residual_mlp"]["auc"] for key in ("0.25", "0.40")]
    )
    if mechanics_auc >= 0.70:
        reading = (
            "Merged loss is mechanics-routable: the visible-mechanics blend "
            f"reaches mean AUC {mechanics_auc:.3f} across registered ratios."
        )
    elif 0.50 <= mechanics_auc <= 0.60 and residual_auc >= 0.70:
        reading = (
            "Merged loss behaves like synthesis despite visible mechanics: "
            f"mechanics AUC is {mechanics_auc:.3f} while residual AUC is "
            f"{residual_auc:.3f}."
        )
    else:
        reading = (
            "Merged-loss routability falls between the two registered anchor "
            f"readings (mechanics {mechanics_auc:.3f}, residual "
            f"{residual_auc:.3f}); retain the measured placement."
        )
    table = _markdown_table(ratio_metrics, pooled_metrics)
    f5_table = _f5_table(ratio_metrics)
    return {
        "pass": True,
        "items_per_ratio": expected_items_per_ratio,
        "e1_items_per_ratio": expected_e1_items,
        "ratios": ratio_metrics,
        "pooled": pooled_metrics,
        "registered_reading": reading,
        "markdown_table": table,
        "f5_markdown_table": f5_table,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", type=Path, default=DEFAULT_RESULTS)
    parser.add_argument("--scores", type=Path, default=DEFAULT_SCORES)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--table", type=Path, default=DEFAULT_TABLE)
    parser.add_argument("--f5-table", type=Path, default=DEFAULT_F5_TABLE)
    parser.add_argument("--trigger", type=Path, default=DEFAULT_TRIGGER)
    args = parser.parse_args()
    with args.results.open() as handle:
        payload = json.load(handle)
    expected_hash = payload.get("scores_sha256")
    actual_hash = _sha256_file(args.scores)
    if not expected_hash or expected_hash != actual_hash:
        raise ValueError("Q2 scores hash differs from remote result manifest")
    with np.load(args.scores, allow_pickle=False) as archive:
        arrays = {name: archive[name] for name in archive.files}
    verdict = analyze(payload, arrays, trigger_path=args.trigger)
    with args.output.open("w") as handle:
        json.dump(verdict, handle, indent=1, allow_nan=False)
    args.table.write_text(verdict["markdown_table"])
    args.f5_table.write_text(verdict["f5_markdown_table"])
    print(json.dumps(verdict, indent=1))


if __name__ == "__main__":
    main()

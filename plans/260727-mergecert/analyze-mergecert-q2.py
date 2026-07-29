"""Independent Q2 routability analysis from compact per-item score evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

import numpy as np

from memsub.certification import (
    Q2_ACCOUNTING_ARRAY_FIELDS,
    Q2_CONTEXT_MECHANICS_VERSION,
    Q2_NAMESPACE_VERSION,
    Q2_PROTOCOL_VERSION,
    Q2_REGISTERED_ITEMS,
    Q2_ROUTABILITY_SCHEMA,
    Q2_SCORE_SCHEMA,
    Q2_VERDICT_SCHEMA,
    load_q1_trigger,
    load_q2_amendment,
    validate_q2_accounting_arrays,
)
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
DEFAULT_TRIGGER = HERE.parent / "260728-mergecert-q1" / "q1-trigger.json"
DEFAULT_AMENDMENT = HERE.parent / "260728-mergecert-q1" / "q2-amendment.json"
DEFAULT_MANIFEST = Path("/artifacts/probe/capture-manifest.json")
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
Q1_BUDGET_MODE = "archived-m1-per-document-matched-physical-v1"
Q1_ADDENDUM_SHA256 = (
    "35869e386bb64242ad0067ab51d680779eed65d4a88bbb4ba7180aec634fd509"
)
Q1_P0_VERDICT_SHA256 = (
    "4dff3d8806a12fd751d352bbbac94b1bef3b9a5b8db20bbea9da221df06ccb2a"
)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _require_q1_trigger(path: str = Q1_TRIGGER_PATH) -> dict:
    try:
        return load_q1_trigger(path)
    except (FileNotFoundError, OSError) as exc:
        raise ValueError("Q2 is blocked until q1-trigger.json exists") from exc


def _singleton_array(arrays: dict, name: str) -> str:
    values = np.asarray(arrays.get(name, [])).reshape(-1)
    if len(values) != 1:
        raise ValueError(f"Q2 score manifest {name} is missing")
    return str(values[0])


def _require_amended_provenance(payload: dict, arrays: dict, amendment_path: Path):
    amendment_sha256 = _sha256_file(amendment_path)
    amendment = load_q2_amendment(amendment_path, amendment_sha256)
    amendment_json = amendment_path.read_text(encoding="utf-8")
    source_hashes = payload.get("source_hashes")
    if not isinstance(source_hashes, dict):
        raise ValueError("Q2 source hashes are missing")
    if (
        payload.get("q2_amendment") != amendment
        or payload.get("q2_amendment_sha256") != amendment_sha256
        or source_hashes.get("q2_amendment") != amendment_sha256
    ):
        raise ValueError("Q2 amendment differs from the local authority")
    expected_versions = {
        "protocol_version": Q2_PROTOCOL_VERSION,
        "namespace_version": Q2_NAMESPACE_VERSION,
        "context_mechanics_version": Q2_CONTEXT_MECHANICS_VERSION,
    }
    for name, expected in expected_versions.items():
        if payload.get(name) != expected:
            raise ValueError(f"Q2 {name} differs from the amendment")
    if (
        _singleton_array(arrays, "q2_amendment_json") != amendment_json
        or _singleton_array(arrays, "q2_amendment_sha256") != amendment_sha256
    ):
        raise ValueError("Q2 score amendment differs from the local authority")
    for name, expected in expected_versions.items():
        if _singleton_array(arrays, f"q2_{name}") != expected:
            raise ValueError(f"Q2 score {name} differs from the amendment")
    capture_summary_sha256 = payload.get("capture_summary_sha256")
    if (
        not isinstance(capture_summary_sha256, str)
        or source_hashes.get("capture_summary") != capture_summary_sha256
        or _singleton_array(arrays, "capture_summary_sha256")
        != capture_summary_sha256
    ):
        raise ValueError("Q2 capture summary hash differs from source evidence")
    return amendment, amendment_sha256


def _require_frozen_manifest(
    payload: dict,
    arrays: dict,
    manifest_path: Path,
    expected_items: int,
):
    manifest_sha256 = _sha256_file(manifest_path)
    source_hashes = payload["source_hashes"]
    if (
        payload.get("manifest_sha256") != manifest_sha256
        or source_hashes.get("manifest") != manifest_sha256
        or _singleton_array(arrays, "source_manifest_sha256")
        != manifest_sha256
    ):
        raise ValueError("Q2 frozen manifest hash differs from source evidence")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError("Q2 frozen manifest is not valid JSON") from error
    if not isinstance(manifest, list):
        raise ValueError("Q2 frozen manifest must be a list")
    if len(manifest) != expected_items:
        raise ValueError(
            f"Q2 frozen manifest must contain exactly {expected_items} rows"
        )
    manifest_by_id = {}
    for row in manifest:
        if (
            not isinstance(row, dict)
            or not isinstance(row.get("item_id"), str)
            or not isinstance(row.get("doc_id"), str)
            or row.get("domain") not in DOMAINS
            or isinstance(row.get("chunk_rel_start"), bool)
            or not isinstance(row.get("chunk_rel_start"), int)
        ):
            raise ValueError("Q2 frozen manifest metadata is invalid")
        if row["item_id"] in manifest_by_id:
            raise ValueError("Q2 frozen manifest contains duplicate item IDs")
        manifest_by_id[row["item_id"]] = row
    return manifest_by_id


def _validate_flattened_accounting(
    arrays, item_ids, documents, domains, ratios, manifest_by_id
):
    audits = {}
    flattened = {
        field: np.asarray(arrays[field]).reshape(-1)
        for field in Q2_ACCOUNTING_ARRAY_FIELDS
    }
    for ratio in RATIOS:
        key = f"{ratio:.2f}"
        mask = ratios == ratio
        indices = np.flatnonzero(mask)
        expected_rows = []
        for index in indices:
            item_id = item_ids[index]
            if item_id not in manifest_by_id:
                raise ValueError("Q2 score item ID is outside the frozen manifest")
            manifest_row = manifest_by_id[item_id]
            if (
                documents[index] != manifest_row["doc_id"]
                or domains[index] != manifest_row["domain"]
            ):
                raise ValueError("Q2 score metadata differs from the frozen manifest")
            expected_rows.append(manifest_row)
        if len(set(item_ids[indices])) != len(indices):
            raise ValueError("Q2 score ratio contains duplicate manifest item IDs")
        segment = {
            field: flattened[field][indices]
            for field in Q2_ACCOUNTING_ARRAY_FIELDS
        }
        audits[key] = validate_q2_accounting_arrays(
            segment, expected_rows, ratio
        )
    audit_sha256 = hashlib.sha256(
        json.dumps(audits, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    if (
        arrays.get("accounting_audit_sha256") is None
        or _singleton_array(arrays, "accounting_audit_sha256") != audit_sha256
    ):
        raise ValueError("Q2 score accounting audit hash differs from rows")
    return audits, audit_sha256


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
    expected_manifest_items=None,
    expected_e1_items=2_000,
    n_resamples=2_000,
    trigger_path: Path = DEFAULT_TRIGGER,
    amendment_path: Path = DEFAULT_AMENDMENT,
    manifest_path: Path = DEFAULT_MANIFEST,
):
    if expected_manifest_items is None:
        expected_manifest_items = expected_items_per_ratio
    if (
        expected_items_per_ratio == Q2_REGISTERED_ITEMS
        and expected_manifest_items != Q2_REGISTERED_ITEMS
    ):
        raise ValueError("production Q2 manifest size is fixed at 30,847")
    q1_trigger = _require_q1_trigger(str(trigger_path))
    q1_trigger_sha256 = _sha256_file(Path(trigger_path))
    if (
        payload.get("q1_trigger") != q1_trigger
        or payload.get("q1_trigger_sha256") != q1_trigger_sha256
    ):
        raise ValueError("Q2 trigger differs from result manifest")
    if payload.get("schema") != Q2_ROUTABILITY_SCHEMA:
        raise ValueError("Q2 routability schema is not amended-v2")
    if payload.get("score_schema") != Q2_SCORE_SCHEMA:
        raise ValueError("Q2 routed score schema is not amended-v2")
    if _singleton_array(arrays, "score_schema") != Q2_SCORE_SCHEMA:
        raise ValueError("Q2 score archive schema is not amended-v2")
    scores_sha256 = payload.get("scores_sha256")
    if (
        not isinstance(scores_sha256, str)
        or len(scores_sha256) != 64
        or any(character not in "0123456789abcdef" for character in scores_sha256)
    ):
        raise ValueError("Q2 scores SHA-256 is missing or noncanonical")
    if payload.get("model_id") != "Qwen/Qwen3-4B-Instruct-2507":
        raise ValueError("Q2 model provenance mismatch")
    if payload.get("ratios") != list(RATIOS) or payload.get("seeds") != [0, 1, 2]:
        raise ValueError("Q2 registered ratios/seeds mismatch")
    amendment, amendment_sha256 = _require_amended_provenance(
        payload, arrays, Path(amendment_path)
    )
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
    manifest_by_id = _require_frozen_manifest(
        payload, arrays, Path(manifest_path), expected_manifest_items
    )

    required = {
        "item_ids",
        "doc_ids",
        "domain",
        "ratio",
        "y",
        "split",
        "in_e1",
        *Q2_ACCOUNTING_ARRAY_FIELDS,
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
    if not np.isfinite(ratios).all() or not np.isin(ratios, RATIOS).all():
        raise ValueError("Q2 ratios must be exact registered values")
    accounting_audit, accounting_audit_sha256 = _validate_flattened_accounting(
        arrays, item_ids, documents, domains, ratios, manifest_by_id
    )
    if (
        payload.get("accounting_audit") != accounting_audit
        or payload.get("accounting_audit_sha256") != accounting_audit_sha256
    ):
        raise ValueError("Q2 accounting audit differs from routed evidence")

    ratio_masks = {}
    item_sets = []
    for ratio in RATIOS:
        key = f"{ratio:.2f}"
        mask = ratios == ratio
        if mask.sum() != expected_items_per_ratio:
            raise ValueError(f"Q2 ratio {key} item count mismatch")
        ids = item_ids[mask]
        if len(set(ids)) != expected_items_per_ratio:
            raise ValueError(f"Q2 ratio {key} item IDs are not unique")
        if int(in_e1[mask].sum()) != expected_e1_items:
            raise ValueError(f"Q2 ratio {key} E1 coverage mismatch")
        ratio_masks[key] = mask
        item_sets.append(set(ids))
    if item_sets[0] != item_sets[1]:
        raise ValueError("Q2 ratios do not cover the same registered items")
    if any(item_set != set(manifest_by_id) for item_set in item_sets):
        raise ValueError("Q2 ratios do not equal the full frozen manifest ID set")

    ratio_metrics = {}
    for ratio_index, ratio in enumerate(RATIOS):
        key = f"{ratio:.2f}"
        mask = ratio_masks[key]
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
        "schema": Q2_VERDICT_SCHEMA,
        "pass": True,
        "q1_trigger": q1_trigger,
        "q1_trigger_sha256": q1_trigger_sha256,
        "protocol_version": Q2_PROTOCOL_VERSION,
        "namespace_version": Q2_NAMESPACE_VERSION,
        "context_mechanics_version": Q2_CONTEXT_MECHANICS_VERSION,
        "q2_amendment": amendment,
        "q2_amendment_sha256": amendment_sha256,
        "context_accounting_audit": accounting_audit,
        "context_accounting_audit_sha256": accounting_audit_sha256,
        "accounting_audit_sha256": accounting_audit_sha256,
        "source_hashes": dict(payload["source_hashes"]),
        "score_schema": Q2_SCORE_SCHEMA,
        "scores_sha256": scores_sha256,
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
    parser.add_argument("--amendment", type=Path, default=DEFAULT_AMENDMENT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args()
    with args.results.open() as handle:
        payload = json.load(handle)
    expected_hash = payload.get("scores_sha256")
    actual_hash = _sha256_file(args.scores)
    if not expected_hash or expected_hash != actual_hash:
        raise ValueError("Q2 scores hash differs from remote result manifest")
    with np.load(args.scores, allow_pickle=False) as archive:
        arrays = {name: archive[name] for name in archive.files}
    verdict = analyze(
        payload, arrays, trigger_path=args.trigger,
        amendment_path=args.amendment,
        manifest_path=args.manifest,
    )
    with args.output.open("w") as handle:
        json.dump(verdict, handle, indent=1, allow_nan=False)
    args.table.write_text(verdict["markdown_table"])
    args.f5_table.write_text(verdict["f5_markdown_table"])
    print(json.dumps(verdict, indent=1))


if __name__ == "__main__":
    main()

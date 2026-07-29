import hashlib
import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest

from memsub.certification import (
    Q2_CONTEXT_MECHANICS_VERSION,
    expected_q2_plan_fields,
    validate_q2_accounting_arrays,
)
from memsub.compaction import validate_capture_chunk


ROOT = Path(__file__).resolve().parents[1]
RUNNER_PATH = ROOT / "modal-runners" / "modal-mergecert-q2-probes.py"
AMENDMENT_PATH = ROOT / "plans" / "260728-mergecert-q1" / "q2-amendment.json"
AMENDMENT_JSON = AMENDMENT_PATH.read_text()
AMENDMENT = json.loads(AMENDMENT_JSON)
AMENDMENT_SHA256 = hashlib.sha256(AMENDMENT_PATH.read_bytes()).hexdigest()
TRIGGER_PATH = ROOT / "plans" / "260728-mergecert-q1" / "q1-trigger.json"
TRIGGER = json.loads(TRIGGER_PATH.read_text())


def _load_runner(name: str):
    spec = importlib.util.spec_from_file_location(name, RUNNER_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _trigger():
    return dict(TRIGGER)


def _short_manifest_row():
    return {
        "item_id": "mcq_code/00130_1230_28",
        "doc_id": "code/00130",
        "domain": "code",
        "chunk_rel_start": 128,
        "pred_raw": "A",
        "raw_correct": 1,
        "in_e1": 0,
    }


def _short_arrays(row, *, ratio=0.25):
    plan = expected_q2_plan_fields(4073, ratio)
    return {
        "item_ids": np.asarray([row["item_id"]]),
        "doc_ids": np.asarray([row["doc_id"]]),
        "domain": np.asarray([row["domain"]]),
        "pred_raw": np.asarray(["A"]),
        "pred_merge": np.asarray(["B"]),
        "y": np.asarray([1], dtype=np.int8),
        "raw_correct": np.asarray([1], dtype=np.int8),
        "in_e1": np.asarray([0], dtype=np.int8),
        "locator_found": np.asarray([1], dtype=np.int8),
        "merge_overlap": np.asarray([0.0], dtype=np.float32),
        "mechanics": np.asarray([[4.0, 0.5, 0.5, 0.5]], dtype=np.float32),
        "sink_features": np.zeros((1, 8), dtype=np.float32),
        "residuals": np.zeros((1, 37, 2560), dtype=np.float16),
        "ratio": np.asarray([ratio], dtype=np.float64),
        "source_manifest_sha256": np.asarray(["manifest-hash"]),
        "item_id": np.asarray([row["item_id"]]),
        "context_mechanics_version": np.asarray([Q2_CONTEXT_MECHANICS_VERSION]),
        "source_document_token_count": np.asarray([4073], dtype=np.int64),
        "source_context_start": np.asarray([0], dtype=np.int64),
        "source_context_end": np.asarray([4073], dtype=np.int64),
        "source_context_token_count": np.asarray([4073], dtype=np.int64),
        "model_input_token_count": np.asarray([4073], dtype=np.int64),
        "source_chunk_token_start": np.asarray([1230], dtype=np.int64),
        "source_chunk_context_start": np.asarray([1230], dtype=np.int64),
        "requested_eviction_start": np.asarray([plan["requested_eviction_start"]], dtype=np.int64),
        "requested_eviction_end": np.asarray([plan["requested_eviction_end"]], dtype=np.int64),
        "requested_evicted_token_count": np.asarray([plan["requested_evicted_token_count"]], dtype=np.int64),
        "physical_before_count": np.asarray([4073], dtype=np.int64),
        "physical_after_count": np.asarray([plan["retained_token_count"]], dtype=np.int64),
        "physical_removed_count": np.asarray([plan["requested_evicted_token_count"]], dtype=np.int64),
        "retained_token_count": np.asarray([plan["retained_token_count"]], dtype=np.int64),
        "merge_target_retained": np.asarray([plan["merge_target_retained"]], dtype=np.int64),
        "merge_recent_start": np.asarray([plan["merge_recent_start"]], dtype=np.int64),
    }


def _write_short_capture(tmp_path):
    row = _short_manifest_row()
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps([row]))
    arrays = _short_arrays(row)
    manifest_sha256 = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    arrays["source_manifest_sha256"] = np.asarray([manifest_sha256])
    chunk_path = tmp_path / "ratio-0.25.npz"
    np.savez(chunk_path, **arrays)
    audit = validate_q2_accounting_arrays(arrays, [row], 0.25)
    summary = {
        "schema": "mergecert-q2-capture-summary-v2",
        "protocol": "MERGECERT-Q2",
        "protocol_version": "mergecert-q2-amended-v2",
        "namespace_version": "mergecert-q2-amended-v2",
        "context_mechanics_version": Q2_CONTEXT_MECHANICS_VERSION,
        "q2_amendment": AMENDMENT,
        "q2_amendment_sha256": AMENDMENT_SHA256,
        "q1_trigger": _trigger(),
        "q1_trigger_sha256": "",
        "model_id": "Qwen/Qwen3-4B-Instruct-2507",
        "ratios": [0.25, 0.4],
        "source_manifest": {
            "path": str(manifest_path),
            "sha256": manifest_sha256,
        },
        "source_manifest_sha256": manifest_sha256,
        "pilot_verdict": {},
        "items_per_ratio": 1,
        "unique_items_per_ratio": {"0.25": 1, "0.40": 1},
        "positive_labels": {"0.25": 1, "0.40": 1},
        "positive_rates": {"0.25": 1.0, "0.40": 1.0},
        "locator_found": {"0.25": 1, "0.40": 1},
        "locator_rates": {"0.25": 1.0, "0.40": 1.0},
        "domain_counts": {"0.25": {"code": 1}, "0.40": {"code": 1}},
        "worker_compute_seconds": 0.0,
        "chunks": [{
            "ratio": 0.25,
            "slice_idx": 0,
            "path": str(chunk_path),
            "sha256": hashlib.sha256(chunk_path.read_bytes()).hexdigest(),
            "audit": {**validate_capture_chunk(arrays, expected_ratio=0.25), "context_accounting": audit},
        }],
        "pass": True,
    }
    summary_path = tmp_path / "capture-summary.json"
    trigger_path = tmp_path / "q1-trigger.json"
    trigger_path.write_bytes(TRIGGER_PATH.read_bytes())
    summary["q1_trigger_sha256"] = hashlib.sha256(trigger_path.read_bytes()).hexdigest()
    pilot_dir = tmp_path / "q2-amended-v2" / "pilot-amended-v2"
    pilot_dir.mkdir(parents=True)
    pilot_path = pilot_dir / "pilot-verdict.json"
    pilot = {
        "schema": "mergecert-q2-pilot-verdict-v3-amended",
        "protocol": "MERGECERT-Q2",
        "protocol_version": "mergecert-q2-amended-v2",
        "namespace_version": "mergecert-q2-amended-v2",
        "context_mechanics_version": Q2_CONTEXT_MECHANICS_VERSION,
        "validator_version": "mergecert-q2-pilot-validator-v3-amended",
        "validation_mode": "single-registered-run",
        "run_tag": "amended-v2",
        "run_tags": ["amended-v2"],
        "items": 16,
        "ratios": [0.25, 0.4],
        "q2_amendment": AMENDMENT,
        "q2_amendment_sha256": AMENDMENT_SHA256,
        "q1_trigger": _trigger(),
        "q1_trigger_sha256": summary["q1_trigger_sha256"],
        "source_manifest": {
            "path": str(manifest_path),
            "sha256": manifest_sha256,
        },
        "state": {
            "path": str(pilot_dir / "state.json"),
            "sha256": "a" * 64,
        },
        "artifacts": {
            key: {
                "path": str(pilot_dir / f"ratio-{key}.npz"),
                "sha256": character * 64,
                "audit": {"context_accounting": {"rows": 16}},
            }
            for key, character in (("0.25", "b"), ("0.40", "c"))
        },
        "compatibility_fingerprint_schema": (
            "memsub-compatibility-fingerprint-v1"
        ),
        "compatibility_fingerprint": {"model": "fixture"},
        "compatibility_fingerprint_sha256": "d" * 64,
        "audits": {
            "0.25": {"context_accounting": {"rows": 16}},
            "0.40": {"context_accounting": {"rows": 16}},
        },
        "comparisons": {},
        "pass": True,
    }
    pilot_path.write_bytes(
        (
            json.dumps(
                pilot, sort_keys=True, separators=(",", ":"), allow_nan=False
            )
            + "\n"
        ).encode()
    )
    summary["pilot_verdict"] = {
        "path": str(pilot_path),
        "sha256": hashlib.sha256(pilot_path.read_bytes()).hexdigest(),
        "schema": pilot["schema"],
    }
    summary_path.write_text(json.dumps(summary))
    return row, arrays, chunk_path, summary, summary_path, trigger_path


def _write_two_chunk_capture(tmp_path):
    first = _short_manifest_row()
    second = {
        **first,
        "item_id": "mcq_code/00130_204_27",
        "chunk_rel_start": 129,
    }
    rows = [first, second]
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(rows))
    manifest_sha256 = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    chunks = []
    for index, row in enumerate(rows):
        arrays = _short_arrays(row)
        arrays["source_manifest_sha256"] = np.asarray([manifest_sha256])
        arrays["source_chunk_token_start"] = np.asarray(
            [int(row["item_id"].rsplit("_", 2)[1])], dtype=np.int64
        )
        arrays["source_chunk_context_start"] = np.asarray(
            [int(row["item_id"].rsplit("_", 2)[1])], dtype=np.int64
        )
        chunk_path = tmp_path / f"ratio-0.25-{index}.npz"
        np.savez(chunk_path, **arrays)
        chunks.append({
            "ratio": 0.25,
            "slice_idx": 0,
            "path": str(chunk_path),
            "sha256": hashlib.sha256(chunk_path.read_bytes()).hexdigest(),
            "audit": {
                **validate_capture_chunk(arrays, expected_ratio=0.25),
                "context_accounting": validate_q2_accounting_arrays(
                    arrays, [row], 0.25
                ),
            },
        })
    summary = {
        "source_manifest_sha256": manifest_sha256,
        "chunks": chunks,
    }
    return rows, summary


def _write_fact_types_state(tmp_path, runner, summary, trigger, trigger_sha256):
    source_path = tmp_path / "fact-types-source.json"
    source_path.write_text(json.dumps({"types": {"item": "number"}}))
    state = {
        "source_path": str(source_path),
        "source_sha256": hashlib.sha256(source_path.read_bytes()).hexdigest(),
        "manifest_sha256": summary["source_manifest_sha256"],
        "q1_trigger": trigger,
        "q1_trigger_sha256": trigger_sha256,
        "q2_protocol_version": "mergecert-q2-amended-v2",
        "q2_namespace_version": "mergecert-q2-amended-v2",
        "q2_context_mechanics_version": Q2_CONTEXT_MECHANICS_VERSION,
        "q2_amendment_json": AMENDMENT_JSON,
        "q2_amendment_sha256": AMENDMENT_SHA256,
        "types": {"item": "number"},
        "completed_missing_item_ids": [],
    }
    state_path = tmp_path / "fact-types-complete.json"
    state_path.write_text(json.dumps(state))
    return source_path, state_path, state


def _configure_gate(monkeypatch, runner, summary_path, trigger_path):
    monkeypatch.setattr(runner, "CAPTURE_SUMMARY", str(summary_path))
    monkeypatch.setattr(runner, "Q1_TRIGGER_PATH", str(trigger_path))
    monkeypatch.setattr(runner, "Q2_AMENDMENT_IMAGE_PATH", str(AMENDMENT_PATH))
    pilot_path = json.loads(summary_path.read_text())["pilot_verdict"]["path"]
    monkeypatch.setattr(runner, "CAPTURE_ROOT", str(Path(pilot_path).parents[1]))


def test_probe_runner_uses_only_amended_artifact_paths_and_app_source():
    runner = _load_runner("mergecert_q2_probe_paths")

    assert runner.CAPTURE_SUMMARY == "/artifacts/mergecert/q2-amended-v2/capture-summary.json"
    assert runner.ROUTABILITY_OUTPUT == "/artifacts/mergecert/q2-amended-v2/routability.json"
    assert runner.SCORES_OUTPUT == "/artifacts/mergecert/q2-amended-v2/scores.npz"
    assert runner.FACT_TYPES_COMPLETE == "/artifacts/mergecert/q2-amended-v2/fact-types-complete.json"
    assert runner.app.name == "memsub-mergecert-q2-amended-v2-probes"
    assert runner.ROUTABILITY_SCHEMA == "mergecert-q2-routability-amended-v2"
    assert runner.SCORE_SCHEMA == "mergecert-q2-scores-amended-v2"


def test_probe_routability_provenance_hashes_the_settled_amendment(monkeypatch):
    runner = _load_runner("mergecert_q2_probe_routability_provenance")
    monkeypatch.setattr(runner, "_sha256_file", lambda path: f"hash:{path}")
    monkeypatch.setattr(runner.glob, "glob", lambda pattern: [])

    hashes = runner._routability_source_hashes(
        "capture-summary-hash", {"q2_amendment_sha256": AMENDMENT_SHA256}
    )

    assert hashes["q2_amendment"] == AMENDMENT_SHA256
    assert hashes["capture_summary"] == "capture-summary-hash"


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("missing-amendment", "amendment"),
        ("amendment-drift", "amendment"),
        ("wrong-schema", "summary"),
        ("wrong-namespace", "namespace"),
        ("wrong-context-mechanics", "context"),
        ("wrong-trigger", "trigger"),
    ],
)
def test_probe_gate_rejects_any_non_amended_capture_summary(
    tmp_path, monkeypatch, mutation, message
):
    _, _, _, summary, summary_path, trigger_path = _write_short_capture(tmp_path)
    runner = _load_runner(f"mergecert_q2_probe_gate_{mutation}")
    _configure_gate(monkeypatch, runner, summary_path, trigger_path)
    if mutation == "missing-amendment":
        del summary["q2_amendment"]
    elif mutation == "amendment-drift":
        summary["q2_amendment_sha256"] = "0" * 64
    elif mutation == "wrong-schema":
        summary["schema"] = "mergecert-q2-capture-summary-v1"
    elif mutation == "wrong-namespace":
        summary["namespace_version"] = "mergecert-q2"
    elif mutation == "wrong-context-mechanics":
        summary["context_mechanics_version"] = "fixed-4096"
    elif mutation == "wrong-trigger":
        summary["q1_trigger"]["run_q2_q3"] = False
    summary_path.write_text(json.dumps(summary))

    with pytest.raises(ValueError, match=message):
        runner._require_gate_and_capture()


def test_probe_gate_rejects_legacy_capture_root(tmp_path, monkeypatch):
    _, _, _, _, summary_path, trigger_path = _write_short_capture(tmp_path)
    runner = _load_runner("mergecert_q2_probe_legacy_root")
    _configure_gate(monkeypatch, runner, summary_path, trigger_path)
    monkeypatch.setattr(runner, "CAPTURE_SUMMARY", "/artifacts/mergecert/q2/capture-summary.json")

    with pytest.raises(ValueError, match="amended"):
        runner._require_gate_and_capture()


def test_probe_gate_accepts_real_canonical_amended_pilot_verdict(
    tmp_path, monkeypatch
):
    _, _, _, summary, summary_path, trigger_path = _write_short_capture(
        tmp_path
    )
    runner = _load_runner("mergecert_q2_probe_real_pilot")
    _configure_gate(monkeypatch, runner, summary_path, trigger_path)

    assert runner._require_gate_and_capture()[1] == summary


@pytest.mark.parametrize(
    "mutation",
    (
        "missing",
        "tampered-bytes",
        "non-object",
        "legacy-path",
        "legacy-schema",
    ),
)
def test_probe_gate_rejects_missing_tampered_or_legacy_pilot_verdict(
    tmp_path, monkeypatch, mutation
):
    _, _, _, summary, summary_path, trigger_path = _write_short_capture(
        tmp_path
    )
    runner = _load_runner(f"mergecert_q2_probe_pilot_{mutation}")
    _configure_gate(monkeypatch, runner, summary_path, trigger_path)
    pilot_path = Path(summary["pilot_verdict"]["path"])
    if mutation == "missing":
        pilot_path.unlink()
    elif mutation == "tampered-bytes":
        pilot_path.write_bytes(pilot_path.read_bytes() + b" ")
    elif mutation == "non-object":
        pilot_path.write_text("[]\n")
        summary["pilot_verdict"]["sha256"] = hashlib.sha256(
            pilot_path.read_bytes()
        ).hexdigest()
        summary_path.write_text(json.dumps(summary))
    elif mutation == "legacy-path":
        summary["pilot_verdict"]["path"] = (
            "/artifacts/mergecert/q2/pilot-q1-triggered/pilot-verdict.json"
        )
        summary_path.write_text(json.dumps(summary))
    elif mutation == "legacy-schema":
        summary["pilot_verdict"]["schema"] = "mergecert-q2-pilot-verdict-v2"
        summary_path.write_text(json.dumps(summary))

    with pytest.raises(ValueError, match="pilot"):
        runner._require_gate_and_capture()


@pytest.mark.parametrize(
    "mutation",
    [
        "source_context_start",
        "source_context_end",
        "physical_removed_count",
        "merge_target_retained",
        "merge_recent_start",
        "item_id",
        "accounting_sha256",
    ],
)
def test_assembly_rejects_mutated_amended_accounting_before_probe_fit(
    tmp_path, mutation
):
    row, arrays, chunk_path, summary, _, _ = _write_short_capture(tmp_path)
    if mutation == "accounting_sha256":
        summary["chunks"][0]["audit"]["context_accounting"]["accounting_sha256"] = "0" * 64
    else:
        arrays[mutation][0] = arrays[mutation][0] + 1 if arrays[mutation].dtype.kind in "iu" else "other-item"
        np.savez(chunk_path, **arrays)
        summary["chunks"][0]["sha256"] = hashlib.sha256(chunk_path.read_bytes()).hexdigest()

    runner = _load_runner(f"mergecert_q2_probe_assembly_{mutation}")
    with pytest.raises(ValueError):
        runner._assemble_capture_chunks(summary, [row], ratios=(0.25,))


def test_assembly_uses_per_item_short_context_distance(tmp_path):
    row, arrays, _, summary, _, _ = _write_short_capture(tmp_path)
    runner = _load_runner("mergecert_q2_probe_short_distance")
    assembled = runner._assemble_capture_chunks(summary, [row], ratios=(0.25,))
    distance = runner._c0_distance(
        assembled["0.25"]["merge_recent_start"],
        assembled["0.25"]["source_chunk_context_start"],
    )

    assert distance.tolist() == [arrays["merge_recent_start"][0] - (1230 + 1024)]
    old_fixed = 4096 - ((4096 - int(4096 * 0.25) - 4) // 2) - (128 + 1024)
    assert distance.tolist() != [old_fixed]


def test_assembly_rejects_coherently_shifted_item_anchor(tmp_path):
    row, arrays, chunk_path, summary, _, _ = _write_short_capture(tmp_path)
    arrays["source_chunk_token_start"][0] += 10
    arrays["source_chunk_context_start"][0] += 10
    np.savez(chunk_path, **arrays)
    summary["chunks"][0]["sha256"] = hashlib.sha256(
        chunk_path.read_bytes()
    ).hexdigest()

    runner = _load_runner("mergecert_q2_probe_shifted_item_anchor")
    with pytest.raises(ValueError, match="source_chunk_token_start"):
        runner._assemble_capture_chunks(summary, [row], ratios=(0.25,))


def test_assembly_aggregates_full_accounting_audit_across_chunks(tmp_path):
    rows, summary = _write_two_chunk_capture(tmp_path)
    runner = _load_runner("mergecert_q2_probe_multichunk_accounting")

    assembled = runner._assemble_capture_chunks(summary, rows, ratios=(0.25,))
    target = assembled["0.25"]
    expected = validate_q2_accounting_arrays(target, rows, 0.25)

    assert target["accounting_audit"] == expected
    assert target["accounting_audit"]["rows"] == 2
    assert target["accounting_audit"]["accounting_sha256"] != summary["chunks"][1]["audit"]["context_accounting"]["accounting_sha256"]


def test_manifest_binding_rejects_same_id_content_drift(tmp_path):
    row, _, _, summary, _, _ = _write_short_capture(tmp_path)
    manifest_path = tmp_path / "manifest.json"
    drifted = {**row, "domain": "financial"}
    manifest_path.write_text(json.dumps([drifted]))
    runner = _load_runner("mergecert_q2_probe_manifest_drift")

    with pytest.raises(ValueError, match="manifest hash"):
        runner._require_frozen_manifest(summary, str(manifest_path))


def test_fact_type_state_accepts_complete_amended_provenance(tmp_path, monkeypatch):
    _, _, _, summary, _, trigger_path = _write_short_capture(tmp_path)
    runner = _load_runner("mergecert_q2_probe_fact_state_valid")
    trigger = _trigger()
    trigger_sha256 = hashlib.sha256(trigger_path.read_bytes()).hexdigest()
    source_path, state_path, state = _write_fact_types_state(
        tmp_path, runner, summary, trigger, trigger_sha256
    )
    monkeypatch.setattr(runner, "FACT_TYPES_SOURCE", str(source_path))
    monkeypatch.setattr(runner, "FACT_TYPES_COMPLETE", str(state_path))
    monkeypatch.setattr(runner, "Q2_AMENDMENT_IMAGE_PATH", str(AMENDMENT_PATH))

    assert runner._require_complete_fact_types(
        summary, trigger, trigger_sha256
    ) == state


@pytest.mark.parametrize(
    "mutation",
    [
        "q2_amendment_sha256",
        "q2_protocol_version",
        "q2_namespace_version",
        "q2_context_mechanics_version",
        "manifest_sha256",
    ],
)
def test_fact_type_state_rejects_stale_amended_provenance(
    tmp_path, monkeypatch, mutation
):
    _, _, _, summary, _, trigger_path = _write_short_capture(tmp_path)
    runner = _load_runner(f"mergecert_q2_probe_fact_state_{mutation}")
    trigger = _trigger()
    trigger_sha256 = hashlib.sha256(trigger_path.read_bytes()).hexdigest()
    source_path, state_path, state = _write_fact_types_state(
        tmp_path, runner, summary, trigger, trigger_sha256
    )
    monkeypatch.setattr(runner, "FACT_TYPES_SOURCE", str(source_path))
    monkeypatch.setattr(runner, "FACT_TYPES_COMPLETE", str(state_path))
    monkeypatch.setattr(runner, "Q2_AMENDMENT_IMAGE_PATH", str(AMENDMENT_PATH))
    if mutation == "manifest_sha256":
        state[mutation] = "0" * 64
    elif mutation == "q2_amendment_sha256":
        state[mutation] = "0" * 64
    else:
        state[mutation] = "stale"
    state_path.write_text(json.dumps(state))

    with pytest.raises(ValueError, match="fact types"):
        runner._require_complete_fact_types(summary, trigger, trigger_sha256)

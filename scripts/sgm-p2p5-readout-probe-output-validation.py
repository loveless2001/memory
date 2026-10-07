"""P2.5 readout-recipe rescue probe: PATH-EXACT output validation (proposal v0.2 §8.1/§8.2; codex 21750 #1/#2).

The campaign extractor normalises selected-layer keys ('L6/out_proj' -> 'L{L}/out_proj') and requires one type per
normalised key, so it cannot express the taskhead graph, where the last selected layer's out_proj/alpha never get a
gradient. Here keys stay exact, and the frozen schema carries the None-vs-zero CONTRACT derived from the graph:
  (a) REQUIRED null  : grad_norm L{last}/out_proj, L{last}/alpha. They only feed layers after the last selected layer,
                       which the task head never reads.
  (b) number-or-null : grad_norm L{l}/k_proj, L{l}/value, L{l}/beta at every selected layer. Write-path parameters
                       reach the loss only through a read (ingest or query time) of a cell written in the batch graph.
  (c) everything else exactly as the frozen campaign learned schema (numbers). update_norm is a parameter-difference
                       norm and stays numeric everywhere (0.0 for an unchanged parameter).
`validate_probe_outputs` runs the ORIGINAL campaign validator with schema=None (every other check kept: done.json
hashes, strict JSON, manifest/populations, rows, metric/row agreement, telemetry counts/steps, registry, finiteness,
wall clock), then checks metrics.json and EVERY telemetry row against the frozen path-exact schema.
`ProbeSlotSupervisor` wires it into the COMPLETE transition (narrow copy of SlotSupervisor.finish); collection and
the reading use the same function. memsub and every campaign file are unchanged.
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from memsub.sgm import packed_slot_cell_output_validation as V  # noqa: E402
from memsub.sgm import packed_slot_epoch_state as es  # noqa: E402
from memsub.sgm.packed_slot_supervisor import SlotSupervisor  # noqa: E402

NULLABLE_FIELD = "grad_norm"                       # the ONLY field whose leaves may be null (update_norm: never)
REQUIRED_NULL_GROUPS = ("out_proj", "alpha")       # last selected layer only
NUM_OR_NULL_GROUPS = ("k_proj", "value", "beta")   # every selected layer
NUM, NULL, NUM_OR_NULL = {"num": True}, {"null": True}, {"num_or_null": True}
GRAD_PATHS = (("telemetry_train_row", ("grad_norm",)), ("metrics", ("train_last", "grad_norm")))


def expand_layers(node: dict, layers: list[str]) -> dict:
    """Normalised campaign schema -> path-exact schema ('{L}' -> each layer id, 'L{L}/x' -> 'L<l>/x')."""
    if "dict" in node:
        out = {}
        for k, v in node["dict"].items():
            sub = expand_layers(v, layers)
            keys = (layers if k == "{L}" else [f"L{l}/{k[5:]}" for l in layers] if k.startswith("L{L}/") else [k])
            for nk in keys:
                if nk in out:
                    raise ValueError(f"expanded key collision {nk}")
                out[nk] = copy.deepcopy(sub)
        return {"dict": out}
    if "list" in node:
        return {"list": None if node["list"] is None else expand_layers(node["list"], layers)}
    return dict(node)


def contract_schema(campaign_learned: dict, layers: list[str]) -> dict:
    """The probe's frozen schema: the campaign learned schema, path-exact, with the taskhead contract applied.
    Fails closed unless every touched leaf exists and was numeric in the campaign schema."""
    last = str(max(int(x) for x in layers))
    out = {k: expand_layers(campaign_learned[k], layers) for k in ("metrics", "telemetry_eval_row", "telemetry_train_row")}
    for kind, path in GRAD_PATHS:
        node = out[kind]
        for key in path:
            node = node["dict"][key]
        leaves = node["dict"]
        for l in layers:
            for g in NUM_OR_NULL_GROUPS:
                _set(leaves, f"L{l}/{g}", NUM_OR_NULL)
        for g in REQUIRED_NULL_GROUPS:
            _set(leaves, f"L{last}/{g}", NULL)
    return out


def _set(leaves: dict, key: str, value: dict) -> None:
    if leaves.get(key) != NUM:
        raise ValueError(f"contract leaf {key} is {leaves.get(key)!r} in the campaign schema, not numeric")
    leaves[key] = dict(value)


def exact_schema(obj) -> dict:
    """Structural description with exact keys (the campaign extractor with no layer normalisation)."""
    return V.structural_schema(obj, set(), set())


def conforms(got: dict, frozen: dict) -> bool:
    """`got` (from data) matches `frozen`; only a frozen num_or_null leaf accepts either num or null."""
    if frozen == NUM_OR_NULL:
        return got in (NUM, NULL)
    if "dict" in frozen:
        return ("dict" in got and set(got["dict"]) == set(frozen["dict"])
                and all(conforms(got["dict"][k], v) for k, v in frozen["dict"].items()))
    if "list" in frozen:
        if "list" not in got:
            return False
        if frozen["list"] is None or got["list"] is None:
            return got["list"] == frozen["list"]
        return conforms(got["list"], frozen["list"])
    return got == frozen


def schema_problem(out: Path, schema: dict) -> str | None:
    try:
        metrics = V.strict_json((out / "metrics.json").read_text())
        tele = [V.strict_json(x) for x in (out / "routing_telemetry.jsonl").read_text().splitlines()]
        if not conforms(exact_schema(metrics), schema["metrics"]):
            return "probe schema: metrics differs from the frozen path-exact schema"
        for r in tele:
            kind = "telemetry_eval_row" if "eval" in r else "telemetry_train_row"
            if not conforms(exact_schema(r), schema[kind]):
                return f"probe schema: {kind} at step {r.get('step')} differs from the frozen path-exact schema"
    except (ValueError, KeyError, TypeError) as e:
        return f"probe schema: {e}"
    return None


def validate_probe_outputs(out: Path, done_outputs: dict, pilot: dict, eval_cfg: dict, memsub_sha: str,
                           registry: dict | None, schema: dict | None) -> str | None:
    """None = valid; else the first problem. Registry and schema are REQUIRED (fail closed)."""
    if registry is None or schema is None:
        return "probe validation needs the frozen registry and schema"
    problem = V.validate_cell_outputs(out, done_outputs, pilot, eval_cfg, memsub_sha, registry, None)
    return problem or schema_problem(Path(out), schema)


class ProbeSlotSupervisor(SlotSupervisor):
    """SlotSupervisor whose COMPLETE transition uses the probe validator (narrow copy of `finish`)."""

    def finish(self, cell: str, rc: int) -> None:
        att = self.attempt_dir(cell)
        if rc != 0:
            self.publish(cell, lambda rec: es.mark(rec, es.FAILED, reason=f"worker exit {rc}"))
            return
        try:
            done = json.loads((att / "done.json").read_text())["outputs"]
            problem = validate_probe_outputs(att / "out", done, self.cells[cell], self.eval_cfg,
                                             self.identity["memsub"], self.registry, self.schema)
        except (OSError, ValueError, KeyError, TypeError) as e:
            done, problem = {}, f"done.json unusable: {e!r:.200}"
        if problem is None and self.records[cell]["state"] != es.TRAINED:
            problem = "outputs without the terminal generation"
        if problem:
            self.publish(cell, lambda rec: es.mark(rec, es.FAILED, reason=f"output validation: {problem}"))
            return
        self.commit()                                  # outputs durable BEFORE the COMPLETE pointer
        outputs = {"attempt": str(att.relative_to(self.root)), "files": done}
        self.publish(cell, lambda rec: es.mark(rec, es.COMPLETE, outputs=outputs))

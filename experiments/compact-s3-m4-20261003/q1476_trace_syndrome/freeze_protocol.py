#!/usr/bin/env python3
"""Freeze Q1476 stage IDs, source hashes, inputs, and comparison cells."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
ROOT = HERE.parents[2]
Q1475 = PARENT / "q1475_ordered_leaves"
PROTOCOL = HERE / "protocol.json"
NEW_SOURCES = (
    "experiments/compact-s3-m4-20261003/q1476_trace_syndrome/"
    "design_protocol.json",
    "experiments/compact-s3-m4-20261003/q1476_trace_syndrome/"
    "prepare_inputs.py",
    "experiments/compact-s3-m4-20261003/q1476_trace_syndrome/"
    "validate_trace.py",
    "experiments/compact-s3-m4-20261003/q1476_trace_syndrome/"
    "freeze_protocol.py",
    "experiments/compact-s3-m4-20261003/q1476_trace_syndrome/"
    "run_stage.py",
    "experiments/compact-s3-m4-20261003/q1476_trace_syndrome/"
    "audit.py",
    "experiments/compact-s3-m4-20261003/q1475_ordered_leaves/"
    "protocol.json",
    "experiments/compact-s3-m4-20261003/q1475_ordered_leaves/"
    "input_manifest.json",
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical(value: dict) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def render() -> dict:
    design = json.loads((HERE / "design_protocol.json").read_text())
    manifest = json.loads((HERE / "input_manifest.json").read_text())
    parent = json.loads((Q1475 / "protocol.json").read_text())
    assert design["proposal_id"] == manifest["proposal_id"] == "Q1476"
    assert design["run_order"] == parent["run_order"]
    assert sha(Q1475 / "protocol.json") == design[
        "parent_q1475_protocol_sha256"]
    assert sha(Q1475 / "input_manifest.json") == design[
        "parent_q1475_input_manifest_sha256"]
    assert manifest["design_protocol_sha256"] == sha(HERE /
                                                     "design_protocol.json")
    assert manifest["candidate_id"] is manifest["run_id"] is None
    assert manifest["isogeny"] == "none"
    binary = PARENT / "q1472_sat_work_meter/native_solver"
    binary_sha = sha(binary)
    assert binary_sha == design["parent_native_solver_binary_sha256"]
    source = dict(parent["source_sha256"])
    source.update({name: sha(ROOT / name) for name in NEW_SOURCES})
    validation_path = HERE / "trace_validation.json"
    validation = json.loads(validation_path.read_text())
    assert validation["status"] == "passed"
    assert validation["source_sha256"] == sha(HERE / "validate_trace.py")
    assert validation["runtime_info_sha256"] == sha(HERE /
                                                   "sage_runtime_info.json")
    assert validation["parent_protocol_sha256"] == sha(Q1475 /
                                                       "protocol.json")
    stages = {}
    for n in (53, 83):
        old = parent["stages"][str(n)]
        record = json.loads(json.dumps(old["stage_config_hash_input"]))
        exact = design["curves"][str(n)]
        assert record["curve"]["curve_id"] == exact["curve_id"]
        assert record["factor_base"][
            "actual_usable_points_B_before_folding"] == exact[
                "factor_base_actual_B"]
        assert record["factor_base"]["folded_columns_K"] == exact[
            "folded_columns_K"]
        assert record["factor_base"]["enumerated_set_sha256"] == exact[
            "factor_base_enumerated_set_sha256"]
        assert record["isogeny"] == "none"
        pdp = record["point_decomposition"]
        assert pdp["stage_code"] == "PDP4hybrid"
        assert pdp["solver_binary_sha256"] == binary_sha
        pdp["trace_syndrome_rule"] = (
            "Kosters-Yeo rational-point Tr(x) homomorphism; three exact "
            "normal-basis parity equations at the two pair S3 links "
            "and target S3 link")
        pdp["trace_clause_source_sha256"] = sha(HERE /
                                                 "prepare_inputs.py")
        pdp["parent_ordered_stage_sha256"] = old[
            "stage_config_sha256_full"]
        digest = hashlib.sha256(canonical(record)).hexdigest()
        stages[str(n)] = {
            "stage_config_hash_input": record,
            "stage_config_sha256_full": digest,
            "stage_config_id": (f"PS1N{n}Ckb1fb{exact['factor_base_actual_B']}"
                                f"PDP4hybridh{digest[:12]}"),
            "curve_manifest_sha256": old["curve_manifest_sha256"],
        }
    cells = {}
    for name in design["run_order"]:
        cell = manifest["cases"][name]
        previous = parent["cases"][name]
        n = cell["degree_n"]
        exact = design["curves"][str(n)]
        assert all(cell[key] == exact[key] for key in
                   ("curve_id", "factor_base_actual_B", "folded_columns_K",
                    "factor_base_enumerated_set_sha256"))
        assert cell["workload_id"] == previous["workload_id"]
        assert cell["public_target"] == previous["public_target"]
        assert cell["parent_input_sha256"] == previous["input_sha256"]
        for leaf, digest in cell["input_sha256"].items():
            assert sha(HERE / "inputs" / name / leaf) == digest
        stage_id = stages[str(n)]["stage_config_id"]
        baseline_path = Q1475 / "runs" / name / "receipt.json"
        cells[name] = {
            **cell,
            "stage_config_id": stage_id,
            "stage_run_id": f"{stage_id}W{cell['workload_id']}R1",
            "baseline_receipt_sha256": sha(baseline_path),
        }
    return {
        "kind": "q1476_trace_syndrome_compact_stage_protocol",
        "proposal_id": "Q1476", "candidate_id": None, "run_id": None,
        "isogeny": "none", "point_decomposition_stage_code": "PDP4hybrid",
        "design_protocol_sha256": sha(HERE / "design_protocol.json"),
        "input_manifest_sha256": sha(HERE / "input_manifest.json"),
        "trace_validation_sha256": sha(validation_path),
        "stages": stages, "cases": cells,
        "run_order": design["run_order"],
        "pair_candidate_cap": design["pair_candidate_cap"],
        "conflict_cap": design["conflict_cap"],
        "native_wall_cap_seconds": design["native_wall_cap_seconds"],
        "external_safeguard_seconds": design[
            "external_safeguard_seconds"],
        "decision_policy": design["decision_policy"],
        "solver_binary_sha256": binary_sha,
        "solver_compile_receipt_sha256": sha(PARENT /
            "q1472_sat_work_meter/compile_receipt.json"),
        "runtime_info_sha256": sha(HERE / "sage_runtime_info.json"),
        "field_file_sha256": parent["field_file_sha256"],
        "source_sha256": source,
        "stop_rule": "run all six frozen cells once in order, retaining every status",
        "measurement_units": [
            "exact CaDiCaL propagations, conflicts, and decisions",
            "separate native field mul, sqr, and inv call counts",
            "native wall and peak child RSS; exploratory without isolation",
        ],
        "selection_scope": design["selection_scope"],
        "measurement_scope": design["claim_limit"],
        "natural_relation_yield_estimate": None,
        "complete_n131_log2_work": None,
        "challenge_run_admitted": False,
        "cpu_isolation_receipt": None,
        "controlled_wall_speedup": None,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--emit", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    assert args.emit != args.check
    result = render()
    if args.emit:
        assert not PROTOCOL.exists(), "refuse overwrite"
        PROTOCOL.write_text(json.dumps(result, sort_keys=True,
                                       indent=2) + "\n")
    else:
        assert result == json.loads(PROTOCOL.read_text())
    print(json.dumps({"status": "pass", "stage_config_ids": [
        result["stages"][str(n)]["stage_config_id"] for n in (53, 83)],
        "protocol_sha256": sha(PROTOCOL)}), flush=True)


if __name__ == "__main__":
    main()

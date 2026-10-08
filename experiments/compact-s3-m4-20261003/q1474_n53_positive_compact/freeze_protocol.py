#!/usr/bin/env python3
"""Freeze Q1474's matched, known-representable N53 stage comparison."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
ROOT = HERE.parents[2]
PROTOCOL = HERE / "protocol.json"
CASES = ("pinned_control", "selected_preimage", "full_coset")
CURVE_MANIFEST = (
    "experiments/koblitz-pair-claw-20260929/candidates/"
    "IC1N53Ckb1fb24062PDP4qtableRCdirectLAnoneTDdirectISO0h7c80ef394c64.json"
)
SOURCE_PATHS = (
    "ecc2k130/codegen/curves.py",
    "ecc2k130/codegen/field.py",
    "experiments/compact-s3-m4-20261003/protocol.json",
    "experiments/compact-s3-m4-20261003/run_probe.py",
    "experiments/compact-s3-m4-20261003/chain_s3.py",
    "experiments/compact-s3-m4-20261003/chain_s3_factored.py",
    "experiments/compact-s3-m4-20261003/chain_s3_multitarget.py",
    "experiments/compact-s3-m4-20261003/cofactor_preimages.py",
    "experiments/compact-s3-m4-20261003/s3_root_oracle.py",
    "experiments/compact-s3-m4-20261003/enumerate_q1413_projected_x.py",
    "experiments/koblitz-pair-claw-20260929/orbit_key.py",
    "experiments/compact-s3-m4-20261003/q1419_partial_pin/run_cell.py",
    "experiments/compact-s3-m4-20261003/q1420_root_theory/build_formula.py",
    "experiments/compact-s3-m4-20261003/q1420_root_theory/verify_archive.py",
    "experiments/compact-s3-m4-20261003/q1420_root_theory/root_field.hpp",
    "experiments/compact-s3-m4-20261003/q1420_root_theory/n53_field.txt",
    "experiments/compact-s3-m4-20261003/q1425_reverse_pair/relax_control.py",
    "experiments/compact-s3-m4-20261003/q1438_dense_base/build_formula.py",
    "experiments/compact-s3-m4-20261003/q1467_density_bridge/build_inputs.py",
    "experiments/compact-s3-m4-20261003/q1467_density_bridge/n53_w3_26_orbits.json",
    "experiments/compact-s3-m4-20261003/q1468_n53_pair_oracle/inputs/base_points.txt",
    "experiments/compact-s3-m4-20261003/q1469_n53_yield_panel/panel.json",
    "experiments/compact-s3-m4-20261003/q1469_n53_yield_panel/runs/001/receipt.json",
    "experiments/compact-s3-m4-20261003/q1472_sat_work_meter/native_solver.cpp",
    "experiments/compact-s3-m4-20261003/q1474_n53_positive_compact/prepare_inputs.py",
    "experiments/compact-s3-m4-20261003/q1474_n53_positive_compact/freeze_protocol.py",
    "experiments/compact-s3-m4-20261003/q1474_n53_positive_compact/run_stage.py",
    "experiments/compact-s3-m4-20261003/q1474_n53_positive_compact/audit.py",
    CURVE_MANIFEST,
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical(value: dict) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def render() -> dict:
    manifest_path = HERE / "input_manifest.json"
    manifest = json.loads(manifest_path.read_text())
    parent = json.loads((PARENT / "q1472_sat_work_meter/protocol.json")
                        .read_text())
    curve_manifest = json.loads((ROOT / CURVE_MANIFEST).read_text())
    panel_path = PARENT / "q1469_n53_yield_panel/panel.json"
    pair_receipt = PARENT / "q1469_n53_yield_panel/runs/001/receipt.json"
    panel = json.loads(panel_path.read_text())
    assert manifest["proposal_id"] == "Q1474"
    assert manifest["candidate_id"] is manifest["run_id"] is None
    assert manifest["isogeny"] == "none"
    assert manifest["curve_id"] == panel["curve_id"] == (
        curve_manifest["curve"]["curve_id"])
    assert manifest["factor_base_actual_B"] == 2756
    assert manifest["folded_columns_K"] == 26
    assert manifest["factor_base_enumerated_set_sha256"] == (
        "cf9bb366bb3cd429693e6891d6b0619e8f942a86f3a8308f737795cbaf8b2d70")
    assert manifest["full_raw_preimage_count"] == 428
    assert manifest["raw_witness_preimage_index_in_full_coset"] == 277
    assert parent["pair_candidate_cap"] == 250_000
    assert parent["conflict_cap"] == 1_000_000
    assert parent["wall_cap_seconds"] == 60
    assert parent["decision_policy"] == "joint_tail_leaf_quarter_shift"
    source = {name: sha(ROOT / name) for name in SOURCE_PATHS}
    binary = PARENT / "q1472_sat_work_meter/native_solver"
    binary_sha = sha(binary)
    assert binary_sha == parent["q1472_binary_sha256"]
    fb = {
        "construction": "Q1467 exact selected W<=3 raw ONB x masks; cofactor projection; 26 signed-Frobenius columns",
        "normal_basis_weight_bound": 3,
        "actual_usable_points_B_before_folding": 2756,
        "folded_columns_K": 26,
        "enumerated_set_sha256": manifest[
            "factor_base_enumerated_set_sha256"],
        "selected_raw_x_record_sha256": source[
            "experiments/compact-s3-m4-20261003/q1467_density_bridge/n53_w3_26_orbits.json"],
        "ordered_projected_points_sha256": source[
            "experiments/compact-s3-m4-20261003/q1468_n53_pair_oracle/inputs/base_points.txt"],
    }
    pdp = {
        "m": 4, "stage_code": "PDP4hybrid",
        "summation_tree": "balanced pair-pair S3 over raw x coordinates",
        "leaf_encoding": "exact selected W<=3 masks",
        "final_target_encoding": "one of the listed raw cofactor preimage x values",
        "solver": "Q1472 CaDiCaL native chained-S3 SAT with exact field-root checks",
        "decision_policy": parent["decision_policy"],
        "pair_candidate_cap": parent["pair_candidate_cap"],
        "conflict_cap": parent["conflict_cap"],
        "native_wall_cap_seconds": parent["wall_cap_seconds"],
        "solver_binary_sha256": binary_sha,
        "solver_source_sha256": source[
            "experiments/compact-s3-m4-20261003/q1472_sat_work_meter/native_solver.cpp"],
        "formula_source_sha256": source[
            "experiments/compact-s3-m4-20261003/q1467_density_bridge/build_inputs.py"],
        "field_kernel_sha256": source[
            "experiments/compact-s3-m4-20261003/q1420_root_theory/root_field.hpp"],
        "cache_policy": "cold native process per case",
        "control_pin_policy": "only the pinned_control workload fixes four raw leaf x values",
    }
    stage_record = {
        "field": curve_manifest["field"], "curve": curve_manifest["curve"],
        "isogeny": "none", "factor_base": fb,
        "point_decomposition": pdp,
    }
    digest = hashlib.sha256(canonical(stage_record)).hexdigest()
    stage_id = f"PS1N53Ckb1fb2756PDP4hybridh{digest[:12]}"
    cases = {}
    for name in CASES:
        cell = manifest["cases"][name]
        assert hashlib.sha256(canonical(cell["workload_record"])).hexdigest(
        )[:12] == cell["workload_id"]
        for leaf, expected in cell["input_sha256"].items():
            assert sha(HERE / "inputs" / name / leaf) == expected
        cases[name] = {
            "workload_id": cell["workload_id"],
            "workload_record": cell["workload_record"],
            "stage_run_id": f"{stage_id}W{cell['workload_id']}R1",
            "input_sha256": cell["input_sha256"],
            "cnf_sha256": cell["cnf_sha256"],
            "cnf_variables": cell["cnf_variables"],
            "cnf_clauses": cell["cnf_clauses"],
            "target_preimage_x_count": cell["target_preimage_x_count"],
            "leaves_pinned": cell["leaves_pinned"],
        }
    return {
        "kind": "q1474_n53_matched_positive_compact_stage_protocol",
        "proposal_id": "Q1474", "candidate_id": None, "run_id": None,
        "isogeny": "none", "point_decomposition_stage_code": "PDP4hybrid",
        "stage_config_hash_input": stage_record,
        "stage_config_sha256_full": digest,
        "stage_config_id": stage_id,
        "curve_id": manifest["curve_id"],
        "curve_manifest_sha256": sha(ROOT / CURVE_MANIFEST),
        "factor_base_actual_B": 2756,
        "folded_columns_K": 26,
        "factor_base_enumerated_set_sha256": manifest[
            "factor_base_enumerated_set_sha256"],
        "public_target": manifest["public_target"],
        "matched_q1469_workload_id": manifest[
            "matched_q1469_workload_id"],
        "matched_pair_oracle_receipt_sha256": sha(pair_receipt),
        "input_manifest_sha256": sha(manifest_path),
        "cases": cases, "run_order": list(CASES),
        "pair_candidate_cap": parent["pair_candidate_cap"],
        "conflict_cap": parent["conflict_cap"],
        "wall_cap_seconds": parent["wall_cap_seconds"],
        "external_safeguard_seconds": parent[
            "external_safeguard_seconds"],
        "decision_policy": parent["decision_policy"],
        "solver_binary_sha256": binary_sha,
        "solver_compile_receipt_sha256": sha(PARENT /
            "q1472_sat_work_meter/compile_receipt.json"),
        "runtime_info_sha256": sha(HERE / "sage_runtime_info.json"),
        "source_sha256": source,
        "stop_rule": "run all three frozen cases once under identical native limits; preserve capped and failed attempts; no result-based early stop",
        "measurement_scope": "exploratory matched known-representable ordinary target stage control, selected after Q1469 pair-table success; pinned leaves and chosen raw preimage are controls, not natural yield estimates",
        "measurement_units": {
            "sat_propagations": "exact CaDiCaL reported count",
            "sat_conflicts": "exact CaDiCaL reported count",
            "field_mul_sqr_inv": "separate native binary-field primitive call counts",
            "wall_ns": "exploratory unisolated native solver-process interval",
        },
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
        PROTOCOL.write_text(json.dumps(result, sort_keys=True, indent=2) +
                            "\n")
    else:
        assert result == json.loads(PROTOCOL.read_text())
    print(json.dumps({"status": "pass", "stage_config_id": result[
        "stage_config_id"], "protocol_sha256": sha(PROTOCOL)}), flush=True)


if __name__ == "__main__":
    main()

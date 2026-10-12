#!/usr/bin/env python3
"""Freeze exact Q1475 ordered-leaf stage identities and six input cells."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
ROOT = HERE.parents[2]
PROTOCOL = HERE / "protocol.json"
CASES = (
    "n53_pinned_sorted", "n83_pinned_sorted", "n53_full_coset",
    "n83_planted_unpinned", "n53_ordinary", "n83_ordinary",
)
CURVE_MANIFESTS = {
    53: "experiments/koblitz-pair-claw-20260929/candidates/"
        "IC1N53Ckb1fb24062PDP4qtableRCdirectLAnoneTDdirectISO0h7c80ef394c64.json",
    83: "experiments/koblitz-pair-claw-20260929/candidates/"
        "IC1N83Ckb1fb8000204PDP4qtableRCdirectLAnoneTDdirectISO0h49b47d79e9e3.json",
}
SOURCE_PATHS = (
    "ecc2k130/codegen/curves.py",
    "ecc2k130/codegen/field.py",
    "experiments/compact-s3-m4-20261003/run_probe.py",
    "experiments/compact-s3-m4-20261003/s3_root_oracle.py",
    "experiments/compact-s3-m4-20261003/enumerate_q1413_projected_x.py",
    "experiments/koblitz-pair-claw-20260929/orbit_key.py",
    "experiments/compact-s3-m4-20261003/q1420_root_theory/verify_archive.py",
    "experiments/compact-s3-m4-20261003/q1420_root_theory/root_field.hpp",
    "experiments/compact-s3-m4-20261003/q1420_root_theory/n53_field.txt",
    "experiments/compact-s3-m4-20261003/q1420_root_theory/n83_field.txt",
    "experiments/compact-s3-m4-20261003/q1438_dense_base/build_formula.py",
    "experiments/compact-s3-m4-20261003/q1446_joint_pair_span/theory_solver.cpp",
    "experiments/compact-s3-m4-20261003/q1458_batch_roots/batch_roots.hpp",
    "experiments/compact-s3-m4-20261003/q1467_density_bridge/n53_w3_26_orbits.json",
    "experiments/compact-s3-m4-20261003/runs/n83_q1413_projected_x_w4.json",
    "experiments/compact-s3-m4-20261003/q1472_sat_work_meter/native_solver.cpp",
    "experiments/compact-s3-m4-20261003/q1475_ordered_leaves/design_protocol.json",
    "experiments/compact-s3-m4-20261003/q1475_ordered_leaves/prepare_inputs.py",
    "experiments/compact-s3-m4-20261003/q1475_ordered_leaves/freeze_protocol.py",
    "experiments/compact-s3-m4-20261003/q1475_ordered_leaves/run_stage.py",
    "experiments/compact-s3-m4-20261003/q1475_ordered_leaves/audit.py",
    *CURVE_MANIFESTS.values(),
)
BASELINES = {
    "n53_full_coset": PARENT /
        "q1474_n53_positive_compact/runs/full_coset/receipt.json",
    "n83_planted_unpinned": PARENT /
        "q1472_sat_work_meter/runs/n83_planted_unpinned/receipt.json",
    "n53_ordinary": PARENT /
        "q1472_sat_work_meter/runs/n53_ordinary/receipt.json",
    "n83_ordinary": PARENT /
        "q1472_sat_work_meter/runs/n83_ordinary/receipt.json",
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical(value: dict) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def render() -> dict:
    design = json.loads((HERE / "design_protocol.json").read_text())
    manifest_path = HERE / "input_manifest.json"
    manifest = json.loads(manifest_path.read_text())
    assert design["proposal_id"] == manifest["proposal_id"] == "Q1475"
    assert design["run_order"] == list(CASES)
    assert manifest["design_protocol_sha256"] == sha(HERE /
                                                     "design_protocol.json")
    assert manifest["candidate_id"] is manifest["run_id"] is None
    assert manifest["isogeny"] == "none"
    assert sha(PARENT / "q1474_n53_positive_compact/protocol.json") == (
        design["parent_q1474_protocol_sha256"])
    assert sha(PARENT / "q1467_density_bridge/solver_protocol.json") == (
        design["parent_q1467_solver_protocol_sha256"])
    binary = PARENT / "q1472_sat_work_meter/native_solver"
    binary_sha = sha(binary)
    assert binary_sha == design["native_solver_binary_sha256"]
    source = {name: sha(ROOT / name) for name in SOURCE_PATHS}
    stages = {}
    for n in (53, 83):
        curve_path = CURVE_MANIFESTS[n]
        curve_manifest = json.loads((ROOT / curve_path).read_text())
        exact = design["curves"][str(n)]
        assert curve_manifest["curve"]["curve_id"] == exact["curve_id"]
        fb_source = ("experiments/compact-s3-m4-20261003/"
                     + ("q1467_density_bridge/n53_w3_26_orbits.json"
                        if n == 53 else
                        "runs/n83_q1413_projected_x_w4.json"))
        base = {
            "construction": ("Q1467 selected W<=3 ONB raw x masks"
                             if n == 53 else "Q1467 exact W<=4 ONB raw x masks"),
            "actual_usable_points_B_before_folding": exact[
                "factor_base_actual_B"],
            "folded_columns_K": exact["folded_columns_K"],
            "enumerated_set_sha256": exact[
                "factor_base_enumerated_set_sha256"],
            "normal_basis_weight_bound": 3 if n == 53 else 4,
            "base_record_sha256": source[fb_source],
        }
        pdp = {
            "m": 4, "stage_code": "PDP4hybrid",
            "summation_tree": "balanced pair-pair S3 over raw x coordinates",
            "leaf_symmetry": "strict numeric x0<x1<x2<x3 using ONB-coordinate integers",
            "ordering_source_sha256": source[
                "experiments/compact-s3-m4-20261003/q1475_ordered_leaves/prepare_inputs.py"],
            "solver": "Q1472 CaDiCaL native chained-S3 SAT with exact field-root checks",
            "solver_source_sha256": source[
                "experiments/compact-s3-m4-20261003/q1472_sat_work_meter/native_solver.cpp"],
            "solver_binary_sha256": binary_sha,
            "decision_policy": design["decision_policy"],
            "pair_candidate_cap": design["pair_candidate_cap"],
            "conflict_cap": design["conflict_cap"],
            "native_wall_cap_seconds": design["native_wall_cap_seconds"],
            "cache_policy": "cold native process per case",
            "control_pin_policy": "only sorted pinned control workloads fix the four raw leaf x values",
        }
        stage_record = {
            "field": curve_manifest["field"],
            "curve": curve_manifest["curve"],
            "isogeny": "none", "factor_base": base,
            "point_decomposition": pdp,
        }
        digest = hashlib.sha256(canonical(stage_record)).hexdigest()
        stage_id = (f"PS1N{n}Ckb1fb{exact['factor_base_actual_B']}"
                    f"PDP4hybridh{digest[:12]}")
        stages[str(n)] = {
            "stage_config_hash_input": stage_record,
            "stage_config_sha256_full": digest,
            "stage_config_id": stage_id,
            "curve_manifest_sha256": sha(ROOT / curve_path),
        }
    cells = {}
    for name in CASES:
        cell = manifest["cases"][name]
        n = cell["degree_n"]
        exact = design["curves"][str(n)]
        assert all(cell[key] == exact[key] for key in
                   ("curve_id", "factor_base_actual_B", "folded_columns_K",
                    "factor_base_enumerated_set_sha256"))
        for leaf, digest in cell["input_sha256"].items():
            assert sha(HERE / "inputs" / name / leaf) == digest
        stage_id = stages[str(n)]["stage_config_id"]
        cells[name] = {
            **cell,
            "stage_config_id": stage_id,
            "stage_run_id": f"{stage_id}W{cell['workload_id']}R1",
            "baseline_receipt_sha256": (sha(BASELINES[name])
                                         if name in BASELINES else None),
        }
    return {
        "kind": "q1475_ordered_leaf_compact_stage_protocol",
        "proposal_id": "Q1475", "candidate_id": None, "run_id": None,
        "isogeny": "none", "point_decomposition_stage_code": "PDP4hybrid",
        "design_protocol_sha256": sha(HERE / "design_protocol.json"),
        "input_manifest_sha256": sha(manifest_path),
        "stages": stages, "cases": cells, "run_order": list(CASES),
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
        "field_file_sha256": {
            str(n): source[f"experiments/compact-s3-m4-20261003/"
                           f"q1420_root_theory/n{n}_field.txt"]
            for n in (53, 83)},
        "source_sha256": source,
        "stop_rule": design["stop_rule"],
        "measurement_scope": design["claim_limit"],
        "measurement_units": design["measurement_units"],
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
    print(json.dumps({"status": "pass", "stage_config_ids": [
        result["stages"][str(n)]["stage_config_id"] for n in (53, 83)],
        "protocol_sha256": sha(PROTOCOL)}), flush=True)


if __name__ == "__main__":
    main()

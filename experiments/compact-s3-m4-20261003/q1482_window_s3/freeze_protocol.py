#!/usr/bin/env python3
"""Freeze Q1482 stage IDs, exact inputs, source, binary, and limits."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
ROOT = HERE.parents[2]
Q1481 = PARENT / "q1481_window_orbit_base"
Q1480 = PARENT / "q1480_conditioned_join"
Q1438 = PARENT / "q1438_dense_base"
PROTOCOL = HERE / "protocol.json"

NEW_SOURCES = (
    "design_protocol.json", "make_planted.py", "build_formula.py",
    "verify_model.py", "prepare_inputs.py", "freeze_protocol.py",
    "run_stage.py", "audit.py",
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical(value: dict) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def render() -> dict:
    design = json.loads((HERE / "design_protocol.json").read_text())
    q1481 = json.loads((Q1481 / "protocol.json").read_text())
    q1480 = json.loads((Q1480 / "protocol.json").read_text())
    q1438 = json.loads((Q1438 / "solver_protocol.json").read_text())
    assert design["proposal_id"] == "Q1482"
    assert q1481["proposal_id"] == "Q1481"
    assert q1480["proposal_id"] == "Q1480"
    assert q1438["proposal_id"] == "Q1438"
    assert q1480["solver_binary_sha256"] == sha(Q1480 / "native_solver")
    assert design["point_decomposition"]["solver_wall_cap_seconds"] == (
        q1480["native_wall_cap_seconds"])
    assert design["point_decomposition"][
        "external_process_safeguard_seconds"] == q1480[
            "external_safeguard_seconds"]
    assert design["point_decomposition"]["solver_conflict_cap"] == (
        q1480["conflict_cap"])
    runtime_path = HERE / "sage_runtime_info.json"
    assert json.loads(runtime_path.read_text())["status"] == "verified"

    source = dict(q1480["source_sha256"])
    source.update(q1481["dependency_sha256"])
    q1481_prefix = "experiments/compact-s3-m4-20261003/q1481_window_orbit_base/"
    source.update({q1481_prefix + name: digest for name, digest
                   in q1481["source_sha256"].items()})
    q1482_prefix = "experiments/compact-s3-m4-20261003/q1482_window_s3/"
    source.update({q1482_prefix + name: sha(HERE / name)
                   for name in NEW_SOURCES})
    source.update({
        q1481_prefix + "protocol.json": sha(Q1481 / "protocol.json"),
        "experiments/compact-s3-m4-20261003/q1480_conditioned_join/"
        "protocol.json": sha(Q1480 / "protocol.json"),
        "experiments/compact-s3-m4-20261003/q1438_dense_base/"
        "solver_protocol.json": sha(Q1438 / "solver_protocol.json"),
    })
    for relative, digest in source.items():
        assert sha(ROOT / relative) == digest, relative

    stages = {}
    for n in (53, 83):
        item = design["instances"][str(n)]
        base_protocol = q1481["instances"][str(n)]
        d = item["nominal_window_dimension_d"]
        base_path = Q1481 / f"n{n}_d{d}_base.json"
        packed_path = Q1481 / f"n{n}_d{d}_projected_keys.bin"
        base = json.loads(base_path.read_text())
        assert base["actual_usable_points_B_before_folding"] == item[
            "actual_usable_B"]
        assert base["signed_frobenius_columns_K"] == item["folded_K"]
        assert base["enumerated_set_sha256"] == item[
            "enumerated_set_sha256"] == sha(packed_path)
        record = {
            "field": base_protocol["field"],
            "curve": base_protocol["curve"],
            "isogeny": "none",
            "factor_base": {
                "construction": (
                    "Frobenius orbit union of normal-basis cyclic "
                    "coordinate windows; rational lift, cofactor "
                    "projection, identity and duplicate filtering"),
                "nominal_window_dimension_d": d,
                "nominal_raw_x_orbits": base["nominal_raw_x_orbits"],
                "actual_usable_points_B_before_folding": item[
                    "actual_usable_B"],
                "signed_frobenius_columns": item["folded_K"],
                "enumerated_set_sha256": item[
                    "enumerated_set_sha256"],
                "enumeration_receipt_sha256": sha(base_path),
                "sign_frobenius_quotient": (
                    "one column per projected x orbit; both signs and "
                    "all n Frobenius powers expand each key"),
            },
            "point_decomposition": {
                "stage_code": "PDP4hybrid", "m": 4,
                "summation_tree": (
                    "balanced pair-pair chained S3 over raw x coordinates"),
                "formula_policy": (
                    "Q1482 exact cyclic-window leaf clauses, compact "
                    "right and final S3 CNF, native exact first-pair roots"),
                "formula_source_sha256": sha(HERE / "build_formula.py"),
                "control_pins_belong_to_workload": True,
                "solver": "Q1480 native SAT plus exact S3 theory",
                "solver_source_sha256": sha(Q1480 / "native_solver.cpp"),
                "solver_binary_sha256": sha(Q1480 / "native_solver"),
                "decision_policy": q1480["decision_policy"],
                "theory_hamming_weight_superset_bound": d,
                "pair_candidate_cap": q1480["pair_candidate_cap"],
                "domain_pair_cap": q1480["domain_pair_cap"],
                "domain_cache_cap": q1480["domain_cache_cap"],
                "sat_conflict_cap": q1480["conflict_cap"],
                "native_wall_cap_seconds": q1480[
                    "native_wall_cap_seconds"],
            },
        }
        digest = hashlib.sha256(canonical(record)).hexdigest()
        stages[str(n)] = {
            "stage_config_hash_input": record,
            "stage_config_sha256_full": digest,
            "stage_config_id": (
                f"PS1N{n}Ckb1fb{item['actual_usable_B']}"
                f"PDP4hybridh{digest[:12]}"),
        }

    cases = {}
    for case in design["run_order"]:
        n_text, role = case.split("_", 1)
        n = int(n_text[1:])
        item = design["instances"][str(n)]
        folder = HERE / "inputs" / case
        input_path = folder / "input.json"
        input_receipt = json.loads(input_path.read_text())
        assert input_receipt["proposal_id"] == "Q1482"
        assert input_receipt["candidate_id"] is None
        assert input_receipt["case"] == case
        assert input_receipt["curve_id"] == item["curve_id"]
        assert input_receipt["factor_base_actual_B"] == item[
            "actual_usable_B"]
        assert input_receipt["folded_columns_K"] == item["folded_K"]
        assert input_receipt["factor_base_enumerated_set_sha256"] == item[
            "enumerated_set_sha256"]
        assert input_receipt["design_sha256"] == sha(HERE /
                                                     "design_protocol.json")
        for name, digest in input_receipt["input_sha256"].items():
            assert sha(folder / name) == digest
        raw = gzip.decompress((folder / "system.cnf.gz").read_bytes())
        assert hashlib.sha256(raw).hexdigest() == input_receipt[
            "cnf_raw_sha256"]
        if role == "ordinary":
            old = q1438["workloads"][case]
            workload_id = item["ordinary_parent_workload_id"]
            assert old["workload_id"] == workload_id
            assert input_receipt["input_sha256"]["targets.txt"] == item[
                "ordinary_target_input_sha256"]
            parent_workload_id = workload_id
        else:
            workload_record = {
                "curve_id": item["curve_id"],
                "public_target": input_receipt["public_target"],
                "target_preimage_x_count": input_receipt[
                    "target_preimage_x_count"],
                "fixture_sha256": input_receipt[
                    "planted_fixture_sha256"],
                "input_law": role,
                "target_count": 1,
            }
            workload_id = hashlib.sha256(canonical(workload_record))\
                .hexdigest()[:12]
            parent_workload_id = None
        stage_id = stages[str(n)]["stage_config_id"]
        cases[case] = {
            "degree_n": n, "role": role,
            "curve_id": item["curve_id"],
            "factor_base_actual_B": item["actual_usable_B"],
            "folded_columns_K": item["folded_K"],
            "factor_base_enumerated_set_sha256": item[
                "enumerated_set_sha256"],
            "public_target": input_receipt["public_target"],
            "target_preimage_x_count": input_receipt[
                "target_preimage_x_count"],
            "workload_id": workload_id,
            "parent_workload_id": parent_workload_id,
            "stage_config_id": stage_id,
            "stage_run_id": f"{stage_id}W{workload_id}R1",
            "input_dir": str(folder.relative_to(ROOT)),
            "input_receipt_sha256": sha(input_path),
            "input_sha256": input_receipt["input_sha256"],
            "cnf_raw_sha256": input_receipt["cnf_raw_sha256"],
            "cnf_variables": input_receipt["cnf_variables"],
            "cnf_clauses": input_receipt["cnf_clauses"],
        }
    return {
        "kind": "q1482_frozen_window_orbit_compact_s3_stage_protocol",
        "proposal_id": "Q1482", "candidate_id": None,
        "run_id": None, "isogeny": "none",
        "point_decomposition_stage_code": "PDP4hybrid",
        "design_sha256": sha(HERE / "design_protocol.json"),
        "q1481_base_protocol_sha256": sha(Q1481 / "protocol.json"),
        "q1480_solver_protocol_sha256": sha(Q1480 / "protocol.json"),
        "q1438_solver_protocol_sha256": sha(Q1438 / "solver_protocol.json"),
        "stages": stages, "cases": cases,
        "run_order": design["run_order"],
        "pair_candidate_cap": q1480["pair_candidate_cap"],
        "domain_pair_cap": q1480["domain_pair_cap"],
        "domain_cache_cap": q1480["domain_cache_cap"],
        "conflict_cap": q1480["conflict_cap"],
        "native_wall_cap_seconds": q1480["native_wall_cap_seconds"],
        "external_safeguard_seconds": q1480[
            "external_safeguard_seconds"],
        "decision_policy": q1480["decision_policy"],
        "solver_binary_sha256": sha(Q1480 / "native_solver"),
        "solver_compile_receipt_sha256": sha(Q1480 /
                                             "compile_receipt.json"),
        "runtime_info_sha256": sha(runtime_path),
        "field_file_sha256": {str(n): sha(PARENT /
                f"q1420_root_theory/n{n}_field.txt") for n in (53, 83)},
        "source_sha256": source,
        "stop_rule": "run six frozen cells once in design order, retaining all statuses",
        "measurement_units": (
            "Exact SAT propagations/conflicts and direct field "
            "mul/sqr/inv calls; exploratory encoding, materialization, "
            "native-process and relation-check wall nanoseconds; peak "
            "child RSS. No calibrated common operation unit."),
        "measurement_scope": design["claim_scope"],
        "natural_relation_yield_estimate": None,
        "complete_n131_log2_work": None,
        "challenge_run_admitted": False,
        "cpu_isolation_receipt": None,
        "controlled_wall_speedup": None,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    data = render()
    if args.check or PROTOCOL.exists():
        assert json.loads(PROTOCOL.read_text()) == data
        print("Q1482 stage protocol verified")
    else:
        PROTOCOL.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
        print("Q1482 stage protocol frozen")


if __name__ == "__main__":
    main()

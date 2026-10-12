#!/usr/bin/env python3
"""Freeze Q1480 stage identities, source, exact archived inputs, and limits."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
ROOT = HERE.parents[2]
Q1476 = PARENT / "q1476_trace_syndrome"
Q1479 = PARENT / "q1479_target_mid_domain"
Q1438 = PARENT / "q1438_dense_base"
PROTOCOL = HERE / "protocol.json"
NEW_SOURCES = (
    "design_protocol.json", "native_solver.cpp", "build.py",
    "validate_conditioned.py", "freeze_protocol.py", "run_stage.py",
    "audit.py",
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical(value: dict) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def stage_record(source: dict, formula: str, formula_sha: str,
                 design: dict, binary_sha: str, native_sha: str) -> dict:
    record = json.loads(json.dumps(source))
    assert record["isogeny"] == "none"
    record["point_decomposition"] = {
        "stage_code": "PDP4hybrid",
        "m": 4,
        "summation_tree": "balanced pair-pair chained S3 over raw x coordinates",
        "formula_policy": formula,
        "formula_source_sha256": formula_sha,
        "control_pins_belong_to_workload": True,
        "solver": design["method"]["solver_family"],
        "solver_source_sha256": native_sha,
        "solver_binary_sha256": binary_sha,
        "decision_policy": "target_mid_domain_conditioned_pair_eval",
        "partial_left_pair_cap": design["method"]["left_pair_domain_cap"],
        "conditioned_pair_cap_per_side": design["method"][
            "conditioned_pair_feasibility_cap_per_side"],
        "conditioned_rule": design["method"]["rule"],
        "soundness_boundary": design["method"]["soundness_boundary"],
        "cache_policy": design["method"]["cache_policy"],
        "sat_conflict_cap": design["limits"]["sat_conflicts_per_case"],
        "native_wall_cap_seconds": design["limits"][
            "native_wall_seconds_per_case"],
    }
    return record


def render() -> dict:
    design = json.loads((HERE / "design_protocol.json").read_text())
    parent = json.loads((Q1479 / "protocol.json").read_text())
    q1476 = json.loads((Q1476 / "protocol.json").read_text())
    q1438 = json.loads((Q1438 / "solver_protocol.json").read_text())
    build = json.loads((HERE / "compile_receipt.json").read_text())
    validation = json.loads((HERE / "conditioned_validation.json").read_text())
    assert design["proposal_id"] == build["proposal_id"] == "Q1480"
    assert parent["proposal_id"] == "Q1479"
    assert q1438["proposal_id"] == "Q1438"
    assert validation["status"] == "passed"
    assert validation["source_sha256"] == sha(HERE /
                                               "validate_conditioned.py")
    assert validation["runtime_info_sha256"] == sha(HERE /
                                                   "sage_runtime_info.json")
    binary_sha = sha(HERE / "native_solver")
    native_sha = sha(HERE / "native_solver.cpp")
    assert build["solver_binary_sha256"] == binary_sha
    assert build["source_sha256"]["native_solver.cpp"] == native_sha
    source = dict(parent["source_sha256"])
    source.update(q1438["dependency_sha256"])
    q1438_prefix = "experiments/compact-s3-m4-20261003/q1438_dense_base/"
    source.update({q1438_prefix + name: digest for name, digest in
                   q1438["source_sha256"].items()})
    q1480_prefix = "experiments/compact-s3-m4-20261003/q1480_conditioned_join/"
    source.update({q1480_prefix + name: sha(HERE / name)
                   for name in NEW_SOURCES})
    source.update({
        "experiments/compact-s3-m4-20261003/q1479_target_mid_domain/"
        "protocol.json": sha(Q1479 / "protocol.json"),
        q1438_prefix + "solver_protocol.json": sha(Q1438 /
                                                    "solver_protocol.json"),
    })
    for relative, digest in source.items():
        assert sha(ROOT / relative) == digest, relative
    stages = {}
    for n in (53, 83):
        for origin in ("q1476", "q1438"):
            if origin == "q1476":
                source_record = q1476["stages"][str(n)][
                    "stage_config_hash_input"]
                formula = "Q1476 ordered-leaf trace-syndrome compact S3 CNF"
                formula_sha = sha(Q1476 / "prepare_inputs.py")
            else:
                source_record = q1438["workloads"][f"n{n}_ordinary"][
                    "stage_config_hash_input"]
                formula = ("Q1438 factored final and right S3 CNF with "
                           "native exact left-pair oracle")
                formula_sha = sha(Q1438 / "build_formula.py")
            record = stage_record(source_record, formula, formula_sha,
                                  design, binary_sha, native_sha)
            base = record["factor_base"]
            actual_b = base["actual_usable_points_B_before_folding"]
            if origin == "q1438":
                exact = design["production_bases"][str(n)]
                assert record["curve"]["curve_id"] == exact["curve_id"]
                assert actual_b == exact["factor_base_actual_B"]
                assert base["signed_frobenius_columns"] == exact[
                    "folded_columns_K"]
                assert base["enumerated_set_sha256"] == exact[
                    "factor_base_enumerated_set_sha256"]
            digest = hashlib.sha256(canonical(record)).hexdigest()
            stages[f"{origin}_{n}"] = {
                "stage_config_hash_input": record,
                "stage_config_sha256_full": digest,
                "stage_config_id":
                    f"PS1N{n}Ckb1fb{actual_b}PDP4hybridh{digest[:12]}",
            }
    cases = {}
    for name in design["run_order"]:
        n = 53 if name.startswith("n53") else 83
        if "q1476" in name:
            source_name = f"n{n}_pinned_sorted"
            old = q1476["cases"][source_name]
            folder = Q1476 / "inputs" / source_name
            input_sha = old["input_sha256"]
            raw_sha = old["cnf_sha256"]
            entry = {
                "input_source": "Q1476", "source_case": source_name,
                "degree_n": n,
                "input_dir": str(folder.relative_to(ROOT)),
                "input_sha256": input_sha,
                "cnf_raw_sha256": raw_sha,
                "cnf_variables": old["cnf_variables"],
                "cnf_clauses": old["cnf_clauses"],
                "target_preimage_x_count": old["target_preimage_x_count"],
                "curve_id": old["curve_id"],
                "factor_base_actual_B": old["factor_base_actual_B"],
                "folded_columns_K": old["folded_columns_K"],
                "factor_base_enumerated_set_sha256": old[
                    "factor_base_enumerated_set_sha256"],
                "workload_id": old["workload_id"],
                "public_target": old["public_target"],
                "input_role": "pinned_sorted_correctness_control",
                "parent_receipt_sha256": sha(Q1476 / "runs" / source_name /
                                             "receipt.json"),
            }
            stage_key = f"q1476_{n}"
        else:
            source_name = name.removeprefix(f"n{n}_q1438_")
            source_name = f"n{n}_{source_name}"
            old = q1438["workloads"][source_name]
            folder = Q1438 / "runs" / source_name
            input_sha = {leaf: sha(folder / leaf) for leaf in
                         ("system.cnf.gz", "variables.txt", "targets.txt")}
            assert input_sha["system.cnf.gz"] == sha(folder /
                                                    "system.cnf.gz")
            assert old["variable_map_sha256"] == input_sha["variables.txt"]
            assert old["target_input_sha256"] == input_sha["targets.txt"]
            raw_sha = old["cnf_raw_sha256"]
            entry = {
                "input_source": "Q1438", "source_case": source_name,
                "degree_n": n,
                "input_dir": str(folder.relative_to(ROOT)),
                "input_sha256": input_sha,
                "cnf_raw_sha256": raw_sha,
                "cnf_variables": old["cnf_variables"],
                "cnf_clauses": old["cnf_clauses"],
                "target_preimage_x_count": old["target_preimage_x_count"],
                "curve_id": old["curve_id"],
                "factor_base_actual_B": old["factor_base_actual_B"],
                "folded_columns_K": old["folded_columns_K"],
                "factor_base_enumerated_set_sha256": old[
                    "factor_base_enumerated_set_sha256"],
                "workload_id": old["workload_id"],
                "public_target": old["public_target"],
                "input_role": old["input_law"],
                "parent_receipt_sha256": sha(folder / "receipt.json"),
                "factor_base_receipt_sha256": old[
                    "factor_base_receipt_sha256"],
            }
            stage_key = f"q1438_{n}"
        for leaf, digest in input_sha.items():
            assert sha(folder / leaf) == digest
        raw = gzip.decompress((folder / "system.cnf.gz").read_bytes())
        assert hashlib.sha256(raw).hexdigest() == raw_sha
        stage_id = stages[stage_key]["stage_config_id"]
        entry["stage_config_id"] = stage_id
        entry["stage_run_id"] = f"{stage_id}W{entry['workload_id']}R1"
        cases[name] = entry
    return {
        "kind": "q1480_midpoint_conditioned_dense_base_stage_protocol",
        "proposal_id": "Q1480", "candidate_id": None, "run_id": None,
        "isogeny": "none", "point_decomposition_stage_code": "PDP4hybrid",
        "design_protocol_sha256": sha(HERE / "design_protocol.json"),
        "parent_q1479_protocol_sha256": sha(Q1479 / "protocol.json"),
        "q1438_solver_protocol_sha256": sha(Q1438 / "solver_protocol.json"),
        "conditioned_validation_sha256": sha(HERE /
                                             "conditioned_validation.json"),
        "stages": stages, "cases": cases, "run_order": design["run_order"],
        "pair_candidate_cap": design["method"][
            "conditioned_pair_feasibility_cap_per_side"],
        "domain_pair_cap": design["method"]["left_pair_domain_cap"],
        "domain_cache_cap": design["limits"][
            "partial_midpoint_domain_cache_entries"],
        "conflict_cap": design["limits"]["sat_conflicts_per_case"],
        "native_wall_cap_seconds": design["limits"][
            "native_wall_seconds_per_case"],
        "external_safeguard_seconds": design["limits"][
            "external_safeguard_seconds_per_case"],
        "decision_policy": "target_mid_domain_conditioned_pair_eval",
        "solver_binary_sha256": binary_sha,
        "solver_compile_receipt_sha256": sha(HERE / "compile_receipt.json"),
        "runtime_info_sha256": sha(HERE / "sage_runtime_info.json"),
        "field_file_sha256": parent["field_file_sha256"],
        "source_sha256": source,
        "stop_rule": "run six frozen cells once in design order, retaining all statuses",
        "measurement_units": design["measurements"],
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
        PROTOCOL.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    else:
        assert result == json.loads(PROTOCOL.read_text())
    print(json.dumps({"status": "pass", "stage_config_ids": {
        key: row["stage_config_id"] for key, row in result["stages"].items()},
        "protocol_sha256": sha(PROTOCOL)}, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()

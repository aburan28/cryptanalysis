#!/usr/bin/env python3
"""Freeze Q1422 sound leaf-lift gate on matched Q1421 workloads."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "q1420_root_theory"
MATCH = HERE.parent / "q1421_work_counted"
PROTOCOL = HERE / "protocol.json"
SOURCE_NAMES = ("build_binaries.py", "freeze_protocol.py", "run_stage.py",
                "theory_solver.cpp", "verify_archive.py", "lift_gate.hpp",
                "lift_gate_cli.cpp", "validate_lift_gate.py")
DEPENDENCY_NAMES = ("root_field.hpp", "build_formula.py",
                    "verify_archive.py")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def digest(value):
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"),
                     ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def build():
    parent_protocol_path = PARENT / "protocol.json"
    parent = json.loads(parent_protocol_path.read_text())
    matched_protocol_path = MATCH / "protocol.json"
    matched = json.loads(matched_protocol_path.read_text())
    compiler_path = HERE / "compile_receipt.json"
    compiler = json.loads(compiler_path.read_text())
    runtime_path = HERE / "sage_runtime_info.json"
    runtime = json.loads(runtime_path.read_text())
    assert runtime["status"] == "verified"
    for name, expected in compiler["source_sha256"].items():
        assert sha(HERE / name) == expected
    for name, expected in compiler["binary_sha256"].items():
        assert sha(HERE / name) == expected
    assert compiler["root_field_header_sha256"] == sha(
        PARENT / "root_field.hpp")
    validations = {}
    for n in (53, 83):
        path = HERE / f"n{n}_lift_validation.json"
        row = json.loads(path.read_text())
        assert row["proposal_id"] == "Q1422" and row["status"] == "PASS"
        assert row["degree_n"] == n
        assert row["lift_gate_cli_binary_sha256"] == compiler[
            "binary_sha256"]["lift_gate_cli"]
        validations[str(n)] = sha(path)
    sources = {name: sha(HERE / name) for name in SOURCE_NAMES}
    dependencies = {name: sha(PARENT / name) for name in DEPENDENCY_NAMES}
    workloads = {}
    for n in (53, 83):
        for cell in ("free_mids", "ordinary"):
            parent_key = f"n{n}_{cell}"
            matched_key = f"{parent_key}_leaf_first"
            parent_workload = parent["workloads"][parent_key]
            matched_workload = matched["workloads"][matched_key]
            assert parent_workload["workload_id"] == matched_workload[
                "workload_id"]
            parent_dir = PARENT / "runs" / parent_key
            parent_receipt_path = parent_dir / "receipt.json"
            matched_receipt_path = MATCH / "runs" / matched_key / "receipt.json"
            parent_receipt = json.loads(parent_receipt_path.read_text())
            matched_receipt = json.loads(matched_receipt_path.read_text())
            assert matched_receipt["stage_run_id"] == matched_workload[
                "stage_run_id"]
            assert matched_receipt["solver_status"] in ("sat", "censored")
            config = dict(matched_workload["stage_config_hash_input"])
            pdp = dict(config["point_decomposition"])
            pdp["decision_policy"] = (
                "external cb_decide chooses first unassigned leaf bit "
                "positive; exact nonzero-x curve-lift gate")
            pdp["leaf_lift_gate"] = (
                "Tr(x+x^-1)=0 on y^2+xy=x^3+1; check each fully assigned "
                "leaf, forbid a failed x using full cube or maximal-weight "
                "positive support")
            pdp["source_sha256"] = {
                "parent_build_formula.py": dependencies["build_formula.py"],
                "parent_root_field.hpp": dependencies["root_field.hpp"],
                "theory_solver.cpp": sources["theory_solver.cpp"],
                "lift_gate.hpp": sources["lift_gate.hpp"],
            }
            pdp["solver_binary_sha256"] = compiler[
                "binary_sha256"]["theory_solver"]
            config["point_decomposition"] = pdp
            full = digest(config)
            stage = (f"PS1N{n}Ckb1fb{parent_workload['factor_base_actual_B']}"
                     f"PDP4theoryh{full[:12]}")
            key = f"{parent_key}_lift"
            workloads[key] = {
                "parent_key": parent_key,
                "parent_stage_run_id": parent_workload["stage_run_id"],
                "parent_receipt_sha256": sha(parent_receipt_path),
                "parent_meta_sha256": sha(parent_dir / "meta.json"),
                "parent_cnf_archive_sha256": sha(
                    parent_dir / "system.cnf.gz"),
                "parent_variable_map_sha256": sha(
                    parent_dir / "variables.txt"),
                "matched_q1421_key": matched_key,
                "matched_q1421_stage_run_id": matched_workload[
                    "stage_run_id"],
                "matched_q1421_receipt_sha256": sha(matched_receipt_path),
                "curve_id": parent_workload["curve_id"],
                "factor_base_actual_B": parent_workload[
                    "factor_base_actual_B"],
                "folded_columns_K": parent_workload["folded_columns_K"],
                "factor_base_enumerated_set_sha256": parent_workload[
                    "factor_base_enumerated_set_sha256"],
                "public_target": parent_workload["public_target"],
                "decision_policy": "leaf_first_lift",
                "input_law": parent_receipt["input_law"],
                "workload_record": parent_workload["workload_record"],
                "workload_id": parent_workload["workload_id"],
                "stage_config_hash_input": config,
                "stage_config_sha256_full": full,
                "stage_config_id": stage,
                "stage_run_id": (f"{stage}W{parent_workload['workload_id']}R1"),
            }
    return {
        "kind": "q1422_frozen_exact_leaf_lift_gate_protocol",
        "proposal_id": "Q1422", "candidate_id": None, "isogeny": "none",
        "question": (
            "Does the exact rational-leaf lift gate reduce unpinned "
            "four-point search work and recover ordinary N53/N83 relations "
            "under the matched Q1421 leaf-first cap?"),
        "parent_q1420_protocol_sha256": sha(parent_protocol_path),
        "matched_q1421_protocol_sha256": sha(matched_protocol_path),
        "workloads": workloads,
        "run_order": [f"n{n}_{cell}_lift" for n in (53, 83)
                      for cell in ("free_mids", "ordinary")],
        "solver_conflict_cap": 1_000_000,
        "solver_wall_cap_seconds": 60,
        "external_process_safeguard_seconds": 75,
        "solver_binary_sha256": compiler["binary_sha256"]["theory_solver"],
        "compile_receipt_sha256": sha(compiler_path),
        "sage_runtime_info_sha256": sha(runtime_path),
        "lift_validation_sha256": validations,
        "source_sha256": sources,
        "dependency_sha256": dependencies,
        "claim_boundary": (
            "The exact leaf-lift gate is a necessary field/curve condition "
            "for nonzero raw x, not a complete factor-base membership test. "
            "Controls validate correctness only. One ordinary point per "
            "degree is a solver gate, not natural yield. CPU wall time is "
            "exploratory on an unisolated host. Formula build, complete "
            "relation collection, matrix solve, descent and replay are "
            "not supplied by this stage."),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    raw = json.dumps(build(), sort_keys=True, indent=2) + "\n"
    if args.check:
        assert PROTOCOL.read_text() == raw
    else:
        assert not PROTOCOL.exists()
        PROTOCOL.write_text(raw)
    print(PROTOCOL)


if __name__ == "__main__":
    main()

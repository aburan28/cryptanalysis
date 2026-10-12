#!/usr/bin/env python3
"""Freeze Q1426 symbolic second-pair S3 cells before ordinary runs."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
sys.path.insert(0, str(PARENT))

from q1423_target_coupled.target_inputs import (  # noqa: E402
    encode_targets, target_list)
from q1426_symbolic_pair.build_formula import build_cnf  # noqa: E402

Q1420 = PARENT / "q1420_root_theory"
Q1425 = PARENT / "q1425_reverse_pair"
Q1423 = PARENT / "q1423_target_coupled"
LIFT = PARENT / "q1422_leaf_lift_gate"
PROTOCOL = HERE / "protocol.json"
SOURCE_NAMES = ("build_formula.py", "freeze_protocol.py", "run_stage.py",
                "verify_archive.py")
DEPENDENCIES = {
    "chain_s3.py": PARENT / "chain_s3.py",
    "chain_s3_factored.py": PARENT / "chain_s3_factored.py",
    "q1420_build_formula.py": Q1420 / "build_formula.py",
    "q1420_verify_archive.py": Q1420 / "verify_archive.py",
    "q1420_root_field.hpp": Q1420 / "root_field.hpp",
    "q1422_lift_gate.hpp": LIFT / "lift_gate.hpp",
    "q1423_target_inputs.py": Q1423 / "target_inputs.py",
    "q1425_relax_control.py": Q1425 / "relax_control.py",
    "q1425_theory_solver.cpp": Q1425 / "theory_solver.cpp",
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def digest(value) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"),
                     ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def build() -> dict:
    parent_path = Q1420 / "protocol.json"
    match_path = Q1425 / "protocol.json"
    parent = json.loads(parent_path.read_text())
    match = json.loads(match_path.read_text())
    compile_path = Q1425 / "compile_receipt.json"
    compiler = json.loads(compile_path.read_text())
    binary = Q1425 / "theory_solver"
    runtime_path = HERE / "sage_runtime_info.json"
    runtime = json.loads(runtime_path.read_text())
    assert runtime["status"] == "verified"
    assert compiler["binary_sha256"] == sha(binary)
    assert compiler["source_sha256"] == sha(
        DEPENDENCIES["q1425_theory_solver.cpp"])
    sources = {name: sha(HERE / name) for name in SOURCE_NAMES}
    dependencies = {name: sha(path) for name, path in DEPENDENCIES.items()}
    workloads = {}
    for n in (53, 83):
        for cell in ("free_partner", "ordinary"):
            key = f"n{n}_{cell}"
            matched_key = f"{key}_reverse_target"
            matched_workload = match["workloads"][matched_key]
            matched_receipt_path = (Q1425 / "runs" / matched_key /
                                    "receipt.json")
            matched_receipt = json.loads(matched_receipt_path.read_text())
            assert matched_receipt["stage_run_id"] == matched_workload[
                "stage_run_id"]
            assert matched_receipt["solver_status"] in ("sat", "censored")
            parent_key = matched_workload["parent_key"]
            parent_workload = parent["workloads"][parent_key]
            assert matched_workload["workload_id"] == parent_workload[
                "workload_id"]
            target_bytes = encode_targets(
                n, target_list(n, "free_mids" if cell == "free_partner"
                               else "ordinary", parent_workload))
            target_hash = hashlib.sha256(target_bytes).hexdigest()
            assert target_hash == matched_workload["target_input_sha256"]
            raw, _, meta, removed, variables, clauses = build_cnf(n, cell)
            assert removed == matched_workload["removed_partner_pin_units"]
            assert meta["curve_id"] == matched_workload["curve_id"]
            assert meta["factor_base_enumerated_set_sha256"] == (
                matched_workload["factor_base_enumerated_set_sha256"])
            config = dict(matched_workload["stage_config_hash_input"])
            pdp = dict(config["point_decomposition"])
            pdp["pair_links"] = (
                "pair0 external exact S3 roots; pair1 external exact roots "
                "plus symbolic factored S3 with XOR-to-CNF Tseitin chain")
            pdp["symbolic_pair1_activation"] = (
                "all n equations of S3(leaf2,leaf3,mid1)=0 are present "
                "before SAT decisions; exact external roots remain as a "
                "redundant model check and propagation rule")
            pdp["source_sha256"] = {
                "build_formula.py": sources["build_formula.py"],
                **dependencies,
            }
            pdp["solver_binary_sha256"] = compiler["binary_sha256"]
            config["point_decomposition"] = pdp
            full = digest(config)
            stage = (f"PS1N{n}Ckb1fb{matched_workload['factor_base_actual_B']}"
                     f"PDP4theoryh{full[:12]}")
            workloads[key] = {
                "matched_q1425_key": matched_key,
                "matched_q1425_stage_run_id": matched_workload[
                    "stage_run_id"],
                "matched_q1425_receipt_sha256": sha(matched_receipt_path),
                "parent_q1420_key": parent_key,
                "parent_q1420_stage_run_id": parent_workload["stage_run_id"],
                "parent_q1420_receipt_sha256": matched_workload[
                    "parent_receipt_sha256"],
                "curve_id": matched_workload["curve_id"],
                "factor_base_actual_B": matched_workload[
                    "factor_base_actual_B"],
                "folded_columns_K": matched_workload["folded_columns_K"],
                "factor_base_enumerated_set_sha256": matched_workload[
                    "factor_base_enumerated_set_sha256"],
                "public_target": matched_workload["public_target"],
                "input_law": matched_workload["input_law"],
                "target_preimage_x_count": matched_workload[
                    "target_preimage_x_count"],
                "target_input_sha256": target_hash,
                "removed_partner_pin_units": removed,
                "cnf_variables": variables,
                "cnf_clauses": clauses,
                "cnf_raw_sha256": hashlib.sha256(raw).hexdigest(),
                "cnf_raw_bytes": len(raw),
                "workload_record": matched_workload["workload_record"],
                "workload_id": matched_workload["workload_id"],
                "stage_config_hash_input": config,
                "stage_config_sha256_full": full,
                "stage_config_id": stage,
                "stage_run_id": f"{stage}W{matched_workload['workload_id']}R1",
            }
    return {
        "kind": "q1426_frozen_symbolic_second_pair_s3_protocol",
        "proposal_id": "Q1426", "candidate_id": None, "isogeny": "none",
        "question": (
            "Does a symbolic second-pair S3 link constrain both sparse "
            "partner leaves before Q1425's reverse-root enumeration, "
            "recovering an ordinary N53/N83 four-point relation?"),
        "workloads": workloads,
        "run_order": [f"n{n}_{cell}" for n in (53, 83)
                      for cell in ("free_partner", "ordinary")],
        "solver_conflict_cap": 1_000_000,
        "solver_wall_cap_seconds": 60,
        "external_process_safeguard_seconds": 75,
        "solver_binary_sha256": compiler["binary_sha256"],
        "compile_receipt_sha256": sha(compile_path),
        "sage_runtime_info_sha256": sha(runtime_path),
        "parent_q1420_protocol_sha256": sha(parent_path),
        "matched_q1425_protocol_sha256": sha(match_path),
        "source_sha256": sources,
        "dependency_sha256": dependencies,
        "claim_boundary": (
            "Known-witness free-partner cells are correctness controls. "
            "One ordinary target per degree is a solver gate, not natural "
            "relation yield. CPU wall times on this host are exploratory. "
            "Complete relation collection, useful rank, final matrix, "
            "descent, replay, and a degree-131 work projection remain "
            "unknown from this stage alone."),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    content = json.dumps(build(), sort_keys=True, indent=2) + "\n"
    if args.check:
        assert PROTOCOL.read_text() == content
    else:
        assert not PROTOCOL.exists()
        PROTOCOL.write_text(content)
    print(PROTOCOL)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Freeze Q1430 partial-trail observations before ordinary runs."""

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
Q1426 = PARENT / "q1426_symbolic_pair"
Q1427 = PARENT / "q1427_interleaved_pair"
Q1429 = PARENT / "q1429_unsaturated_span"
Q1423 = PARENT / "q1423_target_coupled"
LIFT = PARENT / "q1422_leaf_lift_gate"
PROTOCOL = HERE / "protocol.json"
SOURCE_NAMES = ("theory_solver.cpp", "build_binaries.py",
                "freeze_protocol.py", "run_stage.py", "verify_archive.py")
DEPENDENCIES = {
    "chain_s3.py": PARENT / "chain_s3.py",
    "chain_s3_factored.py": PARENT / "chain_s3_factored.py",
    "q1420_build_formula.py": Q1420 / "build_formula.py",
    "q1420_verify_archive.py": Q1420 / "verify_archive.py",
    "q1420_root_field.hpp": Q1420 / "root_field.hpp",
    "q1422_lift_gate.hpp": LIFT / "lift_gate.hpp",
    "q1423_target_inputs.py": Q1423 / "target_inputs.py",
    "q1425_relax_control.py": Q1425 / "relax_control.py",
    "q1426_build_formula.py": Q1426 / "build_formula.py",
    "q1428_screen.py": PARENT / "q1428_bilinear_span" / "screen.py",
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def digest(value) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"),
                     ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def build() -> dict:
    parent_path = Q1420 / "protocol.json"
    match_path = Q1427 / "protocol.json"
    parent = json.loads(parent_path.read_text())
    match = json.loads(match_path.read_text())
    compile_path = HERE / "compile_receipt.json"
    compiler = json.loads(compile_path.read_text())
    binary = HERE / "theory_solver"
    runtime_path = HERE / "sage_runtime_info.json"
    runtime = json.loads(runtime_path.read_text())
    assert runtime["status"] == "verified"
    assert compiler["binary_sha256"] == sha(binary)
    assert compiler["source_sha256"] == sha(
        HERE / "theory_solver.cpp")
    sources = {name: sha(HERE / name) for name in SOURCE_NAMES}
    dependencies = {name: sha(path) for name, path in DEPENDENCIES.items()}
    workloads = {}
    for n in (53, 83):
        for cell in ("free_partner", "ordinary"):
            key = f"n{n}_{cell}"
            matched_key = key
            matched_workload = match["workloads"][matched_key]
            matched_receipt_path = (Q1427 / "runs" / matched_key /
                                    "receipt.json")
            matched_receipt = json.loads(matched_receipt_path.read_text())
            assert matched_receipt["stage_run_id"] == matched_workload[
                "stage_run_id"]
            assert matched_receipt["solver_status"] in ("sat", "censored")
            parent_key = matched_workload["parent_q1420_key"]
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
            pdp["instrumentation"] = (
                "observation only: count states with second intermediate "
                "fixed, both second-pair leaves partial and weight-unsaturated; "
                "retain up to 256 distinct states and first 16 snapshots "
                "when each leaf has at most 14 free bits at N53 or 20 at "
                "N83 and one or two weight units remain")
            pdp["source_sha256"] = {
                "theory_solver.cpp": sources["theory_solver.cpp"],
                **dependencies,
            }
            pdp["solver_binary_sha256"] = compiler["binary_sha256"]
            config["point_decomposition"] = pdp
            full = digest(config)
            stage = (f"PS1N{n}Ckb1fb{matched_workload['factor_base_actual_B']}"
                     f"PDP4theoryh{full[:12]}")
            workloads[key] = {
                "matched_q1427_key": matched_key,
                "matched_q1427_stage_run_id": matched_workload[
                    "stage_run_id"],
                "matched_q1427_receipt_sha256": sha(matched_receipt_path),
                "parent_q1420_key": parent_key,
                "parent_q1420_stage_run_id": parent_workload["stage_run_id"],
                "parent_q1420_receipt_sha256": matched_workload[
                    "parent_q1420_receipt_sha256"],
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
        "kind": "q1430_frozen_partial_trail_observation_protocol",
        "proposal_id": "Q1430", "candidate_id": None, "isogeny": "none",
        "question": (
            "Does the actual Q1427 target-conditioned SAT trail reach "
            "weight-unsaturated partial second-pair states in the "
            "Q1429 span-screen window on ordinary N53/N83 queries?"),
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
        "matched_q1427_protocol_sha256": sha(match_path),
        "q1429_protocol_sha256": sha(Q1429 / "protocol.json"),
        "source_sha256": sources,
        "dependency_sha256": dependencies,
        "claim_boundary": (
            "Observation never adds clauses or changes decisions. The "
            "first 16 qualifying distinct states are samples, not an "
            "unbiased distribution. The 60-second ordinary searches are "
            "censored and CPU wall times exploratory. Reachability alone "
            "does not establish a useful filter, natural relation yield, "
            "or a degree-131 complete-work projection."),
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

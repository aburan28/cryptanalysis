#!/usr/bin/env python3
"""Freeze Q1431 guarded-span solver before ordinary runs."""

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
Q1430 = PARENT / "q1430_partial_trail"
Q1423 = PARENT / "q1423_target_coupled"
LIFT = PARENT / "q1422_leaf_lift_gate"
PROTOCOL = HERE / "protocol.json"
SOURCE_NAMES = ("theory_solver.cpp", "span_filter.hpp", "span_probe.cpp",
                "validate_span.py", "build_binaries.py",
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
    match_path = Q1430 / "protocol.json"
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
    assert compiler["span_header_sha256"] == sha(HERE / "span_filter.hpp")
    assert compiler["probe_source_sha256"] == sha(HERE / "span_probe.cpp")
    assert compiler["probe_binary_sha256"] == sha(HERE / "span_probe")
    validation_path = HERE / "span_validation.json"
    validation = json.loads(validation_path.read_text())
    assert validation["proposal_id"] == "Q1431"
    assert validation["total_cases"] == 112
    assert validation["total_verified_witness_false_rejections"] == 0
    assert validation["native_probe_sha256"] == compiler[
        "probe_binary_sha256"]
    assert validation["native_header_sha256"] == compiler[
        "span_header_sha256"]
    assert validation["source_sha256"] == sha(HERE / "validate_span.py")
    sources = {name: sha(HERE / name) for name in SOURCE_NAMES}
    dependencies = {name: sha(path) for name, path in DEPENDENCIES.items()}
    workloads = {}
    for n in (53, 83):
        for cell in ("free_partner", "ordinary"):
            key = f"n{n}_{cell}"
            matched_key = key
            matched_workload = match["workloads"][matched_key]
            matched_receipt_path = (Q1430 / "runs" / matched_key /
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
            pdp["partial_span_filter"] = (
                "for each distinct actual SAT state with second-pair "
                "intermediate fixed, both partner leaves partial, one or "
                "two Hamming-weight units left on each, and at most "
                "14/20 free coordinates per leaf at N53/N83: reject when "
                "S3 constant is outside the F2 span of all linear and "
                "bilinear free-coordinate coefficients; emit a clause "
                "guarded by every fixed bit of both leaves and all bits "
                "of the second intermediate")
            pdp["partial_span_cache_policy"] = (
                "memoize every checked tuple of intermediate, two fixed "
                "masks, and two fixed-one masks for the entire solve")
            pdp["source_sha256"] = {
                "theory_solver.cpp": sources["theory_solver.cpp"],
                "span_filter.hpp": sources["span_filter.hpp"],
                **dependencies,
            }
            pdp["solver_binary_sha256"] = compiler["binary_sha256"]
            config["point_decomposition"] = pdp
            full = digest(config)
            stage = (f"PS1N{n}Ckb1fb{matched_workload['factor_base_actual_B']}"
                     f"PDP4theoryh{full[:12]}")
            workloads[key] = {
                "matched_q1430_key": matched_key,
                "matched_q1430_stage_run_id": matched_workload[
                    "stage_run_id"],
                "matched_q1430_receipt_sha256": sha(matched_receipt_path),
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
        "kind": "q1431_frozen_guarded_partial_span_protocol",
        "proposal_id": "Q1431", "candidate_id": None, "isogeny": "none",
        "question": (
            "Does a sound guarded partial-pair span propagator reduce "
            "total charged work or recover an ordinary N53/N83 relation "
            "on Q1430's exact target-conditioned SAT workloads?"),
        "workloads": workloads,
        "run_order": [f"n{n}_{cell}" for n in (53, 83)
                      for cell in ("free_partner", "ordinary")],
        "solver_conflict_cap": 1_000_000,
        "solver_wall_cap_seconds": 60,
        "external_process_safeguard_seconds": 75,
        "solver_binary_sha256": compiler["binary_sha256"],
        "probe_binary_sha256": compiler["probe_binary_sha256"],
        "compile_receipt_sha256": sha(compile_path),
        "span_validation_sha256": sha(validation_path),
        "sage_runtime_info_sha256": sha(runtime_path),
        "parent_q1420_protocol_sha256": sha(parent_path),
        "matched_q1430_protocol_sha256": sha(match_path),
        "q1429_protocol_sha256": sha(Q1429 / "protocol.json"),
        "source_sha256": sources,
        "dependency_sha256": dependencies,
        "claim_boundary": (
            "The span test is a sound necessary condition, not a witness "
            "procedure. Count all filter field work and preserve failed "
            "or censored ordinary rows. CPU wall times here are exploratory. "
            "A stage improvement without verified ordinary relations and "
            "useful rank does not estimate natural relation yield or the "
            "complete degree-131 IC solve work."),
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

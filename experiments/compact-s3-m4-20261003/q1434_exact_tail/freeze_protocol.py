#!/usr/bin/env python3
"""Freeze Q1434 exact-tail solver before ordinary runs."""

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
Q1431 = PARENT / "q1431_guarded_span"
Q1432 = PARENT / "q1432_coefficient_cache"
Q1423 = PARENT / "q1423_target_coupled"
LIFT = PARENT / "q1422_leaf_lift_gate"
PROTOCOL = HERE / "protocol.json"
SOURCE_NAMES = ("theory_solver.cpp", "exact_tail.hpp", "tail_probe.cpp",
                "validate_tail.py", "build_binaries.py",
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
    "q1431_span_filter.hpp": Q1431 / "span_filter.hpp",
    "q1432_cached_span.hpp": Q1432 / "cached_span.hpp",
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def digest(value) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"),
                     ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def build() -> dict:
    parent_path = Q1420 / "protocol.json"
    match_path = Q1432 / "protocol.json"
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
    assert compiler["tail_header_sha256"] == sha(HERE / "exact_tail.hpp")
    assert compiler["cached_header_sha256"] == sha(Q1432 / "cached_span.hpp")
    assert compiler["parent_span_header_sha256"] == sha(
        Q1431 / "span_filter.hpp")
    assert compiler["probe_source_sha256"] == sha(HERE / "tail_probe.cpp")
    assert compiler["probe_binary_sha256"] == sha(HERE / "tail_probe")
    validation_path = HERE / "tail_validation.json"
    validation = json.loads(validation_path.read_text())
    assert validation["proposal_id"] == "Q1434"
    assert validation["total_cases"] == 60
    assert validation["total_witness_false_rejections"] == 0
    assert validation["native_probe_sha256"] == compiler[
        "probe_binary_sha256"]
    assert validation["native_header_sha256"] == compiler[
        "tail_header_sha256"]
    assert validation["cached_header_sha256"] == compiler[
        "cached_header_sha256"]
    assert validation["source_sha256"] == sha(HERE / "validate_tail.py")
    sources = {name: sha(HERE / name) for name in SOURCE_NAMES}
    dependencies = {name: sha(path) for name, path in DEPENDENCIES.items()}
    workloads = {}
    for n in (53, 83):
        for cell in ("free_partner", "ordinary"):
            key = f"n{n}_{cell}"
            matched_key = key
            matched_workload = match["workloads"][matched_key]
            matched_receipt_path = (Q1432 / "runs" / matched_key /
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
                "memoize every checked partial tuple; lazily build all "
                "pair-basis products and squares once, gamma columns for "
                "at most 64 exact intermediates, and coordinate-wise "
                "linear coefficients for at most 16384 exact pairs of "
                "intermediate and opposite fixed-one mask; if a table "
                "cap is reached compute uncached without changing the "
                "span result; charge construction and peak memory")
            pdp["partial_exact_tail"] = (
                "after cached span accepts a distinct partial second-pair "
                "state with exactly one weight unit left on each leaf, "
                "enumerate all zero-or-one-free-bit completions using the "
                "exact cached S3 bilinear expansion; if none satisfy S3, "
                "reject under all fixed leaf bits and the full second "
                "intermediate; if exactly one satisfies S3, force all "
                "remaining leaf bits under that same guard; retain "
                "multiple-completion states unchanged; count all field "
                "operations, candidate pairs, clauses and memory")
            pdp["source_sha256"] = {
                "theory_solver.cpp": sources["theory_solver.cpp"],
                "exact_tail.hpp": sources["exact_tail.hpp"],
                **dependencies,
            }
            pdp["solver_binary_sha256"] = compiler["binary_sha256"]
            config["point_decomposition"] = pdp
            full = digest(config)
            stage = (f"PS1N{n}Ckb1fb{matched_workload['factor_base_actual_B']}"
                     f"PDP4theoryh{full[:12]}")
            workloads[key] = {
                "matched_q1432_key": matched_key,
                "matched_q1432_stage_run_id": matched_workload[
                    "stage_run_id"],
                "matched_q1432_receipt_sha256": sha(matched_receipt_path),
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
        "kind": "q1434_frozen_exact_tail_protocol",
        "proposal_id": "Q1434", "candidate_id": None, "isogeny": "none",
        "question": (
            "Does exact weight-one tail membership and witness propagation "
            "improve the Q1432 search on matched ordinary N53/N83 targets, "
            "and what is its fully charged cost?"),
        "workloads": workloads,
        "run_order": [f"n{n}_{cell}" for n in (53, 83)
                      for cell in ("free_partner", "ordinary")],
        "solver_conflict_cap": 1_000_000,
        "solver_wall_cap_seconds": 60,
        "external_process_safeguard_seconds": 75,
        "solver_binary_sha256": compiler["binary_sha256"],
        "probe_binary_sha256": compiler["probe_binary_sha256"],
        "compile_receipt_sha256": sha(compile_path),
        "tail_validation_sha256": sha(validation_path),
        "sage_runtime_info_sha256": sha(runtime_path),
        "parent_q1420_protocol_sha256": sha(parent_path),
        "matched_q1432_protocol_sha256": sha(match_path),
        "q1429_protocol_sha256": sha(Q1429 / "protocol.json"),
        "source_sha256": sources,
        "dependency_sha256": dependencies,
        "claim_boundary": (
            "Exact tail clauses change Q1432's search only at sound, "
            "weight-one completion states. Direct Sage enumeration must "
            "validate membership and unique witnesses first. Count cache "
            "construction, span and tail field work, candidate pairs, "
            "payload bytes and peak RSS; preserve failures and timeouts. "
            "CPU wall times here are exploratory. A stage diagnostic "
            "without verified ordinary relations and useful rank does "
            "not estimate natural yield or complete degree-131 IC work."),
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

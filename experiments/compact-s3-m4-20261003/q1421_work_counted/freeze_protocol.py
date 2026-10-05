#!/usr/bin/env python3
"""Freeze Q1421 work-counted default/leaf-first root-theory comparisons."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "q1420_root_theory"
PROTOCOL = HERE / "protocol.json"
SOURCE_NAMES = ("build_binaries.py", "freeze_protocol.py", "run_stage.py",
                "theory_solver.cpp", "verify_archive.py")
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
    compiler_path = HERE / "compile_receipt.json"
    compiler = json.loads(compiler_path.read_text())
    runtime_path = HERE / "sage_runtime_info.json"
    runtime = json.loads(runtime_path.read_text())
    assert runtime["status"] == "verified"
    assert compiler["source_sha256"] == sha(HERE / "theory_solver.cpp")
    assert compiler["binary_sha256"] == sha(HERE / "theory_solver")
    assert compiler["root_field_header_sha256"] == sha(
        PARENT / "root_field.hpp")
    sources = {name: sha(HERE / name) for name in SOURCE_NAMES}
    dependencies = {name: sha(PARENT / name) for name in DEPENDENCY_NAMES}
    workloads = {}
    for n in (53, 83):
        for cell in ("free_mids", "ordinary"):
            parent_key = f"n{n}_{cell}"
            parent_workload = parent["workloads"][parent_key]
            parent_dir = PARENT / "runs" / parent_key
            parent_receipt_path = parent_dir / "receipt.json"
            parent_receipt = json.loads(parent_receipt_path.read_text())
            assert parent_receipt["protocol_sha256"] == sha(
                parent_protocol_path)
            assert parent_receipt["stage_run_id"] == parent_workload[
                "stage_run_id"]
            for policy in ("default", "leaf_first"):
                config = dict(parent_workload["stage_config_hash_input"])
                pdp = dict(config["point_decomposition"])
                pdp["decision_policy"] = (
                    "CaDiCaL default" if policy == "default" else
                    "external cb_decide chooses first unassigned leaf bit positive")
                pdp["termination_policy"] = (
                    "CaDiCaL synchronous 60-second terminator plus "
                    "one-million-conflict cap; 75-second process safeguard")
                pdp["source_sha256"] = {
                    "parent_build_formula.py": dependencies["build_formula.py"],
                    "parent_root_field.hpp": dependencies["root_field.hpp"],
                    "theory_solver.cpp": sources["theory_solver.cpp"],
                }
                pdp["solver_binary_sha256"] = compiler["binary_sha256"]
                config["point_decomposition"] = pdp
                full = digest(config)
                stage = (f"PS1N{n}Ckb1fb{parent_workload['factor_base_actual_B']}"
                         f"PDP4theoryh{full[:12]}")
                key = f"{parent_key}_{policy}"
                workloads[key] = {
                    "parent_key": parent_key,
                    "parent_stage_run_id": parent_workload["stage_run_id"],
                    "parent_receipt_sha256": sha(parent_receipt_path),
                    "parent_meta_sha256": sha(parent_dir / "meta.json"),
                    "parent_cnf_archive_sha256": sha(
                        parent_dir / "system.cnf.gz"),
                    "parent_variable_map_sha256": sha(
                        parent_dir / "variables.txt"),
                    "curve_id": parent_workload["curve_id"],
                    "factor_base_actual_B": parent_workload[
                        "factor_base_actual_B"],
                    "folded_columns_K": parent_workload["folded_columns_K"],
                    "factor_base_enumerated_set_sha256": parent_workload[
                        "factor_base_enumerated_set_sha256"],
                    "public_target": parent_workload["public_target"],
                    "decision_policy": policy,
                    "input_law": parent_receipt["input_law"],
                    "workload_record": parent_workload["workload_record"],
                    "workload_id": parent_workload["workload_id"],
                    "stage_config_hash_input": config,
                    "stage_config_sha256_full": full,
                    "stage_config_id": stage,
                    "stage_run_id": (f"{stage}W{parent_workload['workload_id']}R1"),
                }
    return {
        "kind": "q1421_frozen_work_counted_root_theory_protocol",
        "proposal_id": "Q1421", "candidate_id": None, "isogeny": "none",
        "question": (
            "Does leaf-first branching make exact-root propagation useful "
            "on unpinned ordinary N53/N83 four-point queries, and what "
            "work is spent before each cap?"),
        "parent_q1420_protocol_sha256": sha(parent_protocol_path),
        "workloads": workloads,
        "run_order": [f"n{n}_{cell}_{policy}" for n in (53, 83)
                      for cell in ("free_mids", "ordinary")
                      for policy in ("default", "leaf_first")],
        "solver_conflict_cap": 1_000_000,
        "solver_wall_cap_seconds": 60,
        "external_process_safeguard_seconds": 75,
        "solver_binary_sha256": compiler["binary_sha256"],
        "compile_receipt_sha256": sha(compiler_path),
        "sage_runtime_info_sha256": sha(runtime_path),
        "source_sha256": sources,
        "dependency_sha256": dependencies,
        "claim_boundary": (
            "Controls validate correctness only. One ordinary point per "
            "degree is a solver gate, not a natural-yield estimate. Solver "
            "process wall time is an exploratory stage diagnostic on an "
            "unisolated host. The archived target-dependent Q1420 formula "
            "build must be charged separately in a complete query. No "
            "complete degree-131 solve exponent follows from these cells."),
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

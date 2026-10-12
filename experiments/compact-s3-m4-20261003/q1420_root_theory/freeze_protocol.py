#!/usr/bin/env python3
"""Freeze the Q1420 external-root m4 stage before solver measurements."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from build_formula import CONTROL_PROTOCOL, ORDINARY_PARENT, HERE, PARENT, ROOT
from run_probe import sha

OUT = HERE / "protocol.json"
SOURCE_NAMES = (
    "build_binaries.py", "build_formula.py", "export_field.py",
    "probe_cadical.cpp", "root_field.hpp", "root_field_cli.cpp",
    "run_stage.py", "theory_solver.cpp", "validate_root_field.py",
    "verify_archive.py",
)
DEPENDENCIES = (
    "ecc2k130/codegen/field.py",
    "ecc2k130/codegen/curves.py",
    "experiments/koblitz-pair-claw-20260929/orbit_key.py",
    "experiments/compact-s3-m4-20261003/chain_s3.py",
    "experiments/compact-s3-m4-20261003/chain_s3_factored.py",
    "experiments/compact-s3-m4-20261003/chain_s3_multitarget.py",
    "experiments/compact-s3-m4-20261003/q1419_partial_pin/run_cell.py",
    "experiments/compact-s3-m4-20261003/run_probe.py",
    "experiments/compact-s3-m4-20261003/s3_root_oracle.py",
)


def canonical_digest(value):
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def workload(n, cell, profile, source, fixture, source_hashes, binary_sha):
    parent = json.loads(source.read_text())
    assert parent["curve_id"] == profile["curve_id"]
    assert parent["factor_base_actual_B"] == profile[
        "factor_base_actual_B"]
    assert parent["factor_base_folded_columns"] == profile[
        "folded_columns_K"]
    assert parent["factor_base_enumerated_set_sha256"] == profile[
        "factor_base_enumerated_set_sha256"]
    pinning = {
        "full_lock": "all four leaf x values, both pair roots, target selector",
        "free_mids": "all four leaf x values and target selector",
        "ordinary": "none",
    }[cell]
    law = ("archived known-satisfiable witness control" if fixture else
           "one archived ordinary public target with no witness pins")
    workload_record = {
        "curve_id": profile["curve_id"],
        "subgroup_order_r": profile["subgroup_order_r"],
        "target_point": [str(value) for value in parent["public_target"]],
        "input_law": law,
        "known_fixture_sha256": sha(fixture) if fixture else None,
        "source_parent_receipt_sha256": sha(source),
        "target_generation_seed": None,
        "target_count": 1, "cold_target_count": 0,
        "warm_target_count": 1,
    }
    workload_id = canonical_digest(workload_record)[:12]
    config = {
        "field": profile["field"],
        "curve": profile["curve"],
        "isogeny": "none",
        "factor_base": profile["factor_base"],
        "point_decomposition": {
            "m": 4, "stage_code": "PDP4theory",
            "summation_tree": "balanced pair-pair S3",
            "leaf_encoding": "normal-basis x Hamming weight bound",
            "pair_links": "external exact S3 roots and guarded CNF clauses",
            "final_link": "factored S3 with XOR-to-CNF Tseitin chain",
            "solver": "CaDiCaL 3 external clause propagator",
            "decision_policy": "CaDiCaL default",
            "pair_guard_policy": "weight-maximal positive support or full cube",
            "root_branch_policy": "first differing intermediate bit",
            "cache_policy": "memoize every observed ordered pair assignment",
            "pinning_policy": pinning,
            "source_sha256": {
                key: source_hashes[key] for key in
                ("build_formula.py", "root_field.hpp", "theory_solver.cpp")},
            "solver_binary_sha256": binary_sha,
        },
    }
    digest = canonical_digest(config)
    stage_id = (f"PS1N{n}Ckb1fb{profile['factor_base_actual_B']}"
                f"PDP4theoryh{digest[:12]}")
    return {
        "curve_id": profile["curve_id"],
        "factor_base_actual_B": profile["factor_base_actual_B"],
        "folded_columns_K": profile["folded_columns_K"],
        "factor_base_enumerated_set_sha256": profile[
            "factor_base_enumerated_set_sha256"],
        "field_bridge_export_sha256": sha(HERE / f"n{n}_field.txt"),
        "field_bridge_manifest_sha256": sha(
            PARENT / "field_bridges" / f"n{n}_onb_poly.json"),
        "parent_receipt_sha256": sha(source),
        "fixture_receipt_sha256": sha(fixture) if fixture else None,
        "public_target": parent["public_target"],
        "workload_record": workload_record,
        "workload_id": workload_id,
        "stage_config_hash_input": config,
        "stage_config_sha256_full": digest,
        "stage_config_id": stage_id,
        "stage_run_id": f"{stage_id}W{workload_id}R1",
    }


def build():
    q1419 = json.loads(CONTROL_PROTOCOL.read_text())
    compiler = json.loads((HERE / "compile_receipt.json").read_text())
    runtime = json.loads((HERE / "sage_runtime_info.json").read_text())
    assert runtime["status"] == "verified"
    validations = {str(n): json.loads((HERE / f"n{n}_root_validation.json")
                                       .read_text()) for n in (53, 83)}
    assert all(row["status"] == "PASS" and row["sampled_pairs"] == 64
               for row in validations.values())
    source_hashes = {name: sha(HERE / name) for name in SOURCE_NAMES}
    assert compiler["binary_sha256"]["theory_solver"] == sha(
        HERE / "theory_solver")
    assert compiler["source_sha256"]["theory_solver.cpp"] == source_hashes[
        "theory_solver.cpp"]
    assert compiler["source_sha256"]["root_field.hpp"] == source_hashes[
        "root_field.hpp"]
    workloads = {}
    for n in (53, 83):
        profile = q1419["profiles"][str(n)]
        fixture = ROOT / profile["fixture_receipt"]["path"]
        control = ROOT / profile["parent_receipt"]["path"]
        for cell in ("full_lock", "free_mids", "ordinary"):
            source = ORDINARY_PARENT[n] if cell == "ordinary" else control
            workloads[f"n{n}_{cell}"] = workload(
                n, cell, profile, source,
                fixture if cell != "ordinary" else None,
                source_hashes, sha(HERE / "theory_solver"))
    return {
        "kind": "q1420_frozen_external_s3_root_theory_stage_protocol",
        "proposal_id": "Q1420", "candidate_id": None,
        "isogeny": "none",
        "question": (
            "Can an external exact S3 root propagator avoid both Boolean "
            "root circuits and a K²n pair index while recovering ordinary "
            "four-point relations on exact N53/N83 bases?"),
        "workloads": workloads,
        "run_order": [f"n{n}_{cell}" for n in (53, 83)
                      for cell in ("full_lock", "free_mids", "ordinary")],
        "solver_wall_cap_seconds": 60,
        "solver_conflict_cap": 1000000,
        "solver_binary_sha256": sha(HERE / "theory_solver"),
        "cadical_header_sha256": compiler["cadical_header_sha256"],
        "cadical_library_sha256": compiler["cadical_library_sha256"],
        "compile_receipt_sha256": sha(HERE / "compile_receipt.json"),
        "sage_runtime_info_sha256": sha(HERE / "sage_runtime_info.json"),
        "root_validation_sha256": {str(n): sha(
            HERE / f"n{n}_root_validation.json") for n in (53, 83)},
        "source_sha256": source_hashes,
        "dependency_sha256": {name: sha(ROOT / name)
                              for name in DEPENDENCIES},
        "q1419_protocol_sha256": sha(CONTROL_PROTOCOL),
        "freeze_source_sha256": sha(Path(__file__)),
        "claim_boundary": (
            "One ordinary target per degree is a solver gate, not a natural "
            "yield estimate. Planted controls only validate correctness. "
            "CPU wall times are exploratory without isolation. No complete "
            "IC candidate, rank/yield rate, degree-131 solve exponent or "
            "speedup follows from this stage alone."),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    content = json.dumps(build(), indent=2, sort_keys=True) + "\n"
    if args.check:
        assert OUT.read_text() == content
    else:
        assert not OUT.exists()
        OUT.write_text(content)
    print(OUT)


if __name__ == "__main__":
    main()

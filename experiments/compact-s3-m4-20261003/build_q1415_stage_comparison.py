#!/usr/bin/env python3
"""Name the matched Q1410/Q1415 N53 solver-only method gate."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from run_probe import HERE, sha
from run_q1415_gauss_n53 import identity_hash

OUT = HERE / "runs/n53_q1410_q1415_named_stage_comparison.json"

SOURCE_COMPONENTS = {
    "field": "ecc2k130/codegen/field.py",
    "curves": "ecc2k130/codegen/curves.py",
    "s3_encoder": "experiments/compact-s3-m4-20261003/chain_s3.py",
    "factored_link": "experiments/compact-s3-m4-20261003/chain_s3_factored.py",
    "target_selector": "experiments/compact-s3-m4-20261003/chain_s3_multitarget.py",
    "balanced_tree": "experiments/compact-s3-m4-20261003/chain_s3_balanced_multitarget.py",
    "cofactor_preimages": "experiments/compact-s3-m4-20261003/cofactor_preimages.py",
}

RUN_ONLY_KEYS = {
    "max_conflicts", "max_models", "limits_seconds",
    "external_wall_cap_seconds", "kernel_seed", "formula_raw_sha256",
    "workload_id", "run_id", "candidate_id", "target_seed",
}


def check_hash_input(value):
    if isinstance(value, dict):
        for key, nested in value.items():
            assert key not in RUN_ONLY_KEYS and "/" not in key
            check_hash_input(nested)
    elif isinstance(value, list):
        for nested in value:
            check_hash_input(nested)
    else:
        assert not isinstance(value, float)


def canonical_stage(protocol: dict, solver_binary_sha256: str,
                    solver_algorithm_flags: list[str]) -> dict:
    """Hash algorithm identity without target formula, seeds, or run limits."""
    pdp = protocol["point_decomposition"]
    assert pdp["m"] == 4 and pdp["stage_code"] == "PDP4sat"
    assert all(path in protocol["source_sha256"]
               for path in SOURCE_COMPONENTS.values())
    identity = {
        "field": protocol["field"],
        "curve": protocol["curve"],
        "isogeny": "none",
        "factor_base": protocol["factor_base"],
        "point_decomposition": {
            "m": pdp["m"],
            "stage_code": pdp["stage_code"],
            "factor_base_verification": pdp["factor_base_verification"],
            "leaf_rule": pdp["leaf_rule"],
            "summation_tree": pdp["summation_tree"],
            "solver_family": "cryptominisat5 native XOR",
            "solver_algorithm_flags": solver_algorithm_flags,
            "solver_binary_sha256": solver_binary_sha256,
            "source_component_sha256": {
                name: protocol["source_sha256"][path]
                for name, path in SOURCE_COMPONENTS.items()
            },
        },
    }
    check_hash_input(identity)
    digest = identity_hash(identity)
    return {
        "stage_config_id": (
            f"PS1N53Ckb1fb{protocol['factor_base_actual_B']}PDP4sath{digest[:12]}"),
        "stage_config_sha256_full": digest,
        "stage_config_hash_input": identity,
    }


def build():
    parent_path = HERE / "runs/n53_q1410_ordinary.json"
    prior_path = HERE / "runs/n53_q1410_n83_q1408_balanced_stage_comparison.json"
    q1415_path = HERE / "runs/n53_q1415_gauss_ordinary.json"
    q1415_protocol_path = HERE / "q1415_gauss_n53_protocol.json"
    parent = json.loads(parent_path.read_text())
    prior = json.loads(prior_path.read_text())["stage_profiles"][0]
    q1415 = json.loads(q1415_path.read_text())
    protocol = json.loads(q1415_protocol_path.read_text())
    assert parent["proposal_id"] == prior["proposal_id"] == "Q1410"
    assert q1415["proposal_id"] == protocol["proposal_id"] == "Q1415"
    assert q1415["candidate_id"] is q1415["run_id"] is None
    assert q1415["curve_id"] == parent["curve_id"] == prior["curve_id"]
    assert q1415["workload_id"] == parent["workload_id"] == prior["workload_id"]
    for name in ("factor_base_actual_B", "factor_base_folded_columns",
                 "factor_base_enumerated_set_sha256"):
        assert q1415[name] == parent[name] == protocol[name]
    assert q1415["formula_raw_sha256"] == parent["attempts"][0][
        "xcnf_sha256"]
    assert q1415["same_ordinary_target_and_formula_as_q1410"] is True
    assert q1415["protocol_sha256"] == sha(q1415_protocol_path)
    assert q1415["stage_config_sha256_full"] == identity_hash(
        q1415["stage_config_hash_input"])
    assert q1415["stage_config_id"] != prior["stage_config_id"]
    assert q1415["solver_status"] == "external_timeout"
    assert q1415["gaussian_matrix_reported_active"] is True
    assert q1415["observed_verified_relation_count"] == 0
    assert parent["solver_binary_sha256"] == q1415[
        "solver_binary_sha256"] == protocol["solver_binary_sha256"]
    parent_protocol = json.loads((HERE /
        "q1410_balanced_s3_n53_protocol.json").read_text())
    baseline_name = canonical_stage(parent_protocol,
        parent["solver_binary_sha256"], [])
    gaussian_name = canonical_stage(parent_protocol,
        q1415["solver_binary_sha256"],
        ["--maxmatrixcols", "10000", "--autodisablegauss", "0"])
    assert baseline_name["stage_config_id"] != gaussian_name["stage_config_id"]
    wid = q1415["workload_id"]
    return {
        "kind": "named_q1410_q1415_matched_n53_solver_stage_comparison",
        "curve_id": q1415["curve_id"],
        "workload_id": q1415["workload_id"],
        "factor_base_actual_B": q1415["factor_base_actual_B"],
        "factor_base_folded_columns": q1415[
            "factor_base_folded_columns"],
        "factor_base_enumerated_set_sha256": q1415[
            "factor_base_enumerated_set_sha256"],
        "controlled_variable": (
            "CryptoMiniSat default XOR matrix discard versus "
            "maxmatrixcols=10000 with autodisablegauss=0 on identical "
            "Q1410 ordinary XCNF"),
        "canonical_stage_identity_policy": (
            "Hash field, curve, exact base, formula method/source, solver "
            "binary and algorithmic XOR-Gauss flags. Keep target-specific "
            "formula digest, seed, conflict cap, model cap, external wall "
            "cap, thread count and verbosity in run records. Archived "
            "stage IDs that included limits remain as legacy aliases."),
        "stage_profiles": [
            {
                "proposal_id": "Q1410", "candidate_id": None,
                **baseline_name,
                "stage_run_id": f"{baseline_name['stage_config_id']}W{wid}R1",
                "legacy_stage_config_id": prior["stage_config_id"],
                "legacy_stage_run_id": prior["run_id"],
                "solver_status": parent["status"],
                "gaussian_matrix_reported_active": False,
                "solver_conflicts_reported": parent["attempts"][0][
                    "solver_conflicts_reported"],
                "charged_target_stage_wall_seconds_exploratory": parent[
                    "target_dependent_stage_wall_seconds"],
                "verified_relation_count": 0,
                "receipt_sha256": sha(parent_path),
            },
            {
                "proposal_id": "Q1415", "candidate_id": None,
                **gaussian_name,
                "stage_run_id": f"{gaussian_name['stage_config_id']}W{wid}R1",
                "legacy_stage_config_id": q1415["stage_config_id"],
                "legacy_stage_run_id": q1415["stage_run_id"],
                "solver_status": q1415["solver_status"],
                "gaussian_matrix_reported_active": True,
                "solver_conflicts_reported": q1415[
                    "solver_conflicts_reported"],
                "solver_only_wall_seconds_exploratory": q1415[
                    "solver_wall_seconds_exploratory"],
                "verified_relation_count": 0,
                "receipt_sha256": sha(q1415_path),
            },
        ],
        "timing_boundaries_differ": True,
        "is_complete_ic_comparison": False,
        "is_controlled_cpu_wall_speedup": False,
        "is_solve_growth_measurement": False,
        "is_natural_relation_yield_estimate": False,
        "complete_solve_work_log2": None,
        "q1415_protocol_sha256": sha(q1415_protocol_path),
        "prior_named_comparison_sha256": sha(
            HERE / "runs/n53_q1410_n83_q1408_balanced_stage_comparison.json"),
        "source_sha256": sha(Path(__file__)),
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
    print(json.dumps({"status": "PASS",
                      "stage_config_ids": [row["stage_config_id"]
                                           for row in build()["stage_profiles"]],
                      "complete_solve_work_log2": None}))


if __name__ == "__main__":
    main()

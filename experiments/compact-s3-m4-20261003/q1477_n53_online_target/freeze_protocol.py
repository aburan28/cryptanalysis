#!/usr/bin/env python3
"""Freeze exact Q1477 source, instance, and one-target workload custody."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
ROOT = HERE.parents[2]
OUT = HERE / "protocol.json"
Q1467 = PARENT / "q1467_density_bridge/n53_w3_26_orbits.json"
Q1473 = PARENT / "q1473_n53_rank_collection/audit_result.json"
SOURCES = (
    "experiments/compact-s3-m4-20261003/protocol.json",
    "experiments/compact-s3-m4-20261003/q1420_root_theory/n53_field.txt",
    "experiments/compact-s3-m4-20261003/q1420_root_theory/root_field.hpp",
    "experiments/compact-s3-m4-20261003/q1468_n53_pair_oracle/pair_oracle.cpp",
    "experiments/compact-s3-m4-20261003/q1468_n53_pair_oracle/inputs/base_points.txt",
    "experiments/compact-s3-m4-20261003/q1467_density_bridge/n53_w3_26_orbits.json",
    "experiments/compact-s3-m4-20261003/q1473_n53_rank_collection/audit_result.json",
    "experiments/compact-s3-m4-20261003/q1477_n53_online_target/design_protocol.json",
    "experiments/compact-s3-m4-20261003/q1477_n53_online_target/make_inputs.py",
    "experiments/compact-s3-m4-20261003/q1477_n53_online_target/validate_inputs.py",
    "experiments/compact-s3-m4-20261003/q1477_n53_online_target/online_oracle.cpp",
    "experiments/compact-s3-m4-20261003/q1477_n53_online_target/build.py",
    "experiments/compact-s3-m4-20261003/q1477_n53_online_target/run_stage.py",
    "experiments/compact-s3-m4-20261003/q1477_n53_online_target/audit.py",
    "experiments/compact-s3-m4-20261003/q1477_n53_online_target/freeze_protocol.py",
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical(value: dict) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode()


def render() -> dict:
    design = json.loads((HERE / "design_protocol.json").read_text())
    manifest = json.loads((HERE / "input_manifest.json").read_text())
    fixture = json.loads((HERE / "audit_fixture.json").read_text())
    validation = json.loads((HERE / "input_validation.json").read_text())
    compile_receipt = json.loads((HERE / "compile_receipt.json").read_text())
    q1467 = json.loads(Q1467.read_text())
    q1473 = json.loads(Q1473.read_text())
    parent = json.loads((PARENT / "protocol.json").read_text())
    profile = next(row for row in parent["profiles"] if row["curve"][
        "curve_id"] == design["exact_instance"]["curve_id"])
    assert design["proposal_id"] == manifest["proposal_id"] == "Q1477"
    assert validation["status"] == "passed"
    assert validation["base_point_log_replays"] == 2756
    assert validation["input_manifest_sha256"] == sha(HERE /
                                                        "input_manifest.json")
    assert compile_receipt["binary_sha256"] == sha(HERE / "online_oracle")
    assert q1473["status"] == "passed" and q1473["combined_rank"] == 26
    assert q1467["actual_usable_points_B_before_folding"] == 2756
    assert q1467["selected_projected_columns_K"] == 26
    assert q1467["selected_projected_orbit_keys_digest_sha256"] == \
        design["exact_instance"]["factor_base_enumerated_set_sha256"]
    assert fixture["workload_id"] == manifest["workload_id"]
    assert manifest["base_logs_sha256"] == sha(HERE / "base_logs.txt")
    assert manifest["target_file_sha256"] == sha(HERE / "target.txt")
    assert manifest["audit_fixture_sha256"] == sha(HERE / "audit_fixture.json")
    assert validation["runtime_info_sha256"] == sha(HERE /
                                                       "sage_runtime_info.json")
    source_hashes = {relative: sha(ROOT / relative) for relative in SOURCES}
    stage_record = {
        "field": profile["field"], "curve": profile["curve"],
        "factor_base": {
            "construction": q1467["selection_rule"],
            "normal_basis_weight_bound": 3,
            "cofactor_projection": q1467["cofactor"],
            "selected_projected_orbit_keys_onb_hex": q1467[
                "selected_projected_orbit_keys_onb_hex"],
            "enumerated_set_sha256": q1467[
                "selected_projected_orbit_keys_digest_sha256"],
            "actual_usable_points_B_before_folding": 2756,
            "signed_frobenius_columns": 26,
            "base_points_sha256": sha(PARENT /
                                      "q1468_n53_pair_oracle/inputs/base_points.txt"),
        },
        "point_decomposition": {
            "m": 4, "solver_family": "mitm",
            "method": "complete cross-column pair-sum table and target complement lookup",
            "table_entries": 3651700,
            "sign_frobenius_quotient": "four distinct folded columns checked after pair lookup",
            "cache_policy": "one prebuilt table reused within one online target and all its shifts",
            "query_wall_cap_seconds": 30,
            "native_source_sha256": sha(HERE / "online_oracle.cpp"),
            "arithmetic_source_sha256": sha(PARENT /
                "q1468_n53_pair_oracle/pair_oracle.cpp"),
            "native_binary_sha256": sha(HERE / "online_oracle"),
        },
        "isogeny": "none",
    }
    stage_digest = hashlib.sha256(canonical(stage_record)).hexdigest()[:12]
    stage_id = f"PS1N53Ckb1fb2756PDP4mitmh{stage_digest}"
    workload_id = hashlib.sha256(canonical(
        fixture["workload_record"])).hexdigest()[:12]
    assert workload_id == fixture["workload_id"]
    return {
        "kind": "q1477_n53_one_target_online_protocol",
        "proposal_id": "Q1477", "candidate_id": None, "run_id": None,
        "isogeny": "none", "curve_id": profile["curve"]["curve_id"],
        "stage_config_id": stage_id,
        "stage_run_id": f"{stage_id}W{workload_id}R1",
        "stage_record": stage_record,
        "workload_id": workload_id,
        "workload_record": fixture["workload_record"],
        "factor_base_actual_B": 2756, "folded_columns_K": 26,
        "factor_base_enumerated_set_sha256": q1467[
            "selected_projected_orbit_keys_digest_sha256"],
        "target_count": 1, "attempt_limit": 256,
        "target_shift_seed": design["workload"]["target_shift_seed"],
        "target_shift_rule": design["workload"]["target_shift_rule"],
        "per_query_wall_cap_seconds": 30,
        "online_wall_cap_seconds": 1200,
        "external_safeguard_seconds": 1260,
        "online_interval": design["online_interval"],
        "measurement_scope": design["claim_scope"],
        "source_sha256": source_hashes,
        "input_manifest_sha256": sha(HERE / "input_manifest.json"),
        "target_file_sha256": sha(HERE / "target.txt"),
        "base_logs_sha256": sha(HERE / "base_logs.txt"),
        "audit_fixture_sha256": sha(HERE / "audit_fixture.json"),
        "input_validation_sha256": sha(HERE / "input_validation.json"),
        "sage_runtime_info_sha256": sha(HERE / "sage_runtime_info.json"),
        "compile_receipt_sha256": sha(HERE / "compile_receipt.json"),
        "native_binary_sha256": sha(HERE / "online_oracle"),
        "q1473_recovered_logs_audit_sha256": sha(Q1473),
        "controlled_wall_speedup": None,
        "complete_n131_log2_work": None,
        "challenge_run_admitted": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--emit", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    assert args.emit != args.check
    result = render()
    if args.emit:
        assert not OUT.exists(), "refuse overwrite"
        OUT.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    else:
        assert result == json.loads(OUT.read_text())
    print(json.dumps({"status": "pass", "stage_config_id":
                      result["stage_config_id"], "workload_id":
                      result["workload_id"]}), flush=True)


if __name__ == "__main__":
    main()

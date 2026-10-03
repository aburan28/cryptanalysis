#!/usr/bin/env python3
"""Audit one source-bound n=83 holdout artifact after checked-Sage replay.

Use this on each downloaded Q1091 artifact. A missing full receipt remains
an incomplete job with unknown actual work and earns no coverage credit.
"""

import argparse
import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
TARGET = HERE / "n83_holdout_target_20261001.json"
SOURCE_NAMES = ("alt_main.cpp", "alt_core.hpp", "alt_pairs.cpp", "eccF83.h")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_text())


def audit(artifact_dir, plan_path, runtime_path,
          workflow_snapshot_path=None):
    plan = load(plan_path)
    target = load(TARGET)
    host_path = artifact_dir / "host.json"
    assert host_path.is_file(), "missing frozen-host preflight"
    host = load(host_path)
    start = host["query_start"]
    assert start in plan["query_starts"]
    assert host["plan_sha256"] == sha(plan_path)
    assert host["target_sha256"] == plan["holdout_target_sha256"] == sha(TARGET)
    assert host["candidate_manifest_sha256"] == plan[
        "candidate_manifest_sha256"] == sha(HERE / plan["candidate_manifest"])
    assert host["candidate_id"] == plan["candidate_id"]
    assert host["run_id"] == plan["run_id"] == (
        plan["candidate_id"] + "W" + plan["workload_id"] + "R1")
    assert host["workload_id"] == plan["workload_id"] == target["workload_id"]
    assert host["curve_id"] == plan["curve_id"] == target["curve_id"]
    assert host["isogeny"] == plan["isogeny"] == target["isogeny"] == "none"
    assert host["public_target"] == plan["public_target"] == target[
        "public_target"]
    assert host["factor_base_enumerated_set_sha256"] == plan[
        "factor_base_enumerated_set_sha256"]
    assert host["actual_usable_points_B_before_folding"] == plan[
        "actual_usable_points_B_before_folding"]
    assert host["signed_frobenius_columns"] == plan[
        "signed_frobenius_columns"]
    assert host["table_start"] == plan["table_start"]
    assert host["table_descriptors"] == plan["table_descriptors"]
    assert host["query_representatives"] == plan["query_representatives"]
    assert host["architecture"].lower() in ("x86_64", "amd64")
    assert host["workflow_sha256"]
    if "wave_proposal_id" in plan:
        assert host["wave_proposal_id"] == plan["wave_proposal_id"]
        if plan["wave_proposal_id"] in ("Q1091", "Q1092"):
            snapshot = (workflow_snapshot_path or artifact_dir.parent /
                        "workflow_snapshot.yml")
            assert snapshot.is_file(), "missing triggering workflow snapshot"
            assert host["workflow_sha256"] == sha(snapshot)

    control_path = artifact_dir / "control.json"
    full_path = artifact_dir / "full.json"
    def optional_json(path):
        if not path.is_file():
            return None
        try:
            return load(path)
        except (ValueError, UnicodeDecodeError):
            return None

    control = optional_json(control_path)
    full = optional_json(full_path)
    if control is None or full is None:
        control_verified = []
        control_sage_path = artifact_dir / "control_sage_verify.json"
        partial_full_verified = []
        full_sage_path = artifact_dir / "sage_verify.json"
        if isinstance(full, dict) and full.get("native_result", {}).get(
                "exact_hit_queries", 0):
            assert full["candidate_id"] == plan["candidate_id"]
            assert full["run_id"] == plan["run_id"]
            assert full["curve_id"] == plan["curve_id"]
            assert full["workload_id"] == plan["workload_id"]
            assert full["isogeny"] == "none"
            assert full["public_target"] == plan["public_target"]
            assert full["query_start"] == start
            assert full["factor_base"]["enumerated_set_sha256"] == plan[
                "factor_base_enumerated_set_sha256"]
            assert full_sage_path.is_file(), (
                "partial full-receipt hit also needs independent Sage replay")
            replay = load(full_sage_path)
            assert replay["receipt_sha256"] == sha(full_path)
            assert replay["sage_runtime_info_sha256"] == sha(runtime_path)
            assert replay["holdout_target_sha256"] == sha(TARGET)
            assert replay["candidate_id"] == plan["candidate_id"]
            assert replay["curve_id"] == plan["curve_id"]
            assert replay["workload_id"] == plan["workload_id"]
            assert replay["verified_relation_count"] == len(
                full["verified_public_target_relations"])
            assert replay["verified_relation_count"] == len(
                replay["verified_relations"])
            assert replay["natural_public_target_relation_verified"]
            partial_full_verified = replay["verified_relations"]
        if isinstance(control, dict) and control.get("native_result", {}).get(
                "exact_hit_queries", 0):
            assert control["candidate_id"] is None
            assert control["run_id"] is None
            assert control["curve_id"] == plan["curve_id"]
            assert control["workload_id"] == plan["workload_id"]
            assert control["public_target"] == plan["public_target"]
            assert control["query_start"] == start
            assert control["factor_base"]["enumerated_set_sha256"] == plan[
                "factor_base_enumerated_set_sha256"]
            assert control_sage_path.is_file(), (
                "partial control hit also needs independent Sage replay")
            replay = load(control_sage_path)
            assert replay["receipt_sha256"] == sha(control_path)
            assert replay["sage_runtime_info_sha256"] == sha(runtime_path)
            assert replay["holdout_target_sha256"] == sha(TARGET)
            assert replay["candidate_id"] is None
            assert replay["curve_id"] == plan["curve_id"]
            assert replay["workload_id"] == plan["workload_id"]
            assert replay["verified_relation_count"] == len(
                control["verified_public_target_relations"])
            assert replay["verified_relation_count"] == len(
                replay["verified_relations"])
            assert replay["natural_public_target_relation_verified"]
            control_verified = replay["verified_relations"]
        return {
            "kind": "n83_holdout_artifact_audit",
            "scope": "one terminal CI job; no coverage credit without a full receipt",
            "proposal_id": None,
            "raw_wave_proposal_id": plan.get("wave_proposal_id",
                                             plan["proposal_id"]),
            "candidate_id": plan["candidate_id"],
            "workload_id": plan["workload_id"],
            "run_id": plan["run_id"],
            "curve_id": plan["curve_id"],
            "isogeny": "none",
            "query_start": start,
            "query_end_exclusive": start + plan["query_representatives"],
            "terminal_status": (
                "incomplete_artifact_candidate_replay_hit"
                if partial_full_verified else
                "incomplete_artifact_control_verified_hit"
                if control_verified else "incomplete_artifact"),
            "control_receipt_present": control_path.is_file(),
            "full_receipt_present": full_path.is_file(),
            "control_receipt_json_valid": control is not None,
            "full_receipt_json_valid": full is not None,
            "reported_full_exact_hit_queries": (
                full.get("native_result", {}).get("exact_hit_queries")
                if isinstance(full, dict) else None),
            "full_receipt_sha256": sha(full_path) if full_path.is_file()
                else None,
            "coverage_credit": 0,
            "actual_field_api_calls": None,
            "verified_relations": None,
            "partial_full_sage_verified_relations": len(
                partial_full_verified),
            "partial_full_sage_verified_scalars": sorted({
                row["recovered_scalar"] for row in partial_full_verified}),
            "partial_full_sage_verify_sha256": (
                sha(full_sage_path) if partial_full_verified else None),
            "control_independently_verified_relations": len(control_verified),
            "control_verified_scalars": sorted({row["recovered_scalar"]
                                                for row in control_verified}),
            "control_sage_verify_sha256": (
                sha(control_sage_path) if control_verified else None),
            "host_sha256": sha(host_path),
            "workflow_snapshot_sha256": (
                sha(snapshot) if plan.get("wave_proposal_id") in
                ("Q1091", "Q1092")
                else None),
            "plan_sha256": sha(plan_path),
            "source_sha256": sha(Path(__file__)),
        }

    runtime = load(runtime_path)
    assert runtime["status"] == "verified"
    assert control["proposal_id"] == full["proposal_id"] == plan[
        "proposal_id"]
    assert control["candidate_id"] is None
    assert control["run_id"] is None
    assert full["candidate_id"] == plan["candidate_id"]
    assert full["run_id"] == plan["run_id"]
    assert control["workload_id"] == full["workload_id"] == plan[
        "workload_id"]
    assert control["curve_id"] == full["curve_id"] == plan["curve_id"]
    assert control["isogeny"] == full["isogeny"] == "none"
    assert control["public_target"] == full["public_target"] == plan[
        "public_target"]
    assert control["factor_base"] == full["factor_base"]
    assert full["factor_base"]["enumerated_set_sha256"] == plan[
        "factor_base_enumerated_set_sha256"]
    assert full["factor_base"]["actual_usable_points_B_before_folding"] == (
        plan["actual_usable_points_B_before_folding"])
    assert full["factor_base"]["signed_frobenius_columns"] == plan[
        "signed_frobenius_columns"]
    assert control["query_start"] == full["query_start"] == start
    assert control["table_descriptors"] == 1 << 20
    assert control["query_representatives"] == 1 << 14
    assert full["query_representatives"] == plan["query_representatives"]
    assert full["table_descriptors"] == plan["table_descriptors"]
    assert full["table_start"] == plan["table_start"]
    assert full["cpu_backend"] == plan["cpu_backend"]
    assert full["query_workers"] == plan["workers"]
    assert full["representative_batch"] == plan["representative_batch"]
    assert full["bits_per_key"] == plan["bits_per_key"]
    assert full["hashes"] == plan["hashes"]
    assert full["wrapper_source_sha256"] == plan["runner_source_sha256"]
    assert full["native_source_sha256"] == plan[
        "zero_run_native_source_sha256"]
    assert full["bloom_core_sha256"] == plan[
        "zero_run_core_source_sha256"]
    assert full["native_pairs_sha256"] == plan[
        "zero_run_pairs_source_sha256"]
    assert full["generated_field_sha256"] == plan[
        "generated_field_sha256"]
    for stem, receipt in (("control", control), ("full", full)):
        binary_path = artifact_dir / (stem + "-bin")
        source_dir = artifact_dir / (stem + "-sources")
        assert binary_path.is_file()
        assert all((source_dir / name).is_file() for name in SOURCE_NAMES)
        assert receipt["compiled_binary_sha256"] == sha(binary_path)
        assert receipt["native_source_sha256"] == sha(
            source_dir / "alt_main.cpp")
        assert receipt["bloom_core_sha256"] == sha(
            source_dir / "alt_core.hpp")
        assert receipt["native_pairs_sha256"] == sha(
            source_dir / "alt_pairs.cpp")
        assert receipt["generated_field_sha256"] == sha(
            source_dir / "eccF83.h")
    assert control["compiled_binary_sha256"] == full[
        "compiled_binary_sha256"]
    control_native = control["native_result"]
    assert control_native["exact_hit_queries"] == len(control_native["hits"])
    assert control_native["bloom_positive_queries"] == (
        control_native["false_positive_queries"] +
        control_native["exact_hit_queries"])
    native = full["native_result"]
    assert native["query_start"] == start
    assert native["query_representatives"] == plan["query_representatives"]
    assert native["table_descriptors"] == plan["table_descriptors"]
    orbit_size, remainder = divmod(
        plan["actual_usable_points_B_before_folding"],
        plan["signed_frobenius_columns"])
    assert remainder == 0 and orbit_size == 166
    assert native["lifted_query_pairs"] == (
        plan["query_representatives"] * orbit_size)
    assert native["exact_hit_queries"] == len(native["hits"])
    assert native["bloom_positive_queries"] == (
        native["false_positive_queries"] + native["exact_hit_queries"])
    assert full["verified_public_target_quotient_table_dlp"] == bool(
        full["verified_public_target_relations"])
    assert control["verified_public_target_quotient_table_dlp"] == bool(
        control["verified_public_target_relations"])
    if native["exact_hit_queries"]:
        assert full["verified_public_target_relations"]
    if control_native["exact_hit_queries"]:
        assert control["verified_public_target_relations"]
    modeled = int(full["native_field_add_mul_sqr_call_model"])
    assert modeled == int(plan["modeled_native_field_calls_per_job"])
    assert math.isclose(math.log2(modeled), full[
        "native_field_add_mul_sqr_call_model_log2"])
    sage_path = artifact_dir / "sage_verify.json"
    assert sage_path.is_file(), "full receipt needs independent Sage replay"
    sage = load(sage_path)
    assert sage["receipt_sha256"] == sha(full_path)
    assert sage["sage_runtime_info_sha256"] == sha(runtime_path)
    assert sage["holdout_target_sha256"] == sha(TARGET)
    assert sage["candidate_id"] == plan["candidate_id"]
    assert sage["curve_id"] == plan["curve_id"]
    assert sage["workload_id"] == plan["workload_id"]
    assert sage["isogeny"] == "none"
    assert sage["verified_relation_count"] == len(
        full["verified_public_target_relations"])
    assert sage["verified_relation_count"] == len(sage["verified_relations"])
    assert sage["natural_public_target_relation_verified"] == bool(
        sage["verified_relation_count"])
    control_sage = None
    control_sage_path = artifact_dir / "control_sage_verify.json"
    if control_native["exact_hit_queries"]:
        assert control_sage_path.is_file(), (
            "control hit also needs independent Sage replay")
        control_sage = load(control_sage_path)
        assert control_sage["receipt_sha256"] == sha(control_path)
        assert control_sage["sage_runtime_info_sha256"] == sha(runtime_path)
        assert control_sage["holdout_target_sha256"] == sha(TARGET)
        assert control_sage["candidate_id"] is None
        assert control_sage["curve_id"] == plan["curve_id"]
        assert control_sage["workload_id"] == plan["workload_id"]
        assert control_sage["isogeny"] == "none"
        assert control_sage["verified_relation_count"] == len(
            control["verified_public_target_relations"])
        assert control_sage["verified_relation_count"] == len(
            control_sage["verified_relations"])
        assert control_sage["natural_public_target_relation_verified"]
    candidate_verified = sage["verified_relations"]
    control_verified = control_sage["verified_relations"] if control_sage else []
    return {
        "kind": "n83_holdout_artifact_audit",
        "scope": "one completed CI job, not a run-level measurement row",
        "proposal_id": None,
        "raw_wave_proposal_id": plan.get("wave_proposal_id",
                                         plan["proposal_id"]),
        "candidate_id": plan["candidate_id"],
        "workload_id": plan["workload_id"],
        "run_id": plan["run_id"],
        "curve_id": plan["curve_id"],
        "isogeny": "none",
        "factor_base_enumerated_set_sha256": plan[
            "factor_base_enumerated_set_sha256"],
        "actual_usable_points_B_before_folding": plan[
            "actual_usable_points_B_before_folding"],
        "signed_frobenius_columns": plan["signed_frobenius_columns"],
        "query_start": start,
        "query_end_exclusive": start + plan["query_representatives"],
        "terminal_status": ("completed_verified_hit" if candidate_verified else
                            "completed_control_verified_hit" if control_verified
                            else "completed_independently_verified_zero"),
        "coverage_credit": plan["query_representatives"],
        "exact_hit_queries": native["exact_hit_queries"],
        "control_exact_hit_queries": control_native["exact_hit_queries"],
        "independently_verified_relations": len(candidate_verified),
        "verified_scalars": sorted({row["recovered_scalar"]
                                    for row in candidate_verified}),
        "control_independently_verified_relations": len(control_verified),
        "control_verified_scalars": sorted({row["recovered_scalar"]
                                            for row in control_verified}),
        "lifted_query_pairs": native["lifted_query_pairs"],
        "bloom_positive_queries": native["bloom_positive_queries"],
        "false_positive_queries": native["false_positive_queries"],
        "native_regular_path_field_api_call_model": str(modeled),
        "control_regular_path_field_api_call_model": control[
            "native_field_add_mul_sqr_call_model"],
        "target_phase_seconds_on_this_host": full["target_online_seconds"],
        "wrapper_subprocess_wall_seconds": full[
            "wrapper_subprocess_wall_seconds"],
        "peak_rss_bytes": native["peak_rss_bytes"],
        "host_sha256": sha(host_path),
        "workflow_snapshot_sha256": (
            sha(snapshot) if plan.get("wave_proposal_id") in
            ("Q1091", "Q1092")
            else None),
        "control_sha256": sha(control_path),
        "full_sha256": sha(full_path),
        "sage_verify_sha256": sha(sage_path),
        "control_sage_verify_sha256": (
            sha(control_sage_path) if control_sage else None),
        "plan_sha256": sha(plan_path),
        "source_sha256": sha(Path(__file__)),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-dir", type=Path, required=True)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--runtime-info", type=Path, required=True)
    parser.add_argument("--workflow-snapshot", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    assert not args.out.exists(), "refusing to overwrite artifact audit"
    result = audit(args.artifact_dir, args.plan, args.runtime_info,
                   args.workflow_snapshot)
    args.out.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({key: result.get(key) for key in (
        "terminal_status", "query_start", "independently_verified_relations",
        "verified_scalars")}))


if __name__ == "__main__":
    main()

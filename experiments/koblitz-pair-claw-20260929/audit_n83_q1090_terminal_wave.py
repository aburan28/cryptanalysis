#!/usr/bin/env python3
"""Audit every terminal Q1090 holdout rectangle before extending the search."""

import hashlib
import json
import math
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
RAW = HERE / "runs" / "q1090_raw_ci_36891418377"
PLAN = HERE / "n83_q1090_holdout_m32_wave_plan.json"
TARGET = HERE / "n83_holdout_target_20261001.json"
OUTPUT = HERE / "n83_q1090_terminal_wave_audit.json"
RUN_ID = 36891418377


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    plan = json.loads(PLAN.read_text())
    target = json.loads(TARGET.read_text())
    workflow_path = RAW / "workflow_run.json"
    workflow = json.loads(workflow_path.read_text())
    artifact_inventory_path = RAW / "artifacts.json"
    artifact_inventory = json.loads(artifact_inventory_path.read_text())
    runtime_path = RAW / "sage_runtime_info.json"
    runtime = json.loads(runtime_path.read_text())
    assert runtime["status"] == "verified"
    assert workflow["url"].endswith(f"/runs/{RUN_ID}")
    assert workflow["status"] == "completed"
    assert workflow["conclusion"] == "success"
    assert workflow["headSha"] == (
        "2a4a069043498cc3507e0d767c11e244acc85d18")
    assert len(workflow["jobs"]) == len(plan["query_starts"]) == 16
    assert artifact_inventory["total_count"] == 16
    assert len(artifact_inventory["artifacts"]) == 16
    assert {item["name"] for item in artifact_inventory["artifacts"]} == {
        f"n83-q1090-holdout-M32-R29-start-{start}"
        for start in plan["query_starts"]}
    assert all(not item["expired"] for item in
               artifact_inventory["artifacts"])
    exemplar = RAW / "n83-q1090-holdout-M32-R29-start-0"
    exemplar_binary = exemplar / "full-bin"
    exemplar_source = exemplar / "full-sources"
    assert exemplar_binary.is_file()
    assert all((exemplar_source / name).is_file() for name in (
        "alt_main.cpp", "alt_core.hpp", "alt_pairs.cpp", "eccF83.h"))
    assert sha(exemplar / "control-bin") == sha(exemplar_binary)
    assert all(sha(exemplar / "control-sources" / name) ==
               sha(exemplar_source / name) for name in (
                   "alt_main.cpp", "alt_core.hpp", "alt_pairs.cpp",
                   "eccF83.h"))
    assert plan["holdout_target_sha256"] == sha(TARGET)
    assert plan["public_target"] == target["public_target"]
    assert plan["workload_id"] == target["workload_id"]
    assert plan["run_id"] == (
        plan["candidate_id"] + "W" + plan["workload_id"] + "R1")
    assert plan["runner_source_sha256"] == sha(
        HERE / "run_n83_holdout_chunk.py")
    assert plan["candidate_manifest_sha256"] == sha(
        HERE / plan["candidate_manifest"])
    assert plan["query_starts"] == [i * (1 << 29) for i in range(16)]

    jobs = {}
    for job in workflow["jobs"]:
        match = re.fullmatch(r"physical-x86-holdout-wave \((\d+)\)",
                             job["name"])
        assert match is not None
        start = int(match.group(1))
        assert start in plan["query_starts"] and start not in jobs
        assert job["status"] == "completed" and job["conclusion"] == "success"
        assert all(step["conclusion"] == "success" for step in job["steps"])
        jobs[start] = job
    assert set(jobs) == set(plan["query_starts"])

    rows = []
    total_field_calls = 0
    total_control_field_calls = 0
    total_native_target_phase_seconds = 0.0
    total_control_target_phase_seconds = 0.0
    total_wrapper_seconds = 0.0
    total_lifted_queries = 0
    total_control_lifted_queries = 0
    total_bloom_positives = 0
    total_false_positives = 0
    peak_rss = 0
    for start in sorted(jobs):
        directory = RAW / f"n83-q1090-holdout-M32-R29-start-{start}"
        assert directory.is_dir()
        host_path = directory / "host.json"
        control_path = directory / "control.json"
        full_path = directory / "full.json"
        sage_path = directory / "sage_verify.json"
        assert all(path.exists() for path in (
            host_path, control_path, full_path, sage_path))
        host = json.loads(host_path.read_text())
        control = json.loads(control_path.read_text())
        full = json.loads(full_path.read_text())
        sage = json.loads(sage_path.read_text())
        assert host["query_start"] == full["query_start"] == start
        assert host["plan_sha256"] == sha(PLAN)
        assert host["target_sha256"] == sha(TARGET)
        assert host["candidate_manifest_sha256"] == plan[
            "candidate_manifest_sha256"]
        assert host["candidate_id"] == full["candidate_id"] == plan[
            "candidate_id"]
        assert host["run_id"] == full["run_id"] == plan["run_id"]
        assert full["workload_id"] == plan["workload_id"]
        assert host["curve_id"] == full["curve_id"] == target["curve_id"]
        assert full["isogeny"] == host["isogeny"] == "none"
        assert control["public_target"] == full["public_target"] == target[
            "public_target"]
        assert control["table_descriptors"] == 1 << 20
        assert control["query_representatives"] == 1 << 14
        assert control["native_result"]["exact_hit_queries"] == 0
        assert control["verified_public_target_relations"] == []
        assert control["verified_public_target_quotient_table_dlp"] is False
        assert full["factor_base"]["enumerated_set_sha256"] == plan[
            "factor_base_enumerated_set_sha256"]
        assert full["factor_base"]["actual_usable_points_B_before_folding"] == (
            plan["actual_usable_points_B_before_folding"])
        assert full["factor_base"]["signed_frobenius_columns"] == plan[
            "signed_frobenius_columns"]
        assert full["table_descriptors"] == plan["table_descriptors"]
        assert full["query_representatives"] == plan[
            "query_representatives"]
        assert full["wrapper_source_sha256"] == plan[
            "runner_source_sha256"]
        assert full["native_source_sha256"] == plan[
            "zero_run_native_source_sha256"]
        assert full["bloom_core_sha256"] == plan[
            "zero_run_core_source_sha256"]
        assert full["native_pairs_sha256"] == plan[
            "zero_run_pairs_source_sha256"]
        assert control["compiled_binary_sha256"] == full[
            "compiled_binary_sha256"] == sha(exemplar_binary)
        assert full["native_source_sha256"] == sha(
            exemplar_source / "alt_main.cpp")
        assert full["bloom_core_sha256"] == sha(
            exemplar_source / "alt_core.hpp")
        assert full["native_pairs_sha256"] == sha(
            exemplar_source / "alt_pairs.cpp")
        assert full["generated_field_sha256"] == sha(
            exemplar_source / "eccF83.h")
        native = full["native_result"]
        assert native["exact_hit_queries"] == 0
        assert native["hits"] == []
        assert full["verified_public_target_relations"] == []
        assert full["verified_public_target_quotient_table_dlp"] is False
        assert sage["receipt_sha256"] == sha(full_path)
        assert sage["sage_runtime_info_sha256"] == sha(runtime_path)
        assert sage["holdout_target_sha256"] == sha(TARGET)
        assert sage["verified_relation_count"] == 0
        assert sage["natural_public_target_relation_verified"] is False
        assert native["lifted_query_pairs"] == plan[
            "query_representatives"] * 166
        assert native["bloom_positive_queries"] == native[
            "false_positive_queries"]
        modeled = int(full["native_field_add_mul_sqr_call_model"])
        assert modeled == int(plan["modeled_native_field_calls_per_job"])
        control_modeled = int(control[
            "native_field_add_mul_sqr_call_model"])
        total_field_calls += modeled
        total_control_field_calls += control_modeled
        total_native_target_phase_seconds += full["target_online_seconds"]
        total_control_target_phase_seconds += control["target_online_seconds"]
        total_wrapper_seconds += full["wrapper_subprocess_wall_seconds"]
        total_lifted_queries += native["lifted_query_pairs"]
        total_control_lifted_queries += control["native_result"][
            "lifted_query_pairs"]
        total_bloom_positives += native["bloom_positive_queries"]
        total_false_positives += native["false_positive_queries"]
        peak_rss = max(peak_rss, native["peak_rss_bytes"])
        rows.append({
            "query_start": start,
            "query_end_exclusive": start + plan["query_representatives"],
            "terminal_status": "completed_zero_exact_hits",
            "exact_hits": 0,
            "verified_relations": 0,
            "lifted_queries": native["lifted_query_pairs"],
            "bloom_positives": native["bloom_positive_queries"],
            "false_positives": native["false_positive_queries"],
            "native_regular_path_field_api_call_model": str(modeled),
            "control_regular_path_field_api_call_model": str(
                control_modeled),
            "target_phase_seconds_on_this_host": full[
                "target_online_seconds"],
            "wrapper_subprocess_wall_seconds": full[
                "wrapper_subprocess_wall_seconds"],
            "peak_rss_bytes": native["peak_rss_bytes"],
            "host_sha256": sha(host_path),
            "control_sha256": sha(control_path),
            "full_sha256": sha(full_path),
            "independent_sage_audit_sha256": sha(sage_path),
            "github_job_id": jobs[start]["databaseId"],
        })
    assert all(rows[i]["query_end_exclusive"] <= rows[i + 1][
        "query_start"] for i in range(len(rows) - 1))
    assert total_field_calls == 16 * int(plan[
        "modeled_native_field_calls_per_job"])
    assert math.isclose(math.log2(total_field_calls), plan[
        "modeled_native_field_calls_sixteen_jobs_log2"])
    assert total_bloom_positives == total_false_positives
    assert total_control_field_calls == 16 * int(rows[0][
        "control_regular_path_field_api_call_model"])
    report = {
        "kind": "n83_q1090_terminal_fresh_holdout_zero_yield_audit",
        "scope": "terminal wave segment of an open one-target run; not a run-level measurement row",
        "proposal_id": None,
        "raw_proposal_id": "Q1090",
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
        "completed_jobs": len(rows),
        "failed_jobs": 0,
        "exact_hit_queries": 0,
        "independently_verified_natural_relations": 0,
        "complete_discrete_logarithm": False,
        "first_query_representative": rows[0]["query_start"],
        "query_end_exclusive": rows[-1]["query_end_exclusive"],
        "total_query_representatives": 16 * plan[
            "query_representatives"],
        "total_lifted_query_pairs": total_lifted_queries,
        "total_control_lifted_query_pairs": total_control_lifted_queries,
        "total_bloom_positives": total_bloom_positives,
        "total_false_positives": total_false_positives,
        "native_regular_path_field_api_call_model": str(total_field_calls),
        "native_regular_path_field_api_call_model_log2": math.log2(
            total_field_calls),
        "control_regular_path_field_api_call_model": str(
            total_control_field_calls),
        "combined_full_and_control_field_api_call_model": str(
            total_field_calls + total_control_field_calls),
        "combined_full_and_control_field_api_call_model_log2": math.log2(
            total_field_calls + total_control_field_calls),
        "sum_target_phase_host_seconds_not_online_wall":
            total_native_target_phase_seconds,
        "sum_control_target_phase_host_seconds_not_online_wall":
            total_control_target_phase_seconds,
        "sum_wrapper_subprocess_host_seconds_not_online_wall":
            total_wrapper_seconds,
        "peak_single_job_rss_bytes": peak_rss,
        "one_target_online_wall_ms": None,
        "complete_calibrated_solve_operations": None,
        "paired_rho_online_wall_ms": None,
        "online_speedup": None,
        "plan_sha256": sha(PLAN),
        "target_sha256": sha(TARGET),
        "workflow_run_sha256": sha(workflow_path),
        "artifact_inventory_sha256": sha(artifact_inventory_path),
        "sage_runtime_info_sha256": sha(runtime_path),
        "deduplicated_source_binary_exemplar": {
            "directory": str(exemplar.relative_to(HERE)),
            "binary_sha256": sha(exemplar_binary),
            "native_source_sha256": sha(exemplar_source / "alt_main.cpp"),
            "bloom_core_sha256": sha(exemplar_source / "alt_core.hpp"),
            "native_pairs_sha256": sha(exemplar_source / "alt_pairs.cpp"),
            "generated_field_sha256": sha(exemplar_source / "eccF83.h"),
        },
        "source_sha256": sha(Path(__file__)),
        "rows": rows,
        "limits": [
            "Zero exact matches after sixteen completed disjoint rectangles; this is measured yield, not an estimate of a successful solve.",
            "The field API-call total is a regular-path shape model. Keying, Bloom, memory, disk, exceptional work, and Sage replay are outside that unit.",
            "Summed parallel host times are not one-target online wall time. No scalar was recovered in this wave.",
            "All 16 workers reported the same generated-source and binary hashes. The archive retains one byte-identical exemplar and all worker-specific JSON receipts; duplicate source and binary copies are omitted.",
        ],
    }
    assert not OUTPUT.exists(), "refusing to overwrite terminal audit"
    OUTPUT.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"completed_jobs": len(rows),
                      "verified_relations": 0,
                      "modeled_field_calls_log2": math.log2(total_field_calls),
                      "total_lifted_query_pairs": total_lifted_queries}))


if __name__ == "__main__":
    main()

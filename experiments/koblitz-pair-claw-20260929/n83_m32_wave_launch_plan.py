#!/usr/bin/env python3
"""Freeze a disjoint eight-job M32/R29 public-target search wave."""

import hashlib
import json
import math
from pathlib import Path

from n83_full_spill_screen import field_calls

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
OUTPUT = HERE / "n83_m32_wave_launch_plan.json"
R29 = 1 << 29
M32 = 1 << 32
STARTS = [range_index * (1 << 30) + segment * (1 << 27)
          for range_index in range(7, 11) for segment in (0, 4)]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    screen_path = HERE / "n83_full_spill_screen.json"
    ledger_path = HERE / "n83_full_spill_segment_work.json"
    prior_path = HERE / "n83_m32_group_launch_plan.json"
    workflow = REPO / ".github/workflows/n83-portable-quotient-m32-wave.yml"
    screen = json.loads(screen_path.read_text())
    ledger = json.loads(ledger_path.read_text())
    prior = json.loads(prior_path.read_text())
    assert screen["curve_id"] == ledger["curve_id"] == prior["curve_id"]
    assert ledger["verified_quotient_table_dlp_receipts"] == []
    assert ledger["unverified_exact_hit_receipts"] == []
    assert prior["proposal_id"] == "Q1068"
    assert prior["query_end_exclusive"] <= STARTS[0]
    assert all(a + R29 <= b for a, b in zip(STARTS, STARTS[1:]))
    assert STARTS[-1] + R29 <= 118 * (1 << 30)
    assert all(start % R29 == 0 for start in STARTS)
    assert ledger["completed_M32_extension_M28_by_R27_cells"] == 16
    subgroup_order = screen["curve_identity_record"]["curve"][
        "subgroup_order"]
    orbit_size = screen["factor_base"]["signed_frobenius_orbit_size"]
    intensity_per_job = M32 * R29 * orbit_size ** 2 / subgroup_order
    projected_calls = field_calls(M32, R29)
    paths = {
        "screen_sha256": screen_path,
        "coverage_ledger_sha256": ledger_path,
        "prior_M32_launch_plan_sha256": prior_path,
        "wave_plan_sha256": HERE / "n83_portable_wave_plan.json",
        "workflow_sha256": workflow,
        "portable_native_source_sha256":
            HERE / "native_n83_orbit_query_spill_portable.cpp",
        "portable_core_source_sha256":
            HERE / "native_n83_bloom_core_portable.hpp",
        "portable_pairs_source_sha256":
            HERE / "native_n83_pairs_portable.cpp",
        "portable_wrapper_source_sha256":
            HERE / "run_n83_portable_chunk.py",
        "generated_field_header_sha256":
            REPO / "ecc2k130/runner/generated/eccF83.h",
        "base_receipt_sha256":
            HERE / "runs/n83_knownlog_orbit_base_k48194.json",
    }
    report = {
        "kind": "n83_q1069_eight_job_M32_R29_one_shot_wave_plan",
        "proposal_id": "Q1069", "candidate_id": None, "run_id": None,
        "status": "ready_for_one_shot_dispatch",
        "curve_id": screen["curve_id"], "isogeny": "none",
        "factor_base_enumerated_set_sha256": screen["factor_base"][
            "enumerated_set_sha256"],
        "actual_usable_points_B_before_folding": screen["factor_base"][
            "actual_usable_points_B_before_folding"],
        "signed_frobenius_columns": screen["factor_base"][
            "signed_frobenius_columns"],
        "public_target": screen["public_target"],
        "target_count": 1,
        "table_start": 0, "table_descriptors": M32,
        "query_starts": STARTS, "query_representatives": R29,
        "query_end_exclusive": STARTS[-1] + R29,
        "prior_M32_query_end_exclusive": prior["query_end_exclusive"],
        "wave_query_end_max_exclusive": 6 * (1 << 30),
        "max_parallel_jobs": 8,
        "cpu_backend": "x86_pclmul", "query_workers": 4,
        "representative_batch": 8, "bits_per_key": 20, "hashes": 10,
        "minimum_mem_available_bytes": 13 << 30,
        "minimum_root_free_bytes": 10 << 30,
        "timeout_seconds_per_job": 21600,
        "modeled_native_field_calls_per_job": str(projected_calls),
        "modeled_native_field_calls_eight_jobs_log2":
            math.log2(8 * projected_calls),
        "relation_placement_heuristic_hit_probability_eight_jobs":
            -math.expm1(-8 * intensity_per_job),
        "complete_solve_work_log2": None,
        "limits": [
            "The hit probability is a frozen quotient-collision heuristic, not natural relation yield.",
            "In-flight Q1061 and Q1068 receipts are excluded until terminal and independently audited.",
            "Field calls omit hashing, Bloom, memory, disk, setup, failed work, and scalar replay.",
            "A native exact hit must pass independent checked-Sage witness replay before promotion to a DLP result.",
        ],
        **{key: sha(path) for key, path in paths.items()},
        "source_sha256": sha(Path(__file__)),
    }
    assert report["curve_id"] == "EC1N83Ckb1h876c2921cb64"
    assert report["actual_usable_points_B_before_folding"] == 8000204
    assert report["signed_frobenius_columns"] == 48194
    OUTPUT.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"query_starts": STARTS,
                      "modeled_field_calls_log2": report[
                          "modeled_native_field_calls_eight_jobs_log2"],
                      "heuristic_hit_probability": report[
                          "relation_placement_heuristic_hit_probability_eight_jobs"]}),
          flush=True)


if __name__ == "__main__":
    main()

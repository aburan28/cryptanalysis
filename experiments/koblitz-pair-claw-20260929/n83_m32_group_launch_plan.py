#!/usr/bin/env python3
"""Freeze one concurrent, disjoint Q1068 M32/R29 CI dispatch."""

import hashlib
import json
from pathlib import Path

from n83_full_spill_screen import field_calls
from n83_identity_contract import validate_reference

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
DESIGN = HERE / "n83_m32_group_followup_plan.json"
SCREEN = HERE / "n83_full_spill_screen.json"
WAVE = HERE / "n83_portable_wave_plan.json"
WORKFLOW = REPO / ".github/workflows/n83-portable-quotient-m32-group.yml"
NATIVE = HERE / "native_n83_orbit_query_spill_portable.cpp"
CORE = HERE / "native_n83_bloom_core_portable.hpp"
PAIRS = HERE / "native_n83_pairs_portable.cpp"
WRAPPER = HERE / "run_n83_portable_chunk.py"
GENERATED = REPO / "ecc2k130/runner/generated/eccF83.h"
BASE = HERE / "runs/n83_knownlog_orbit_base_k48194.json"
OUTPUT = HERE / "n83_m32_group_launch_plan.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    design = json.loads(DESIGN.read_text())
    screen = json.loads(SCREEN.read_text())
    wave = json.loads(WAVE.read_text())
    validate_reference(screen)
    assert design["proposal_id"] == "Q1068"
    assert design["candidate_id"] is None and design["run_id"] is None
    assert design["curve_id"] == screen["curve_id"] == wave["curve_id"]
    assert design["isogeny"] == screen["isogeny"] == "none"
    assert design["factor_base_enumerated_set_sha256"] == screen[
        "factor_base"]["enumerated_set_sha256"]
    assert design["actual_usable_points_B_before_folding"] == screen[
        "factor_base"]["actual_usable_points_B_before_folding"]
    assert design["signed_frobenius_columns"] == screen[
        "factor_base"]["signed_frobenius_columns"]
    assert design["query_start"] == 6710886400
    assert design["query_representatives"] == 1 << 29
    assert design["table_descriptors"] == 1 << 32
    assert design["prior_M32_query_end_exclusive"] == design["query_start"]
    assert design["wave_query_end_max_exclusive"] <= 6 * (1 << 30)
    assert design["modeled_native_field_calls"] == str(field_calls(
        1 << 32, 1 << 29))
    assert design["portable_native_source_sha256"] == sha(NATIVE)
    assert design["source_sha256"] == sha(
        HERE / "n83_m32_group_followup_plan.py")
    assert not OUTPUT.exists(), "refusing to overwrite a frozen launch plan"
    report = {
        "kind": "n83_q1068_one_shot_concurrent_M32_R29_launch_plan",
        "proposal_id": "Q1068", "candidate_id": None, "run_id": None,
        "status": "one_shot_concurrent_disjoint_dispatch",
        "curve_id": screen["curve_id"], "isogeny": "none",
        "factor_base_enumerated_set_sha256": screen[
            "factor_base"]["enumerated_set_sha256"],
        "actual_usable_points_B_before_folding": screen[
            "factor_base"]["actual_usable_points_B_before_folding"],
        "signed_frobenius_columns": screen["factor_base"][
            "signed_frobenius_columns"],
        "public_target": screen["public_target"], "target_count": 1,
        "table_start": 0, "table_descriptors": 1 << 32,
        "query_start": design["query_start"],
        "query_representatives": design["query_representatives"],
        "query_end_exclusive": design["query_end_exclusive"],
        "prior_M32_query_end_exclusive": design[
            "prior_M32_query_end_exclusive"],
        "wave_query_end_max_exclusive": design[
            "wave_query_end_max_exclusive"],
        "cpu_backend": "x86_pclmul", "query_workers": 4,
        "representative_batch": 8, "bits_per_key": 20, "hashes": 10,
        "minimum_mem_available_bytes": 13 << 30,
        "minimum_root_free_bytes": 10 << 30,
        "timeout_seconds": 6 * 3600,
        "modeled_native_field_calls": design["modeled_native_field_calls"],
        "modeled_native_field_calls_log2": design[
            "modeled_native_field_calls_log2"],
        "measured_prior_M32_R28_peak_rss_bytes": design[
            "measured_prior_M32_R28_peak_rss_bytes"],
        "projected_M32_R29_full_wall_seconds": design[
            "projected_M32_R29_full_wall_seconds"],
        "relation_placement_heuristic_hit_probability": design[
            "relation_placement_heuristic_hit_probability"],
        "dispatch_reason": "One disjoint R29 grouped call adds natural-relation coverage while the active M31 wave runs; its host preflight and bounded control must pass before the full query.",
        "stop_rule": "One terminal artifact only; inspect exact hits immediately and cancel this job if an earlier wave artifact has a verified hit before its full query starts.",
        "complete_solve_work_log2": None,
        "limits": [
            "No n83 relation is claimed by this launch plan.",
            "The 2.59 percent hit probability and 3.24-hour full-wall forecast are unverified projections.",
            "The native field-call model omits hashing, Bloom, memory, disk, setup, failed work, and independent scalar replay.",
            "A natural exact hit needs independent checked-Sage witness replay before promotion to a DLP result.",
        ],
        "design_plan_sha256": sha(DESIGN),
        "screen_sha256": sha(SCREEN),
        "wave_plan_sha256": sha(WAVE),
        "workflow_sha256": sha(WORKFLOW),
        "portable_native_source_sha256": sha(NATIVE),
        "portable_core_source_sha256": sha(CORE),
        "portable_pairs_source_sha256": sha(PAIRS),
        "portable_wrapper_source_sha256": sha(WRAPPER),
        "generated_field_header_sha256": sha(GENERATED),
        "base_receipt_sha256": sha(BASE),
        "source_sha256": sha(Path(__file__)),
    }
    OUTPUT.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"status": report["status"],
                      "query_start": report["query_start"],
                      "modeled_field_calls_log2": report[
                          "modeled_native_field_calls_log2"],
                      "workflow_sha256": report["workflow_sha256"]}))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Freeze the one-shot n=83 M32/R28 shape search before CI dispatch."""

import hashlib
import json
import math
from pathlib import Path

from n83_full_spill_screen import field_calls
from n83_identity_contract import validate_reference

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SCREEN = HERE / "n83_full_spill_screen.json"
WAVE = HERE / "n83_portable_wave_plan.json"
PREVIOUS = HERE / "runs/n83_portable_q1061_M31_R27_ci_36663733518"
WORKFLOW = REPO / ".github/workflows/n83-portable-quotient-shape.yml"
OUTPUT = HERE / "n83_m32_shape_plan.json"
M = 1 << 32
R = 1 << 28
QUERY_START = 6 << 30


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bloom_bytes(entries):
    return ((entries * 20 + 511) // 512 + 1024) * 64


def main():
    screen = json.loads(SCREEN.read_text())
    wave = json.loads(WAVE.read_text())
    previous_host = json.loads((PREVIOUS / "host.json").read_text())
    previous_full = json.loads((PREVIOUS / "full.json").read_text())
    validate_reference(screen)
    assert screen["curve_id"] == wave["curve_id"] == previous_full[
        "curve_id"]
    assert screen["factor_base"] == previous_full["factor_base"]
    assert QUERY_START >= max(wave["query_starts"]) + wave[
        "query_representatives_per_job"]
    assert QUERY_START + R <= 118 * (1 << 30)
    assert QUERY_START % (1 << 27) == 0
    assert previous_full["table_descriptors"] == 1 << 31
    assert previous_host["architecture"] == "x86_64"
    previous_native = previous_full["native_result"]
    assert previous_native["exact_hit_queries"] == 0
    assert previous_native["bloom_bytes"] == bloom_bytes(1 << 31)
    calls = field_calls(M, R)
    old_calls = field_calls(1 << 31, 1 << 29)
    intensity = (M * R *
                 screen["factor_base"]["signed_frobenius_orbit_size"] ** 2 /
                 screen["curve_identity_record"]["curve"]["subgroup_order"])
    report = {
        "kind": "n83_q1065_one_shot_physical_x86_M32_R28_plan",
        "proposal_id": "Q1065", "candidate_id": None, "run_id": None,
        "status": "activation_workflow_staged",
        "curve_id": screen["curve_id"], "isogeny": "none",
        "factor_base_enumerated_set_sha256": screen[
            "factor_base"]["enumerated_set_sha256"],
        "actual_usable_points_B_before_folding": screen[
            "factor_base"]["actual_usable_points_B_before_folding"],
        "signed_frobenius_columns": screen[
            "factor_base"]["signed_frobenius_columns"],
        "public_target": screen["public_target"],
        "table_start": 0, "table_descriptors": M,
        "query_start": QUERY_START, "query_representatives": R,
        "query_interval_end_exclusive": QUERY_START + R,
        "same_area_M31_R29_field_calls": str(old_calls),
        "modeled_native_field_calls": str(calls),
        "modeled_native_field_calls_log2": math.log2(calls),
        "modeled_M31_R29_to_M32_R28_field_call_ratio": old_calls / calls,
        "bloom_bytes": bloom_bytes(M),
        "previous_x86_M31_peak_rss_bytes": previous_native[
            "peak_rss_bytes"],
        "previous_x86_mem_available_bytes": previous_host[
            "mem_available_bytes"],
        "rss_forecast_by_bloom_delta_bytes": (
            previous_native["peak_rss_bytes"] +
            bloom_bytes(M) - previous_native["bloom_bytes"]),
        "relation_placement_heuristic_intensity": intensity,
        "relation_placement_heuristic_hit_probability": -math.expm1(-intensity),
        "measured_full_size_wall_seconds": None,
        "verified_natural_relation_count": None,
        "complete_solve_work_log2": None,
        "limits": [
            "The hit probability is the frozen quotient collision heuristic, not observed natural relation yield.",
            "The RSS forecast adds one measured Bloom-size delta to one earlier x86 peak; M32 feasibility remains unmeasured.",
            "Native field calls omit keying, Bloom, memory, I/O, setup, failed work, and independent Sage replay.",
        ],
        "screen_sha256": sha(SCREEN),
        "wave_plan_sha256": sha(WAVE),
        "previous_host_sha256": sha(PREVIOUS / "host.json"),
        "previous_full_sha256": sha(PREVIOUS / "full.json"),
        "workflow_sha256": sha(WORKFLOW),
        "source_sha256": sha(Path(__file__)),
    }
    OUTPUT.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({
        "status": report["status"],
        "query_start": QUERY_START,
        "modeled_native_field_calls_log2": report[
            "modeled_native_field_calls_log2"],
        "heuristic_hit_probability": report[
            "relation_placement_heuristic_hit_probability"],
        "rss_forecast_by_bloom_delta_bytes": report[
            "rss_forecast_by_bloom_delta_bytes"],
    }), flush=True)


if __name__ == "__main__":
    main()

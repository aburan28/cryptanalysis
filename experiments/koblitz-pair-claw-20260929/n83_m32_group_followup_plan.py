#!/usr/bin/env python3
"""Freeze a disjoint M32/R29 follow-up before any optional dispatch."""

import hashlib
import json
import math
from pathlib import Path

from n83_full_spill_screen import field_calls
from n83_identity_contract import validate_receipt, validate_reference

HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs"
SCREEN = HERE / "n83_full_spill_screen.json"
WAVE = HERE / "n83_portable_wave_plan.json"
LEDGER = HERE / "n83_full_spill_segment_work.json"
M32 = RUNS / "n83_portable_q1065_M32_R28_ci_36673555074"
OUTPUT = HERE / "n83_m32_group_followup_plan.json"
M = 1 << 32
R = 1 << 29
QUERY_START = 6 * (1 << 30) + (1 << 28)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    screen = json.loads(SCREEN.read_text())
    wave = json.loads(WAVE.read_text())
    ledger = json.loads(LEDGER.read_text())
    bundle = json.loads((M32 / "bundle.json").read_text())
    full = json.loads((M32 / "full.json").read_text())
    sage = json.loads((M32 / "sage_verify.json").read_text())
    validate_reference(screen)
    validate_receipt(screen, full)
    assert screen["curve_id"] == wave["curve_id"] == full["curve_id"]
    assert screen["factor_base"] == full["factor_base"]
    assert screen["isogeny"] == full["isogeny"] == "none"
    assert screen["candidate_id"] is None and full["candidate_id"] is None
    assert bundle["status"] == "completed_zero_hit"
    assert bundle["github_run_id"] == 36673555074
    assert bundle["artifact_sha256"]["full.json"] == sha(M32 / "full.json")
    assert full["table_descriptors"] == M
    assert full["query_start"] == 6 * (1 << 30)
    assert full["query_representatives"] == R // 2
    assert full["native_result"]["exact_hit_queries"] == 0
    assert not full["verified_public_target_quotient_table_dlp"]
    assert sage["receipt_sha256"] == sha(M32 / "full.json")
    assert sage["verified_relation_count"] == 0
    assert ledger["complete_solve_work_log2"] is None
    assert not ledger["verified_quotient_table_dlp_receipts"]
    assert not ledger["unverified_exact_hit_receipts"]
    assert any(row["path"].endswith(
        "n83_portable_q1065_M32_R28_ci_36673555074/full.json")
        for row in ledger["completed_receipts"])
    assert wave["proposal_id"] == "Q1061"
    assert len(wave["query_starts"]) == 8
    assert max(wave["query_starts"]) + wave[
        "query_representatives_per_job"] <= 6 * (1 << 30)
    assert QUERY_START == full["query_start"] + full[
        "query_representatives"]
    assert QUERY_START + R <= 7 * (1 << 30)
    assert QUERY_START % (1 << 27) == 0
    native = full["native_result"]
    calls = field_calls(M, R)
    separate_calls = 2 * field_calls(M, R // 2)
    intensity = (M * R * screen["factor_base"][
        "signed_frobenius_orbit_size"] ** 2 /
        screen["curve_identity_record"]["curve"]["subgroup_order"])
    # One table build and one exact table replay, with twice the measured
    # target-query span. This is a forecast, not a matched host measurement.
    wall_forecast = (native["build_seconds"] +
                     2 * native["query_seconds"] +
                     native["exact_replay_seconds"])
    report = {
        "kind": "n83_q1068_disjoint_M32_R29_group_followup_plan",
        "proposal_id": "Q1068", "candidate_id": None, "run_id": None,
        "status": "staged_pending_wave_terminal_review_no_dispatch",
        "curve_id": screen["curve_id"], "isogeny": "none",
        "factor_base_enumerated_set_sha256": screen["factor_base"][
            "enumerated_set_sha256"],
        "actual_usable_points_B_before_folding": screen["factor_base"][
            "actual_usable_points_B_before_folding"],
        "signed_frobenius_columns": screen["factor_base"][
            "signed_frobenius_columns"],
        "public_target": screen["public_target"], "target_count": 1,
        "table_start": 0, "table_descriptors": M,
        "query_start": QUERY_START, "query_representatives": R,
        "query_end_exclusive": QUERY_START + R,
        "prior_M32_query_end_exclusive": full["query_start"] + full[
            "query_representatives"],
        "wave_query_end_max_exclusive": max(wave["query_starts"]) + wave[
            "query_representatives_per_job"],
        "cpu_backend": "x86_pclmul", "query_workers": 4,
        "representative_batch": 8, "bits_per_key": 20, "hashes": 10,
        "minimum_mem_available_bytes": 13 << 30,
        "minimum_root_free_bytes": 10 << 30,
        "timeout_seconds": 6 * 3600,
        "modeled_native_field_calls": str(calls),
        "modeled_native_field_calls_log2": math.log2(calls),
        "two_separate_R28_calls": str(separate_calls),
        "grouped_to_two_separate_field_call_ratio": calls / separate_calls,
        "relation_placement_heuristic_intensity": intensity,
        "relation_placement_heuristic_hit_probability": -math.expm1(-intensity),
        "measured_prior_M32_R28_full_wall_seconds": full[
            "wrapper_subprocess_wall_seconds"],
        "measured_prior_M32_R28_peak_rss_bytes": native["peak_rss_bytes"],
        "projected_M32_R29_full_wall_seconds": wall_forecast,
        "projected_M32_R29_full_wall_hours": wall_forecast / 3600,
        "projected_wall_model": "one measured M32 table build plus twice its R28 query phase plus one measured M32 exact table replay; extra candidate processing, host variance, and startup omitted",
        "measured_natural_relation_count": None,
        "complete_solve_work_log2": None,
        "activation_gate": "Review all terminal wave receipts and independent Sage audits; do not dispatch if any verified or unverified exact hit needs review. Recompute coverage and resource forecasts first.",
        "limits": [
            "The 2.6 percent collision probability is a frozen heuristic, not measured natural relation yield.",
            "The wall projection is not a full-size M32/R29 measurement and excludes possible replay and host variation.",
            "Field-call counts omit keying, Bloom work, memory and disk traffic, failed attempts, setup, and scalar replay.",
            "No natural n83 relation or complete target DLP is present in the prior M32 receipt.",
        ],
        "screen_sha256": sha(SCREEN),
        "wave_plan_sha256": sha(WAVE),
        "coverage_ledger_sha256": sha(LEDGER),
        "prior_M32_bundle_sha256": sha(M32 / "bundle.json"),
        "prior_M32_full_sha256": sha(M32 / "full.json"),
        "prior_M32_sage_audit_sha256": sha(M32 / "sage_verify.json"),
        "portable_native_source_sha256": bundle[
            "portable_native_source_sha256"],
        "source_sha256": sha(Path(__file__)),
    }
    assert not OUTPUT.exists(), "refusing to overwrite the frozen plan"
    OUTPUT.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({
        "status": report["status"],
        "query_start": QUERY_START,
        "modeled_native_field_calls_log2": report[
            "modeled_native_field_calls_log2"],
        "heuristic_hit_probability": report[
            "relation_placement_heuristic_hit_probability"],
        "projected_full_wall_hours": report[
            "projected_M32_R29_full_wall_hours"],
    }))


if __name__ == "__main__":
    main()

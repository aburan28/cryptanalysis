#!/usr/bin/env python3
"""Audit the completed M28 pair and retain the interrupted repetition."""

import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
AGGREGATE = HERE / "runs" / "n83_signed_x_m28_hashes_paired.json"
BENCH = HERE / "bench_n83_signed_x_m28_hashes.py"
RUNNER = HERE / "run_n83_signed_x_chunk.py"
Q1051 = HERE / "runs" / "n83_orbit_k48194_chunk_M31_R30_tstart0_qstart0_b20_h14_rb8.json"
Q1054 = HERE / "n83_signed_x_screen.json"
Q1055 = HERE / "n83_signed_x_hashes_screen.json"
OUTPUT = HERE / "n83_signed_x_m28_hashes_screen.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    aggregate = json.loads(AGGREGATE.read_text())
    first = json.loads(Q1051.read_text())
    q1054 = json.loads(Q1054.read_text())
    q1055 = json.loads(Q1055.read_text())
    assert aggregate["source_sha256"] == sha(BENCH)
    assert aggregate["runner_source_sha256"] == sha(RUNNER)
    assert aggregate["hash_order"] == [14, 10, 10, 14]
    assert aggregate["candidate_id"] is None
    assert aggregate["isogeny"] == "none"
    assert aggregate["curve_id"] == first["curve_id"] == q1054[
        "curve_id"] == q1055["curve_id"]
    assert aggregate["public_target"] == first["public_target"]
    assert aggregate["factor_base_enumerated_set_sha256"] == first[
        "factor_base"]["enumerated_set_sha256"]
    assert aggregate["table_descriptors"] == 1 << 28
    assert aggregate["query_representatives"] == 1 << 24
    assert aggregate["query_start"] == 1 << 30
    assert len(aggregate["runs"]) == 3
    completed = []
    for entry, hashes in zip(aggregate["runs"][:2], (14, 10)):
        path = Path(entry["receipt"])
        record = json.loads(path.read_text())
        assert sha(path) == entry["receipt_sha256"]
        assert record["proposal_id"] == ("Q1054" if hashes == 14 else "Q1055")
        assert record["candidate_id"] is None and record["isogeny"] == "none"
        assert record["curve_id"] == aggregate["curve_id"]
        assert record["public_target"] == aggregate["public_target"]
        assert record["hashes"] == hashes
        assert record["query_start"] == aggregate["query_start"]
        assert record["native_result"]["exact_hit_queries"] == 0
        assert record["verified_public_target_quotient_table_dlp"] is False
        assert record["wrapper_source_sha256"] == sha(RUNNER)
        assert entry["guard_reason"] is None and entry["exit_code"] == 0
        assert entry["swapouts_after"] == entry["swapouts_before"]
        completed.append((entry, record))
    failed_entry = aggregate["runs"][2]
    failed_path = Path(failed_entry["receipt"])
    failed = json.loads(failed_path.read_text())
    assert sha(failed_path) == failed_entry["receipt_sha256"]
    assert failed["proposal_id"] == "Q1055"
    assert failed["kind"].endswith("chunk_failed")
    assert failed["native_phase_counts"] is None
    assert failed["cumulative_work_known"] is False
    assert failed_entry["guard_reason"] == "swap_growth"
    assert failed_entry["native_result"] is None
    base, trial = completed
    n14 = base[1]["native_result"]
    n10 = trial[1]["native_result"]
    def stage(native):
        return sum(native[key] for key in (
            "allocation_seconds", "build_seconds", "query_seconds",
            "exact_replay_seconds"))
    ratio = n10["bloom_positive_queries"] / n14["bloom_positive_queries"]
    full_positive_proxy = round(first["native_result"][
        "bloom_positive_queries"] * ratio)
    completed_calls = sum(int(record[
        "native_field_add_mul_sqr_call_model"]) for _, record in completed)
    failed_full_rectangle_model = int(base[1][
        "native_field_add_mul_sqr_call_model"])
    current_target_model_upper = (
        int(q1054["current_target_prior_Q1051_completed_field_calls"]) +
        int(q1054["current_target_prior_failed_attempts_model_upper_bound"]) +
        117 * int(q1054["modeled_field_calls_per_completed_chunk"]) +
        completed_calls + failed_full_rectangle_model)
    report = {
        "kind": "n83_signed_x_m28_hash_count_single_completed_pair_screen",
        "proposal_id": "Q1055", "candidate_id": None,
        "curve_id": aggregate["curve_id"], "isogeny": "none",
        "public_target": aggregate["public_target"],
        "factor_base_enumerated_set_sha256": aggregate[
            "factor_base_enumerated_set_sha256"],
        "actual_usable_points_B_before_folding": 8000204,
        "signed_frobenius_columns": 48194,
        "table_descriptors": 1 << 28,
        "query_representatives": 1 << 24,
        "query_start": 1 << 30,
        "completed_hash_order": [14, 10],
        "interrupted_repetition_hashes": 10,
        "measured_query_seconds": {"14": n14["query_seconds"],
                                   "10": n10["query_seconds"]},
        "measured_full_native_stage_seconds": {"14": stage(n14),
                                               "10": stage(n10)},
        "measured_query_speedup_14_over_10": n14["query_seconds"] /
            n10["query_seconds"],
        "measured_full_native_stage_speedup_14_over_10": stage(n14) /
            stage(n10),
        "measured_bloom_positives": {"14": n14["bloom_positive_queries"],
                                     "10": n10["bloom_positive_queries"]},
        "measured_bloom_positive_ratio_10_over_14": ratio,
        "measured_peak_rss_bytes": {"14": n14["peak_rss_bytes"],
                                    "10": n10["peak_rss_bytes"]},
        "measured_completed_pair_native_field_call_model_log2": math.log2(
            completed_calls),
        "interrupted_attempt_actual_native_work": None,
        "interrupted_attempt_full_rectangle_field_call_model_upper_bound": str(
            failed_full_rectangle_model),
        "interrupted_attempt_swapouts_growth_pages": failed_entry[
            "swapouts_after"] - failed_entry["swapouts_before"],
        "interrupted_attempt_terminal_receipt_sha256": sha(failed_path),
        "projected_full_M31_bloom_positives_if_M28_ratio_transfers":
            full_positive_proxy,
        "conditional_95pct_native_field_call_model_log2_unchanged": q1054[
            "standalone_95pct_prefix_modeled_field_calls_log2"],
        "current_target_conditional_95pct_field_call_model_upper_with_all_prior_attempts_log2":
            math.log2(current_target_model_upper),
        "current_target_model_upper_boundary": "one completed Q1051 full rectangle; full-rectangle structural models for three prior Q1051 interruptions; 117 future Q1054/Q1055 full rectangles; two completed M28 calibrations; one full-M28 structural model for the swap-interrupted calibration; native add/mul/sqr calls plus modeled inversions only",
        "conditional_95pct_10hash_bloom_bit_probes_log2": q1055[
            "hash_variants"]["10"]["modeled_bloom_bit_probes_p95_prefix_log2"],
        "ordinary_n83_relation_measured": False,
        "complete_solve_work_log2": None,
        "limits": [
            "Only one M28 pair completed; the reverse-order 10-hash repetition was guard-interrupted and the final 14-hash repetition did not start.",
            "The interrupted attempt has no native phase counts; its actual work and exact-hit status are unknown.",
            "The completed pair found zero exact hits. This is not a natural-relation yield rate or a complete IC DLP.",
            "Scaling the M28 positive ratio to M31 is a conditional filter-shape proxy, not measured full-size memory or throughput.",
            "Bloom probes and native field calls remain different work units; setup and scalar replay are incomplete.",
        ],
        "aggregate_sha256": sha(AGGREGATE),
        "Q1051_full_receipt_sha256": sha(Q1051),
        "Q1054_screen_sha256": sha(Q1054),
        "Q1055_small_filter_screen_sha256": sha(Q1055),
        "source_sha256": sha(Path(__file__)),
    }
    OUTPUT.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({
        "query_speedup": report["measured_query_speedup_14_over_10"],
        "full_native_stage_speedup": report[
            "measured_full_native_stage_speedup_14_over_10"],
        "positive_ratio": ratio,
        "interrupted_actual_work": None,
    }))


if __name__ == "__main__":
    main()

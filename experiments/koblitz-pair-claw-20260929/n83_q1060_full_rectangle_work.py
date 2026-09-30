#!/usr/bin/env python3
"""Reconcile the first Q1060 full rectangle with frozen finite-support work.

The first-hit distribution is a model, not a measured relation yield. This
script uses only completed terminal receipts and does not launch Sage jobs.
"""

import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs"
BASE = HERE / "n83_large_knownlog_base_screen.json"
SCREEN = HERE / "n83_spill_low_memory_screen.json"
FIRST = RUNS / "n83_orbit_k48194_chunk_M31_R30_tstart0_qstart0_b20_h14_rb8.json"
MEASURED = RUNS / (
    "n83_spill_lowmem_k48194_chunk_M28_R30_tstart0_"
    "qstart1073741824_b20_h10_rb8.json")
OUTPUT = HERE / "n83_q1060_full_rectangle_work.json"
M = 1 << 28
R = 1 << 30
RECTANGLES = 936
QUANTILES = ("0.5", "0.8", "0.9", "0.95")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def modeled_intensity(covered_fraction, mean):
    return mean * (1 - (1 - covered_fraction) ** 6)


def main():
    base = json.loads(BASE.read_text())
    screen = json.loads(SCREEN.read_text())
    first = json.loads(FIRST.read_text())
    measured = json.loads(MEASURED.read_text())
    native = measured["native_result"]
    assert base["proposal_id"] == first["proposal_id"] == "Q1051"
    assert screen["proposal_id"] == measured["proposal_id"] == "Q1060"
    assert all(row["candidate_id"] is None and row["isogeny"] == "none"
               for row in (base, screen, first, measured))
    assert all(row["curve_id"] == "EC1N83Ckb1h876c2921cb64"
               for row in (base, screen, first, measured))
    digest = base["factor_base"]["enumerated_set_sha256"]
    assert (digest == screen["factor_base_enumerated_set_sha256"] ==
            first["factor_base"]["enumerated_set_sha256"] ==
            measured["factor_base"]["enumerated_set_sha256"])
    assert measured["native_source_sha256"] == screen["native_source_sha256"]
    assert measured["native_pairs_sha256"] == screen["native_pairs_sha256"]
    assert measured["bloom_core_sha256"] == screen["bloom_core_sha256"]
    assert measured["wrapper_source_sha256"] == screen["runner_source_sha256"]
    assert sha(FIRST) == screen["first_completed_Q1051_receipt_sha256"]
    assert first["table_start"] == first["query_start"] == 0
    assert first["table_descriptors"] == 8 * M
    assert first["query_representatives"] == R
    assert first["native_result"]["exact_hit_queries"] == 0
    assert measured["table_start"] == 0 and measured["query_start"] == R
    assert measured["table_descriptors"] == M
    assert measured["query_representatives"] == R
    assert native["exact_hit_queries"] == 0 and native["hits"] == []
    assert measured["verified_public_target_quotient_table_dlp"] is False
    assert native["candidate_store_mode"] == "unlinked_file"

    per_rectangle = int(measured["native_field_add_mul_sqr_call_model"])
    first_calls = int(first["native_field_add_mul_sqr_call_model"])
    assert math.isclose(math.log2(RECTANGLES * per_rectangle),
                        screen["modeled_future_native_field_calls_log2"])
    qfrac = R * base["factor_base"]["signed_frobenius_orbit_size"] / (
        base["unordered_query_pair_domain"])
    shard_fraction = (M / base["zero_pair_key_cap_before_accidental_collisions"]
                      * qfrac)
    initial_coverage = 8 * shard_fraction
    mean = base["heuristic_mean_four_point_multisets"]
    start_intensity = modeled_intensity(initial_coverage + shard_fraction,
                                        mean)
    cdf = [0.0] + [
        -math.expm1(-(modeled_intensity(
            initial_coverage + (1 + count) * shard_fraction, mean) -
            start_intensity))
        for count in range(1, RECTANGLES)]
    assert all(a <= b for a, b in zip(cdf, cdf[1:]))
    assert cdf[-1] < screen[
        "modeled_plan_end_success_probability_conditional_on_first_no_hit"]
    conditional_success = cdf[-1]
    expected_more = sum(
        count * (cdf[count] - cdf[count - 1])
        for count in range(1, RECTANGLES)) / conditional_success
    quantiles = {}
    for label in QUANTILES:
        more = next((count for count in range(1, RECTANGLES)
                     if cdf[count] >= float(label)), None)
        quantiles[label] = {
            "additional_completed_rectangles": more,
            "total_Q1060_completed_rectangles": 1 + more if more else None,
            "modeled_conditional_success_probability":
                cdf[more] if more else None,
            "Q1051_plus_Q1060_field_calls_log2":
                math.log2(first_calls + (1 + more) * per_rectangle)
                if more else None,
        }
    report = {
        "kind": "n83_q1060_first_full_rectangle_measured_and_conditional_work",
        "scope": "one measured natural-target zero-hit rectangle plus a frozen finite-support first-hit model; no completed quotient-table DLP",
        "proposal_id": "Q1060", "candidate_id": None, "run_id": None,
        "curve_id": measured["curve_id"], "isogeny": "none",
        "public_target": measured["public_target"],
        "factor_base_enumerated_set_sha256": digest,
        "actual_usable_points_B_before_folding": measured["factor_base"][
            "actual_usable_points_B_before_folding"],
        "signed_frobenius_columns": measured["factor_base"][
            "signed_frobenius_columns"],
        "measured_first_Q1060_rectangle": {
            "table_start": measured["table_start"],
            "query_start": measured["query_start"],
            "table_descriptors": M, "query_representatives": R,
            "bloom_positive_queries": native["bloom_positive_queries"],
            "exact_hit_queries": native["exact_hit_queries"],
            "candidate_spill_bytes": native["candidate_spill_bytes"],
            "peak_rss_bytes": native["peak_rss_bytes"],
            "build_seconds": native["build_seconds"],
            "query_seconds": native["query_seconds"],
            "exact_replay_seconds": native["exact_replay_seconds"],
            "target_online_seconds": measured["target_online_seconds"],
            "subprocess_wall_seconds": measured[
                "wrapper_subprocess_wall_seconds"],
            "field_call_model": str(per_rectangle),
            "field_call_model_log2": math.log2(per_rectangle),
            "terminal_receipt_sha256": sha(MEASURED),
            "sage_runtime_info_sha256": measured["sage_runtime_info_sha256"],
        },
        "frozen_model_after_first_Q1051_and_first_Q1060_no_hits": {
            "remaining_disjoint_rectangles": RECTANGLES - 1,
            "probability_of_hit_by_plan_end_conditional_on_no_hits_so_far":
                conditional_success,
            "probability_of_no_hit_by_plan_end_conditional_on_no_hits_so_far":
                1 - conditional_success,
            "expected_additional_rectangles_given_hit_by_plan_end":
                expected_more,
            "expected_Q1051_plus_Q1060_field_calls_given_hit_log2":
                math.log2(first_calls + (1 + expected_more) * per_rectangle),
            "first_hit_quantiles": quantiles,
            "all_Q1051_plus_Q1060_plan_field_calls_log2":
                math.log2(first_calls + RECTANGLES * per_rectangle),
            "all_remaining_Q1060_online_seconds_if_first_rate_transfers":
                (RECTANGLES - 1) * measured["target_online_seconds"],
            "all_remaining_Q1060_subprocess_days_if_first_rate_transfers":
                (RECTANGLES - 1) * measured[
                    "wrapper_subprocess_wall_seconds"] / 86400,
        },
        "field_call_boundary": measured["field_call_model_boundary"],
        "complete_solve_work_log2": None,
        "ordinary_n83_relation_measured": False,
        "limits": [
            "The first-hit distribution is the Q1051 random-base finite-support heuristic; zero observed hits do not calibrate its natural relation yield.",
            "The field-call model omits keying, Bloom operations, memory and SSD traffic, historical failed attempts, and independent scalar replay.",
            "Projected days transfer one rectangle's rate to all other disjoint rectangles; they are not a measured full-campaign duration or a guarantee of success.",
            "The first Q1051 and first Q1060 completed receipts are included in modeled total field calls; historical failed attempts have unknown actual work.",
        ],
        "base_screen_sha256": sha(BASE),
        "Q1060_screen_sha256": sha(SCREEN),
        "first_Q1051_receipt_sha256": sha(FIRST),
        "source_sha256": sha(Path(__file__)),
    }
    OUTPUT.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({
        "measured_field_calls_log2": math.log2(per_rectangle),
        "modeled_expected_total_field_calls_given_hit_log2": report[
            "frozen_model_after_first_Q1051_and_first_Q1060_no_hits"][
                "expected_Q1051_plus_Q1060_field_calls_given_hit_log2"],
        "modeled_plan_end_success_probability": conditional_success,
        "complete_solve_work_log2": None,
    }))


if __name__ == "__main__":
    main()

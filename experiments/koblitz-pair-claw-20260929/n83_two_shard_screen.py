#!/usr/bin/env python3
"""Conditional two-table quotient-search work and memory screen for n=83."""

import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE_SCREEN = HERE / "n83_large_knownlog_base_screen.json"
PAIRED = HERE / "runs" / "n83_two_shard_paired_bounded.json"
PLANTED = HERE / "runs" / "n83_two_shard_second_table_planted.json"
OUTPUT = HERE / "n83_two_shard_screen.json"
M = 1 << 31
R = 1 << 30
L = 166


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def probability(chunks, mean, table_fraction, query_fraction_per_chunk):
    fraction = table_fraction * chunks * query_fraction_per_chunk
    assert 0 <= fraction <= 1
    return -math.expm1(-mean * (1 - (1 - fraction) ** 6))


def main():
    base = json.loads(BASE_SCREEN.read_text())
    paired = json.loads(PAIRED.read_text())
    planted = json.loads(PLANTED.read_text())
    factor = base["factor_base"]
    assert base["proposal_id"] == "Q1051" and base["candidate_id"] is None
    assert base["isogeny"] == "none"
    assert factor["actual_usable_points_B_before_folding"] == 8000204
    assert factor["signed_frobenius_columns"] == 48194
    assert factor["signed_frobenius_orbit_size"] == L
    assert paired["proposal_id"] == planted["proposal_id"] == "Q1052"
    assert paired["candidate_id"] is None and planted["candidate_id"] is None
    assert paired["curve_id"] == planted["curve_id"] == base["curve_id"]
    assert paired["isogeny"] == planted["isogeny"] == "none"
    assert paired["factor_base_enumerated_set_sha256"] == planted[
        "factor_base_enumerated_set_sha256"] == factor[
        "enumerated_set_sha256"]
    assert paired["identical_per_shard_exact_outcomes"] is True
    assert planted["verified_relation"]["independent_scalar_replay"] is True
    assert planted["native_result"]["exact_hit_queries"] >= 1
    assert planted["native_result"]["per_shard"][1][
        "exact_hit_queries"] >= 1
    assert paired["double_source_sha256"] == planted[
        "native_source_sha256"] == sha(HERE /
        "native_n83_orbit_query_two_shard.cpp")
    assert paired["bloom_core_sha256"] == planted[
        "bloom_core_sha256"]
    assert paired["native_pairs_sha256"] == planted[
        "native_pairs_sha256"]
    assert paired["source_sha256"] == sha(HERE /
        "bench_n83_two_shard_paired.py")
    assert planted["source_sha256"] == sha(HERE /
        "verify_n83_two_shard_planted.py")
    mean = base["heuristic_mean_four_point_multisets"]
    table_fraction = 2 * M / base[
        "zero_pair_key_cap_before_accidental_collisions"]
    query_fraction_per_chunk = R * L / base[
        "unordered_query_pair_domain"]
    max_chunks = base["cross_orbit_query_representative_domain"] // R
    low, high = 1, max_chunks
    while low < high:
        middle = (low + high) // 2
        if probability(middle, mean, table_fraction,
                       query_fraction_per_chunk) >= 0.95:
            high = middle
        else:
            low = middle + 1
    chunks = low
    assert chunks == 59
    assert probability(chunks - 1, mean, table_fraction,
                       query_fraction_per_chunk) < 0.95
    assert math.isclose(probability(chunks, mean, table_fraction,
                                    query_fraction_per_chunk), base[
        "model_success_probability_at_prefix"])
    inversions = 4 * math.ceil(M / 1024) + 2 * math.ceil(R / 8)
    calls_per_chunk = 52 * M + 13 * R + 13 * R * L + 90 * inversions
    measured = base["measured_extended_base_2pow31_stage"]
    two_over_one_query_ratio = (2 /
        paired["bounded_query_speedup_separate_over_shared"])
    projected_query_seconds_eight = (measured["query_seconds"] *
                                     R / (1 << 20) *
                                     two_over_one_query_ratio)
    projected_build_replay_seconds = 2 * (
        measured["build_seconds"] + measured["exact_replay_seconds"])
    days_eight = chunks * (projected_build_replay_seconds +
                           projected_query_seconds_eight) / 86400
    days_fourteen = chunks * (projected_build_replay_seconds +
        projected_query_seconds_eight /
        base["paired_bounded_query_speedup_14_vs_8_workers"]) / 86400
    overhead = (measured["peak_rss_bytes"] - measured["bloom_bytes"] -
                0)
    illustrative_candidate_capacity = (
        2 * 2 * R * L * base["measured_2pow31_false_positive_fraction"] *
        24)
    illustrative_peak = (2 * measured["bloom_bytes"] + overhead +
                         illustrative_candidate_capacity)
    report = {
        "kind": "n83_two_table_shared_query_conditional_screen",
        "scope": "Q1052 bounded exact-outcome and planted controls plus finite-support prediction; no natural n83 relation or complete IC DLP",
        "proposal_id": "Q1052", "candidate_id": None,
        "curve_id": base["curve_id"],
        "curve_identity_record": base["curve_identity_record"],
        "isogeny": "none",
        "factor_base": factor,
        "table_shards": 2,
        "table_descriptors_per_shard": M,
        "total_table_descriptors": 2 * M,
        "campaign_query_workers": 14,
        "query_representatives_per_chunk": R,
        "query_chunks_for_95pct_model": chunks,
        "zero_pair_key_cap_before_accidental_collisions": base[
            "zero_pair_key_cap_before_accidental_collisions"],
        "unordered_query_pair_domain": base[
            "unordered_query_pair_domain"],
        "heuristic_mean_four_point_multisets": mean,
        "model_success_probability_at_prefix": probability(
            chunks, mean, table_fraction, query_fraction_per_chunk),
        "model_success_probability_after_all_full_query_chunks":
            probability(max_chunks, mean, table_fraction,
                        query_fraction_per_chunk),
        "native_field_add_mul_sqr_call_model_per_chunk": str(
            calls_per_chunk),
        "native_field_add_mul_sqr_call_model_95pct_prefix": str(
            chunks * calls_per_chunk),
        "native_field_add_mul_sqr_call_model_95pct_prefix_log2":
            math.log2(chunks * calls_per_chunk),
        "q1051_active_R30_95pct_field_call_model_log2": math.log2(
            118 * (26 * M + 13 * R + 13 * R * L +
                   90 * (2 * math.ceil(M / 1024) +
                         2 * math.ceil(R / 8)))),
        "measured_bounded_one_worker_query_speedup_two_separate_over_shared":
            paired["bounded_query_speedup_separate_over_shared"],
        "projected_days_from_bounded_eight_worker_rate": days_eight,
        "projected_days_if_small_filter_query_ratio_and_14_worker_speedup_transfer":
            days_fourteen,
        "two_full_filter_bytes": 2 * measured["bloom_bytes"],
        "illustrative_candidate_capacity_bytes":
            illustrative_candidate_capacity,
        "illustrative_full_chunk_peak_filter_phase_bytes":
            illustrative_peak,
        "bounded_per_shard_exact_outcomes_match_single_table_runs": True,
        "planted_second_table_scalar_replay_passed": True,
        "ordinary_n83_relation_measured": False,
        "complete_solve_work_log2": None,
        "assumptions_and_limits": [
            "The four-point relation probability is the same finite-support random-base heuristic used for Q1051, with two disjoint table shards and a shared query range.",
            "The field-call model counts both table builds and both exact replays per chunk, one representative query-pair pass, all 166 target complements, and modeled inversions; it excludes keying, Bloom, memory, base setup, and scalar replay.",
            "The paired query ratio was measured with one worker and small filters while a full-size Q1051 run shared the host; full-size two-filter throughput is unknown.",
            "The 14-worker wall projection combines separate bounded calibrations and is not a full-size measurement.",
            "The peak-memory illustration uses twice the expected Bloom-positive candidate capacity and constant base-process overhead; it is not a memory bound.",
            "The planted witness proves the second-shard verification path, not natural relation yield.",
        ],
        "base_screen_sha256": sha(BASE_SCREEN),
        "paired_receipt_sha256": sha(PAIRED),
        "planted_receipt_sha256": sha(PLANTED),
        "source_sha256": sha(Path(__file__)),
    }
    OUTPUT.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({
        "curve_id": report["curve_id"],
        "actual_B": factor["actual_usable_points_B_before_folding"],
        "chunks": chunks,
        "model_probability": report["model_success_probability_at_prefix"],
        "field_calls_log2": report[
            "native_field_add_mul_sqr_call_model_95pct_prefix_log2"],
        "projected_days": days_fourteen,
    }))


if __name__ == "__main__":
    main()

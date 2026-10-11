#!/usr/bin/env python3
"""Conditional memory, time, yield, and field-call model for n=83 shards."""

import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
FINITE = HERE / "n83_knownlog_conditional_screen.json"
CALIBRATION = HERE / "runs" / "n83_bloom_bits20_stage_M28_Q24.json"
PLANTED = HERE / "runs" / "n83_bloom_bits20_nonzero_shard_planted.json"
INTERRUPTED = HERE / "runs" / "n83_bloom_chunk_M33_Q38_start0.json"
OUTPUT = HERE / "n83_bloom_shard_screen.json"
M = 1 << 32
Q = 1 << 38
BATCH = 1024
BITS = 20
HASHES = 14


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def success_probability(finite, table_descriptors, queries):
    table_fraction = table_descriptors / finite[
        "signed_frobenius_zero_pair_key_cap_before_accidental_collisions"]
    query_fraction = queries / finite["unordered_pair_domain"]
    mean = finite[
        "heuristic_mean_four_point_multiset_relations_for_one_target"]
    return -math.expm1(-mean * (1 - (1 - table_fraction * query_fraction) ** 6))


def field_calls(table_descriptors, queries):
    inversions = (2 * math.ceil(table_descriptors / BATCH) +
                  2 * math.ceil(queries / BATCH))
    return 26 * table_descriptors + 27 * queries + 90 * inversions


def wilson95(positives, trials):
    z = 1.959963984540054
    p = positives / trials
    denominator = 1 + z * z / trials
    center = (p + z * z / (2 * trials)) / denominator
    half = z * math.sqrt(p * (1 - p) / trials +
                         z * z / (4 * trials * trials)) / denominator
    return [max(0.0, center - half), min(1.0, center + half)]


def main():
    finite = json.loads(FINITE.read_text())
    calibration = json.loads(CALIBRATION.read_text())
    planted = json.loads(PLANTED.read_text())
    interrupted = json.loads(INTERRUPTED.read_text())
    curve_id = finite["curve_id"]
    assert curve_id == calibration["curve_id"] == planted["curve_id"] == interrupted["curve_id"]
    assert calibration["factor_base"]["enumerated_set_sha256"] == finite[
        "factor_base_enumerated_set_sha256"]
    assert calibration["isogeny"] == "none"
    assert calibration["bits_per_key"] == BITS
    assert calibration["hashes"] == HASHES
    assert calibration["native_result"]["exact_hit_queries"] == 0
    assert planted["verified_relation"]["independent_scalar_replay"] is True
    assert planted["natural_relation_yield"] is False
    assert interrupted["native_phase_counts"] is None
    row = calibration["native_result"]
    measured_m = calibration["table_descriptors"]
    measured_q = calibration["query_count"]
    positives = row["false_positive_queries"]
    rate = positives / measured_q
    false_positive_interval = wilson95(positives, measured_q)
    bloom_bytes = ((M * BITS + 511) // 512 + 1024) * 64
    projected_candidates = Q * rate
    # Observed small-run non-filter RSS is a proxy. Vector capacity is
    # illustrated at twice the candidate count, not guaranteed by C++.
    non_filter_bytes = (row["peak_rss_bytes"] - row["bloom_bytes"] -
                        row["candidate_vector_capacity_bytes"])
    illustrative_vector_bytes = (2 * projected_candidates *
                                 row["candidate_record_bytes"])
    projected_candidates_interval = [Q * value for value in
                                     false_positive_interval]
    projected_seconds = (
        row["build_seconds"] * M / measured_m +
        row["query_seconds"] * Q / measured_q +
        row["exact_replay_seconds"] * M / measured_m)
    one_calls = field_calls(M, Q)
    target_95_queries = next(item[
        "ideal_unique_query_pairs_for_95pct_success"]
        for item in finite["tradeoff_rows"]
        if item["hypothetical_distinct_table_keys"] == 1 << 33)
    two_shard_95_calls = 2 * field_calls(M, target_95_queries)
    two_shard_95_seconds = 2 * (
        row["build_seconds"] * M / measured_m +
        row["query_seconds"] * target_95_queries / measured_q +
        row["exact_replay_seconds"] * M / measured_m)
    bounded_chunks_per_shard = math.ceil(target_95_queries / Q)
    bounded_query_prefix = bounded_chunks_per_shard * Q
    assert bounded_query_prefix <= finite["unordered_pair_domain"]
    bounded_calls = 2 * bounded_chunks_per_shard * one_calls
    bounded_seconds = 2 * bounded_chunks_per_shard * projected_seconds
    full_prefix_candidates = target_95_queries * rate
    full_prefix_illustrative_peak = (
        bloom_bytes + 2 * full_prefix_candidates *
        row["candidate_record_bytes"] + non_filter_bytes)
    report = {
        "kind": "n83_20bit_bloom_two_shard_conditional_screen",
        "scope": "projection from measured 2^28-key, 2^24-query run; no ordinary n83 relation or IC DLP claimed",
        "proposal_id": "Q1049", "candidate_id": None,
        "curve_id": curve_id,
        "curve_identity_record": finite["curve_identity_record"],
        "isogeny": "none",
        "actual_usable_points_B_before_folding": finite[
            "actual_usable_points_B_before_folding"],
        "signed_frobenius_columns": finite[
            "actual_signed_frobenius_columns"],
        "factor_base_enumerated_set_sha256": finite[
            "factor_base_enumerated_set_sha256"],
        "bits_per_key": BITS,
        "hashes": HASHES,
        "shard_table_descriptors": M,
        "first_shard_table_start": 0,
        "second_shard_table_start": M,
        "first_query_count": Q,
        "measured_table_descriptors": measured_m,
        "measured_target_queries": measured_q,
        "measured_false_positive_queries": positives,
        "measured_false_positive_rate": rate,
        "measured_false_positive_rate_wilson95":
            false_positive_interval,
        "measured_public_target_exact_hits": row["exact_hit_queries"],
        "planted_nonzero_shard_scalar_replay_passed": True,
        "one_shard_heuristic_relation_probability": success_probability(
            finite, M, Q),
        "two_shard_heuristic_relation_probability": success_probability(
            finite, 2 * M, Q),
        "one_shard_bloom_bytes": bloom_bytes,
        "one_shard_projected_positive_queries": projected_candidates,
        "one_shard_projected_positive_queries_wilson95":
            projected_candidates_interval,
        "one_shard_illustrative_twice_count_candidate_vector_bytes":
            illustrative_vector_bytes,
        "one_shard_illustrative_peak_filter_phase_bytes": (
            bloom_bytes + illustrative_vector_bytes + non_filter_bytes),
        "one_shard_projected_seconds_from_small_run_rates":
            projected_seconds,
        "one_shard_conditional_field_add_mul_sqr_calls": str(one_calls),
        "one_shard_conditional_field_add_mul_sqr_calls_log2":
            math.log2(one_calls),
        "two_shard_95pct_model_queries_each": target_95_queries,
        "two_shard_95pct_model_field_add_mul_sqr_calls": str(
            two_shard_95_calls),
        "two_shard_95pct_model_field_add_mul_sqr_calls_log2":
            math.log2(two_shard_95_calls),
        "two_shard_95pct_model_projected_seconds_from_small_run_rates":
            two_shard_95_seconds,
        "two_shard_95pct_one_pass_each_illustrative_peak_filter_bytes":
            full_prefix_illustrative_peak,
        "bounded_95pct_chunks_per_shard": bounded_chunks_per_shard,
        "bounded_95pct_total_chunk_runs": 2 * bounded_chunks_per_shard,
        "bounded_95pct_query_prefix_each_shard": bounded_query_prefix,
        "bounded_95pct_model_relation_probability":
            success_probability(finite, 2 * M, bounded_query_prefix),
        "bounded_95pct_conditional_field_add_mul_sqr_calls": str(
            bounded_calls),
        "bounded_95pct_conditional_field_add_mul_sqr_calls_log2":
            math.log2(bounded_calls),
        "bounded_95pct_projected_seconds_from_small_run_rates":
            bounded_seconds,
        "interrupted_24bit_2pow33_attempt_work_known": False,
        "complete_one_target_work_log2": None,
        "verified_n83_quotient_table_dlp": False,
        "same_target_rho_reference": finite[
            "n83_same_target_rho_reference"],
        "assumptions_and_limits": [
            "The success probabilities use the finite-support Poisson heuristic, not measured ordinary relation yield.",
            "The projected time scales small-run rates linearly and may be inaccurate at a 10 GiB random-access Bloom filter.",
            "The projected candidate vector uses twice the expected number of positives as an illustrative capacity, not a memory bound.",
            "The Wilson interval assumes independent Bloom outcomes; deterministic query ordering and correlated keys may invalidate its nominal 95pct coverage.",
            "The build, query, and replay time projection uses one bounded run, so its timing uncertainty has not been estimated.",
            "The 95pct field-call count assumes exactly two shards, each scanned with the same unique query prefix; each build and exact replay is charged.",
            "The two one-pass 95pct shard projection would retain too many positives for the current host's available memory; it is a lower-work proxy, not the operational plan.",
            "The bounded 95pct plan uses 29 complete 2^38-query chunks per table shard, rebuilding and exactly replaying each chunk because the current runner retains positives in memory.",
            "The field-call model omits quotient-keying, Bloom hashes and probes, memory traffic, base construction, and independent verification; it is not complete solve work.",
            "The interrupted 24-bit attempt has unknown consumed work and cannot be silently counted as zero in a cumulative campaign cost.",
        ],
        "finite_support_screen_sha256": sha(FINITE),
        "calibration_receipt_sha256": sha(CALIBRATION),
        "planted_receipt_sha256": sha(PLANTED),
        "interrupted_receipt_sha256": sha(INTERRUPTED),
        "source_sha256": sha(Path(__file__)),
    }
    OUTPUT.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({
        "curve_id": curve_id,
        "one_shard_heuristic_relation_probability": report[
            "one_shard_heuristic_relation_probability"],
        "two_shard_heuristic_relation_probability": report[
            "two_shard_heuristic_relation_probability"],
        "one_shard_projected_hours": projected_seconds / 3600,
        "one_shard_illustrative_peak_GiB": report[
            "one_shard_illustrative_peak_filter_phase_bytes"] / (1 << 30),
        "one_shard_field_calls_log2": math.log2(one_calls),
        "two_shard_95pct_field_calls_log2": math.log2(two_shard_95_calls),
        "two_shard_95pct_projected_days": two_shard_95_seconds / 86400,
        "bounded_95pct_total_chunk_runs": 2 * bounded_chunks_per_shard,
        "bounded_95pct_field_calls_log2": math.log2(bounded_calls),
        "bounded_95pct_projected_days": bounded_seconds / 86400,
    }))


if __name__ == "__main__":
    main()

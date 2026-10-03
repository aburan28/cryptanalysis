#!/usr/bin/env python3
"""Conditional n83 Bloom-filter resource and solve-work projection."""

import hashlib
import json
import math
import re
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE_SCREEN = HERE / "n83_knownlog_conditional_screen.json"
BLOOM = HERE / "runs" / "n83_native_bloom_exact_replay_perf.json"
EXACT = HERE / "runs" / "n83_native_exact_table_perf.json"
OUTPUT = HERE / "n83_bloom_resource_screen.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def physical_memory_bytes():
    try:
        result = subprocess.run(
            ["memory_pressure", "-Q"], check=True, capture_output=True,
            text=True)
        match = re.search(r"The system has (\d+) ", result.stdout)
        return int(match.group(1)) if match else None
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None


def main():
    screen = json.loads(BASE_SCREEN.read_text())
    bloom = json.loads(BLOOM.read_text())
    exact = json.loads(EXACT.read_text())
    assert screen["curve_id"] == bloom["curve_id"] == exact["curve_id"]
    assert screen["factor_base_enumerated_set_sha256"] == bloom[
        "factor_base"]["enumerated_set_sha256"]
    assert bloom["verified_public_target_quotient_table_dlp"] is False
    assert bloom["planted_control"]["verified_relation"][
        "independent_scalar_replay"] is True
    row = next(item for item in screen["tradeoff_rows"]
               if item["hypothetical_distinct_table_keys"] == 1 << 33)
    measured = bloom["public_target_runs"][-1]
    assert measured["table_descriptors"] == 1 << 28
    M = row["hypothetical_distinct_table_keys"]
    Q = row["ideal_unique_query_pairs_for_95pct_success"]
    bits = bloom["bloom_bits_per_table_descriptor"]
    bloom_bytes = ((M * bits + 511) // 512 + 1024) * 64
    candidate_record_bytes = measured["candidate_record_bytes"]
    exact_slot_bytes = measured["candidate_exact_slot_bytes"]
    rate = measured["false_positive_rate"]
    low, high = measured["false_positive_rate_wilson95"]
    candidates = [Q * value for value in (low, rate, high)]
    # std::vector growth is implementation-dependent; twice the element
    # count is an illustrative upper envelope, not an observed bound.
    candidate_capacity_bytes = [2 * count * candidate_record_bytes
                                for count in candidates]
    exact_candidate_table_bytes = [
        (count * 10 / 7 + 1024) * exact_slot_bytes
        for count in candidates]
    last_exact = exact["runs"][-1]
    observed_non_table_rss_bytes = (last_exact["peak_rss_bytes"] -
                                    last_exact["table_bytes"])
    query_ns = measured["query_ns_per_pair_including_filter"]
    build_ns = measured["build_ns_per_descriptor"]
    replay_ns = measured["exact_replay_ns_per_descriptor"]
    build_days = M * build_ns / 1e9 / 86400
    online_query_days = Q * query_ns / 1e9 / 86400
    online_replay_days = M * replay_ns / 1e9 / 86400
    # Existing field-call model has one table pass; exact Bloom replay
    # makes a second. One regular table pair takes 13 add/mul/sqr calls,
    # plus 90 calls for its batch inversion.
    batch = bloom["batch_size"]
    original_field_calls = 2 ** row[
        "conditional_native_batch_field_add_mul_sqr_calls_log2"]
    projected_field_calls = (original_field_calls + 13 * M +
                             90 * math.ceil(M / batch))
    host_memory = physical_memory_bytes()
    report = {
        "kind": "n83_knownlog_bloom_exact_replay_conditional_resource_screen",
        "scope": "bounded measured n83 Bloom stage extrapolated to 95pct finite-support model; no ordinary target relation or quotient-table DLP",
        "proposal_id": "Q1048", "candidate_id": None,
        "curve_id": bloom["curve_id"],
        "curve_identity_record": bloom["curve_identity_record"],
        "isogeny": "none",
        "public_target": bloom["public_target"],
        "actual_usable_points_B_before_folding": bloom["factor_base"][
            "actual_usable_points_B_before_folding"],
        "signed_frobenius_columns": bloom["factor_base"][
            "signed_frobenius_columns"],
        "factor_base_enumerated_set_sha256": bloom["factor_base"][
            "enumerated_set_sha256"],
        "model_success_probability": .95,
        "hypothetical_table_keys": M,
        "hypothetical_unique_query_pairs": Q,
        "hypothetical_pair_evaluations_including_exact_replay_log2":
            math.log2(2 * M + Q),
        "conditional_native_field_add_mul_sqr_calls_including_replay_log2":
            math.log2(projected_field_calls),
        "bloom_bits_per_key": bits,
        "bloom_hashes_per_key": bloom["bloom_hashes_per_key"],
        "bloom_blocks_per_key": bloom["bloom_blocks_per_key"],
        "hypothetical_bloom_bytes": bloom_bytes,
        "measured_false_positive_rate": rate,
        "measured_false_positive_rate_wilson95": [low, high],
        "hypothetical_candidate_queries_low_point_high": candidates,
        "hypothetical_candidate_record_bytes": candidate_record_bytes,
        "illustrative_twice_count_candidate_vector_bytes_low_point_high":
            candidate_capacity_bytes,
        "illustrative_exact_candidate_table_bytes_low_point_high":
            exact_candidate_table_bytes,
        "observed_nontable_rss_bytes_at_2pow28_exact_table":
            observed_non_table_rss_bytes,
        "illustrative_peak_filter_phase_bytes_point":
            bloom_bytes + candidate_capacity_bytes[1] +
            observed_non_table_rss_bytes,
        "illustrative_peak_filter_phase_bytes_high95":
            bloom_bytes + candidate_capacity_bytes[2] +
            observed_non_table_rss_bytes,
        "host_physical_memory_bytes_from_memory_pressure": host_memory,
        "measured_table_key_count": measured["table_descriptors"],
        "measured_unique_target_queries": measured["query_pairs"],
        "measured_exact_public_target_hits": measured["exact_hit_queries"],
        "measured_planted_control_verified": True,
        "one_core_proxy_cold_filter_build_days": build_days,
        "one_core_proxy_online_query_days": online_query_days,
        "one_core_proxy_online_exact_replay_days": online_replay_days,
        "one_core_proxy_cold_total_days_excluding_setup_checks":
            build_days + online_query_days + online_replay_days,
        "complete_solve_work_log2": None,
        "verified_n83_quotient_table_dlp": False,
        "n83_same_target_rho_reference": screen[
            "n83_same_target_rho_reference"],
        "assumptions_and_limits": [
            "The 95pct relation model is a random-base finite-support heuristic; no ordinary relation or quotient-table target DLP was measured.",
            "Bloom positives are checked by an exact second pass. At full size, the positive count and query lookup rate may differ from the bounded 2^28-key, 2^24-query run.",
            "The Wilson interval treats deterministic distinct query-key outcomes as independent Bernoulli observations; correlations could invalidate its nominal coverage.",
            "Candidate vector capacity is illustrated as twice the positive count. Actual C++ vector growth and memory fragmentation are unmeasured at full size.",
            "The filter and candidate vector coexist during queries; the filter is released before constructing the exact candidate table for replay.",
            "The day proxies use one-core bounded rates and omit candidate-table construction, allocation, base setup, memory pressure, scheduling, final answer verification, and any scaling slowdown.",
            "The field-call model counts add, multiply, and square calls, including inversion chains, but excludes bit-level canonicalization, Bloom hashes and probes, memory traffic, and final answer verification.",
            "Physical memory alone does not guarantee that the full run fits available memory without paging under other host load.",
        ],
        "bloom_receipt_sha256": sha(BLOOM),
        "finite_support_screen_sha256": sha(BASE_SCREEN),
        "exact_table_receipt_sha256": sha(EXACT),
        "source_sha256": sha(Path(__file__)),
    }
    OUTPUT.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({
        "curve_id": report["curve_id"],
        "bloom_bytes": bloom_bytes,
        "candidate_queries_point": candidates[1],
        "peak_filter_phase_bytes_point": report[
            "illustrative_peak_filter_phase_bytes_point"],
        "physical_memory_bytes": host_memory,
        "one_core_proxy_cold_total_days": report[
            "one_core_proxy_cold_total_days_excluding_setup_checks"],
        "field_calls_log2": report[
            "conditional_native_field_add_mul_sqr_calls_including_replay_log2"],
    }))


if __name__ == "__main__":
    main()

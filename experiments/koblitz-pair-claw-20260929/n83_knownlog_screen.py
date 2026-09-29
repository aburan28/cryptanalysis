#!/usr/bin/env python3
"""Finite-support work screen for one target on the exact n=83 known-log base."""

import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE / "runs" / "n83_knownlog_orbit_base.json"
PERF = HERE / "runs" / "n83_knownlog_pair_perf.json"
BATCH_PERF = HERE / "runs" / "n53_n83_batch_xkey_perf.json"
SCHEDULE_PERF = HERE / "runs" / "n53_n83_unique_schedule_perf.json"
FIELD_PERF = HERE / "runs" / "n53_n83_field_unit_perf.json"
N53 = HERE / "runs" / "n53_knownlog_one_target.json"
OUTPUT = HERE / "n83_knownlog_conditional_screen.json"
TARGET_SUCCESS = 0.95


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def success(mean_relations, table_fraction, query_fraction):
    # One four-point multiset has six zero-pair/query-pair partitions.
    covered = 1 - (1 - table_fraction * query_fraction) ** 6
    return -math.expm1(-mean_relations * covered)


def main():
    base = json.loads(BASE.read_text())
    perf = json.loads(PERF.read_text())
    batch = json.loads(BATCH_PERF.read_text())
    schedule = json.loads(SCHEDULE_PERF.read_text())
    field_cal = json.loads(FIELD_PERF.read_text())
    n53 = json.loads(N53.read_text())
    assert base["curve_id"] == perf["curve_id"] == "EC1N83Ckb1h876c2921cb64"
    assert n53["verified_single_target_dlp"] is True
    record = base["factor_base"]
    order = base["curve_identity_record"]["curve"]["subgroup_order"]
    B = record["actual_usable_points_B_before_folding"]
    K = record["signed_frobenius_columns"]
    L = record["signed_frobenius_orbit_size"]
    assert B == 4000102 and K == 24097 and L == 166
    assert record["unknown_log_columns"] == 0
    assert batch["runs"][1]["curve_id"] == base["curve_id"]
    assert schedule["runs"][1]["curve_id"] == base["curve_id"]
    pair_domain = math.comb(B + 1, 2)
    # Cross-orbit unordered pairs have L relative positions. Within one
    # orbit there are L/2+1 pair classes, including one identity class.
    # The identity class is excluded from a proper four-point relation.
    key_cap = math.comb(K, 2) * L + K * (L // 2)
    mean_relations = math.comb(B + 3, 4) / order
    required_partition_coverage = 1 - (
        1 - (-math.log1p(-TARGET_SUCCESS) / mean_relations)
    ) ** (1 / 6)
    minimum_keys = math.ceil(key_cap * required_partition_coverage)
    scheduled = schedule["runs"][1]
    assert scheduled["unique_table_descriptors_checked"] == 32768
    assert scheduled["unique_query_pair_ranks_checked"] == 32768
    table_ns = scheduled["table_ns_per_sample"]
    query_ns = scheduled["query_ns_per_sample"]
    table_calls = perf["table_field_api_calls_per_sample"]
    query_calls = perf["query_field_api_calls_per_sample"]
    calibration = field_cal["runs"][1]
    assert calibration["degree"] == 83
    weights = calibration["time_ratio_to_one_mul"]
    mul_ns = calibration["operations"]["mul"]["median_ns_per_call"]
    table_units = sum(table_calls.get(name, 0) for name in
                      ("add", "mul", "sqr", "inv"))
    query_units = sum(query_calls.get(name, 0) for name in
                      ("add", "mul", "sqr", "inv"))
    table_mul_units = sum(table_calls.get(name, 0) * weights[name] for name in
                          ("add", "mul", "sqr", "inv"))
    query_mul_units = sum(query_calls.get(name, 0) * weights[name] for name in
                          ("add", "mul", "sqr", "inv"))
    rows = []
    for M in (1 << 20, 1 << 24, 1 << 27, 1 << 30,
              1 << 32, 1 << 33, 1 << 34, key_cap):
        if M > key_cap:
            continue
        fraction = M / key_cap
        max_success = success(mean_relations, fraction, 1)
        possible = max_success + 1e-12 >= TARGET_SUCCESS
        unique_queries = None
        replacement_queries = None
        unit_work_log2 = None
        field_mul_time_work_log2 = None
        sampled_stage_mul_time_work_log2 = None
        python_years = None
        if possible:
            query_fraction = required_partition_coverage / fraction
            unique_queries = query_fraction * pair_domain
            if query_fraction < 1:
                replacement_queries = -pair_domain * math.log1p(-query_fraction)
            unit_work_log2 = math.log2(M * table_units +
                                       unique_queries * query_units)
            field_mul_time_work_log2 = math.log2(
                M * table_mul_units + unique_queries * query_mul_units)
            sampled_stage_mul_time_work_log2 = math.log2(
                (M * table_ns + unique_queries * query_ns) / mul_ns)
            python_years = (
                M * table_ns + unique_queries * query_ns
            ) / 1e9 / (365.25 * 24 * 3600)
        rows.append({
            "hypothetical_distinct_table_keys": M,
            "table_keys_log2": math.log2(M),
            "fraction_of_distinct_zero_pair_keys": fraction,
            "maximum_success_probability_after_exhaustive_unique_queries":
                max_success,
            "reaches_95pct_one_target_success_in_finite_support_model":
                possible,
            "ideal_unique_query_pairs_for_95pct_success": unique_queries,
            "ideal_unique_query_pairs_for_95pct_success_log2":
                math.log2(unique_queries) if unique_queries else None,
            "ideal_with_replacement_query_samples_for_95pct_success":
                replacement_queries,
            "ideal_cold_table_plus_unique_query_pair_samples_log2":
                math.log2(M + unique_queries) if unique_queries else None,
            "conditional_field_api_unit_work_log2_if_each_call_one_unit":
                unit_work_log2,
            "conditional_field_api_mul_time_equivalents_log2":
                field_mul_time_work_log2,
            "conditional_sampled_stage_python_mul_time_equivalents_log2":
                sampled_stage_mul_time_work_log2,
            "conditional_one_core_python_years_at_measured_unique_schedule_rate":
                python_years,
            "x_key_bits_only_memory_bytes_lower_bound": M * 11,
            "illustrative_32byte_packed_entry_bytes": M * 32,
        })
    report = {
        "kind": "n83_exact_knownlog_base_finite_support_one_target_quotient_table_screen",
        "scope": "exact base and bounded measured pair costs; 95% work remains heuristic; no n83 relation or DLP",
        "proposal_id": "Q1045",
        "candidate_id": None,
        "curve_id": base["curve_id"],
        "curve_identity_record": base["curve_identity_record"],
        "isogeny": "none",
        "actual_usable_points_B_before_folding": B,
        "actual_signed_frobenius_columns": K,
        "initially_known_log_columns": record["initially_known_log_columns"],
        "unknown_log_columns": record["unknown_log_columns"],
        "factor_base_enumerated_set_sha256": record["enumerated_set_sha256"],
        "canonical_log_sha256": record["canonical_log_sha256"],
        "unordered_pair_domain": pair_domain,
        "signed_frobenius_zero_pair_key_cap_before_accidental_collisions": key_cap,
        "heuristic_mean_four_point_multiset_relations_for_one_target":
            mean_relations,
        "heuristic_full_table_maximum_one_target_success_probability":
            success(mean_relations, 1, 1),
        "target_match_probability_used_in_proxy": TARGET_SUCCESS,
        "minimum_distinct_table_keys_for_95pct_under_model": minimum_keys,
        "measured_n83_unique_schedule_xkey_table_ns_per_sample": table_ns,
        "measured_n83_unique_schedule_xkey_query_ns_per_sample": query_ns,
        "measured_n83_unique_schedule_samples_per_phase":
            scheduled["samples_per_phase"],
        "measured_n83_unique_schedule_timing_repetitions":
            scheduled["timing_repetitions"],
        "measured_n83_unique_schedule_table_ns_per_sample_each":
            scheduled["table_ns_per_sample_each"],
        "measured_n83_unique_schedule_query_ns_per_sample_each":
            scheduled["query_ns_per_sample_each"],
        "measured_n83_direct_xkey_table_field_api_calls_per_sample": table_calls,
        "measured_n83_direct_xkey_query_field_api_calls_per_sample": query_calls,
        "measured_n83_field_mul_ns_per_call": mul_ns,
        "measured_n83_field_api_time_ratios_to_mul": weights,
        "measured_n83_stage_table_samples": perf["table_samples"],
        "measured_n83_stage_query_samples": perf["query_samples"],
        "measured_n83_stage_key_hits": perf["query_table_key_hits"],
        "verified_n53_complete_control_candidate_id": n53["candidate_id"],
        "verified_n53_complete_control_scalar": n53["recovered_scalar"],
        "tradeoff_rows": rows,
        "model": "A finite base has B(B+1)/2 unordered query pairs and at most D zero-pair quotient keys. Under a random-base heuristic, proper four-point multisets for a fixed target are Poisson with mean C(B+3,4)/r. Each has six pair partitions. Index fraction f and unique-query fraction t give success 1-exp(-mu*(1-(1-f*t)^6)). Repeated queries cannot make t exceed one.",
        "assumptions_and_limits": [
            "The n83 base and its logs are exact; no ordinary n83 target relation has been found.",
            "The four-point count and Poisson law are heuristics for this deterministic base, not measured representability.",
            "The six pair partitions are correlated, and different relations may be correlated.",
            "The key cap assumes only forced signed-Frobenius equivalences; accidental collisions can reduce it.",
            "The bounded affine schedules visit unique table descriptors and query pairs; only 32768 entries per phase were timed, so full-domain throughput is unmeasured.",
            "The affine schedules are deterministic permutations, not random samples; uniform placement of this fixed target's relation partitions within them is a heuristic.",
            "Table build charges one sample per distinct key; duplicate sampling, large-table hash and memory effects, and base construction are omitted.",
            "Eleven bytes per x key excludes witnesses and hash overhead; 32 bytes per entry is illustrative.",
            "The field API unit model assigns one unit to add, mul, sqr, and inv; it is neither a multiplication equivalent nor a complete work bound.",
            "Multiplication-time equivalents divide measured Python stage wall time or weighted field API time by the measured local Python field-mul call time. They are implementation-specific proxies, not a mathematical field-operation count.",
            "The paired n83 direct-x-key benchmark verified key equivalence on 32768 samples per phase. The chosen schedule benchmark also covers 32768 samples per phase and no large table.",
        ],
        "measured_n83_relation_yield": None,
        "verified_n83_dlp": False,
        "complete_work_log2": None,
        "base_receipt_sha256": sha(BASE),
        "stage_benchmark_sha256": sha(PERF),
        "batch_benchmark_sha256": sha(BATCH_PERF),
        "unique_schedule_benchmark_sha256": sha(SCHEDULE_PERF),
        "field_calibration_sha256": sha(FIELD_PERF),
        "n53_complete_control_sha256": sha(N53),
        "source_sha256": sha(Path(__file__)),
    }
    OUTPUT.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({
        "curve_id": report["curve_id"],
        "mean_four_point_relations": mean_relations,
        "minimum_keys_for_95pct": minimum_keys,
        "rows": [{"M_log2": row["table_keys_log2"],
                  "max_success": row[
                      "maximum_success_probability_after_exhaustive_unique_queries"],
                  "unique_query_log2": row[
                      "ideal_unique_query_pairs_for_95pct_success_log2"],
                  "unit_api_work_log2": row[
                      "conditional_field_api_unit_work_log2_if_each_call_one_unit"]}
                 for row in rows],
    }))


if __name__ == "__main__":
    main()

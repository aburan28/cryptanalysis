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
NATIVE_PERF = HERE / "runs" / "n83_native_pair_perf.json"
EXACT_TABLE_PERF = HERE / "runs" / "n83_native_exact_table_perf.json"
N53 = HERE / "runs" / "n53_knownlog_one_target.json"
N83_RHO = (HERE.parent / "ecc2k130-quotient-pair-probe-20260926" /
           "runs" / "n83_public_target_rho_solved.json")
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
    native = json.loads(NATIVE_PERF.read_text())
    exact_table = json.loads(EXACT_TABLE_PERF.read_text())
    n53 = json.loads(N53.read_text())
    rho = json.loads(N83_RHO.read_text())
    assert base["curve_id"] == perf["curve_id"] == "EC1N83Ckb1h876c2921cb64"
    assert n53["verified_single_target_dlp"] is True
    assert rho["curve_id"] == base["curve_id"]
    assert rho["independent_scalar_replay_passed"] is True
    assert rho["public_target"] == exact_table["public_target"]
    record = base["factor_base"]
    order = base["curve_identity_record"]["curve"]["subgroup_order"]
    B = record["actual_usable_points_B_before_folding"]
    K = record["signed_frobenius_columns"]
    L = record["signed_frobenius_orbit_size"]
    assert B == 4000102 and K == 24097 and L == 166
    assert record["unknown_log_columns"] == 0
    assert batch["runs"][1]["curve_id"] == base["curve_id"]
    assert schedule["runs"][1]["curve_id"] == base["curve_id"]
    assert native["curve_id"] == base["curve_id"]
    assert native["factor_base"]["enumerated_set_sha256"] == record["enumerated_set_sha256"]
    assert exact_table["curve_id"] == base["curve_id"]
    assert exact_table["factor_base"]["enumerated_set_sha256"] == record["enumerated_set_sha256"]
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
    native_table_ns = native["table_ns_per_sample_median"]
    native_query_ns = native["query_ns_per_sample_median"]
    native_batch = native["chosen_batch_size_by_query_median"]
    largest_exact = exact_table["runs"][-1]
    exact_table_ns = largest_exact["table_ns_per_descriptor"]
    exact_query_ns = largest_exact[
        "query_ns_per_pair_including_exact_lookup"]
    rows = []
    for M in (1 << 20, 1 << 24, 1 << 27, 1 << 28, 1 << 30,
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
        native_days = None
        native_exact_lookup_proxy_days = None
        native_field_mul_calls_log2 = None
        native_field_operation_calls_log2 = None
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
            native_days = (
                M * native_table_ns + unique_queries * native_query_ns
            ) / 1e9 / (24 * 3600)
            native_exact_lookup_proxy_days = (
                M * exact_table_ns + unique_queries * exact_query_ns
            ) / 1e9 / (24 * 3600)
            native_field_mul_calls_log2 = math.log2(
                5 * M + 10 * unique_queries +
                8 * (math.ceil(M / native_batch) +
                     2 * math.ceil(unique_queries / native_batch)))
            # Each batch inversion uses 8 multiplications and 82
            # squarings in the native Itoh-Tsujii chain. The pair additions
            # use 5/10 multiplies, 1/2 squares, and 7/15 field XORs.
            inversions = (math.ceil(M / native_batch) +
                          2 * math.ceil(unique_queries / native_batch))
            native_field_operation_calls_log2 = math.log2(
                13 * M + 27 * unique_queries + 90 * inversions)
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
            "conditional_one_core_native_pair_stage_days_at_bounded_rate":
                native_days,
            "conditional_one_core_native_exact_lookup_days_at_2pow28_table_rate":
                native_exact_lookup_proxy_days,
            "conditional_native_batch_field_mul_calls_log2":
                native_field_mul_calls_log2,
            "conditional_native_batch_field_add_mul_sqr_calls_log2":
                native_field_operation_calls_log2,
            "x_key_bits_only_memory_bytes_lower_bound": M * 11,
            "illustrative_12byte_exact_open_address_table_bytes_at_70pct_load":
                (M * 10 // 7 + 1024) * 12,
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
        "measured_n83_native_table_ns_per_sample": native_table_ns,
        "measured_n83_native_query_ns_per_sample": native_query_ns,
        "measured_n83_native_batch_size": native_batch,
        "measured_n83_native_samples_per_phase": native["samples_per_phase"],
        "measured_n83_native_timing_repetitions": native["timing_repetitions"],
        "measured_n83_exact_table_largest_descriptors":
            exact_table["runs"][-1]["table_descriptors"],
        "measured_n83_exact_table_largest_memory_bytes":
            exact_table["runs"][-1]["table_bytes"],
        "measured_n83_exact_table_largest_query_ns_per_pair_including_lookup":
            exact_query_ns,
        "measured_n83_exact_table_largest_table_ns_per_descriptor":
            exact_table_ns,
        "measured_n83_exact_table_largest_key_hits":
            exact_table["runs"][-1]["key_hits"],
        "measured_n83_stage_table_samples": perf["table_samples"],
        "measured_n83_stage_query_samples": perf["query_samples"],
        "measured_n83_stage_key_hits": perf["query_table_key_hits"],
        "verified_n53_complete_control_candidate_id": n53["candidate_id"],
        "verified_n53_complete_control_scalar": n53["recovered_scalar"],
        "n83_same_target_rho_reference": {
            "recovered_scalar": rho["recovered_scalar"],
            "walk_iterations": rho["rho_walk_iterations"],
            "walk_iterations_log2": rho["rho_walk_iterations_log2"],
            "independent_scalar_replay_passed": True,
            "receipt_sha256": sha(N83_RHO),
        },
        "tradeoff_rows": rows,
        "model": "A finite base has B(B+1)/2 unordered query pairs and at most D zero-pair quotient keys. Under a random-base heuristic, proper four-point multisets for a fixed target are Poisson with mean C(B+3,4)/r. Each has six pair partitions. Index fraction f and unique-query fraction t give success 1-exp(-mu*(1-(1-f*t)^6)). Repeated queries cannot make t exceed one.",
        "assumptions_and_limits": [
            "The n83 base and its logs are exact; no ordinary n83 target relation has been found.",
            "The four-point count and Poisson law are heuristics for this deterministic base, not measured representability.",
            "The six pair partitions are correlated, and different relations may be correlated.",
            "The key cap assumes only forced signed-Frobenius equivalences; accidental collisions can reduce it.",
            "The bounded affine schedules visit unique table descriptors and query pairs; only 32768 entries per phase were timed, so full-domain throughput is unmeasured.",
            "The affine schedules are deterministic permutations, not random samples; uniform placement of this fixed target's relation partitions within them is a heuristic.",
            "Table build charges one sample per distinct key. The Python and native arithmetic-only stage rates omit duplicate sampling, hash lookup, large-table memory effects, and base construction.",
            "Eleven bytes per x key excludes witnesses and hash overhead; 32 bytes per entry is illustrative.",
            "The field API unit model assigns one unit to add, mul, sqr, and inv; it is neither a multiplication equivalent nor a complete work bound.",
            "Multiplication-time equivalents divide measured Python stage wall time or weighted field API time by the measured local Python field-mul call time. They are implementation-specific proxies, not a mathematical field-operation count.",
            "Native field call counts use 5/10 multiplications, 1/2 squarings, and 7/15 field XORs per batched table/target pair, plus 8 multiplications and 82 squarings per batch inversion. Exceptional pairs are ignored. Counts exclude x-keying, hashing, lookup, base setup, and answer verification.",
            "Native one-core days extrapolate a one-million-sample arithmetic-and-key stage without a materialized large table or lookup. They are not a demonstrated run time for a complete solve.",
            "The native exact-lookup day proxy uses measured 2^28-key table build and lookup rates for a hypothetical larger table; it excludes allocation, base setup, replay, verification, and any slowdown at larger memory sizes.",
            "The exact 12-byte-slot hash table and lookup have only been measured through 2^28 distinct n83 keys; capacity, insertion, and lookup at 2^33 keys are unmeasured.",
            "The paired n83 direct-x-key benchmark verified key equivalence on 32768 samples per phase. The chosen schedule benchmark also covers 32768 samples per phase and no large table.",
        ],
        "measured_n83_relation_yield": None,
        "verified_n83_quotient_table_dlp": False,
        "complete_work_log2": None,
        "base_receipt_sha256": sha(BASE),
        "stage_benchmark_sha256": sha(PERF),
        "batch_benchmark_sha256": sha(BATCH_PERF),
        "unique_schedule_benchmark_sha256": sha(SCHEDULE_PERF),
        "field_calibration_sha256": sha(FIELD_PERF),
        "native_benchmark_sha256": sha(NATIVE_PERF),
        "exact_table_benchmark_sha256": sha(EXACT_TABLE_PERF),
        "n53_complete_control_sha256": sha(N53),
        "n83_rho_reference_sha256": sha(N83_RHO),
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

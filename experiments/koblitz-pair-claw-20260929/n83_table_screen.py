#!/usr/bin/env python3
"""Conditional n=83 memory/work tradeoff for the quotient pair table."""

import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE_SCREEN = HERE / "n83_conditional_screen.json"
BASE_RECEIPT = HERE / "runs" / "n83_weight5_orbit_base.json"
FULL_BENCH = HERE / "runs" / "n83_full_base_quotient_pair_perf.json"
N53_RELATION = HERE / "runs" / "n53_weight3_quotient_table_probe.json"
STEP_BENCH = HERE / "runs" / "n53_n83_quotient_step_perf.json"
OUTPUT = HERE / "n83_conditional_table_screen.json"
FIELD_OPERATION_GATE_LOG2 = 61
TARGET_SUCCESS_PROBABILITY = 0.95


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    base = json.loads(BASE_SCREEN.read_text())
    enumerated = json.loads(BASE_RECEIPT.read_text())
    full_bench = json.loads(FULL_BENCH.read_text())
    n53 = json.loads(N53_RELATION.read_text())
    bench = json.loads(STEP_BENCH.read_text())
    assert base["curve_id"] == "EC1N83Ckb1h876c2921cb64"
    assert enumerated["curve_id"] == full_bench["curve_id"] == base["curve_id"]
    assert n53["ordinary_query"]["status"] == "verified_four_point_relation"
    n83_bench = next(row for row in bench["runs"]
                     if row["curve_id"] == base["curve_id"])
    order = base["curve_identity_record"]["curve"]["subgroup_order"]
    B = enumerated["factor_base"]["actual_usable_points_B_before_folding"]
    columns = enumerated["factor_base"]["signed_frobenius_columns"]
    assert B == base["actual_usable_points_B_before_folding"] == full_bench["factor_base"]["actual_usable_points_B_before_folding"]
    assert columns == base["effective_columns"] == 24097
    orbit_size = 166
    pair_domain = math.comb(B + 1, 2)
    approximate_key_cap = pair_domain // orbit_size
    target_multiplier = -math.log(1 - TARGET_SUCCESS_PROBABILITY)
    ideal_rank_queries = columns / TARGET_SUCCESS_PROBABILITY
    table_calls = full_bench["table_field_api_calls_per_sample"]
    query_calls = full_bench["query_field_api_calls_per_sample"]
    table_noninversion_calls = sum(table_calls[name]
                                   for name in ("add", "mul", "sqr"))
    query_noninversion_calls = sum(query_calls[name]
                                   for name in ("add", "mul", "sqr"))
    rows = []
    for table_keys in (1 << 27, 1 << 30, 1 << 33, approximate_key_cap):
        if table_keys > approximate_key_cap:
            continue
        ideal_query_samples = target_multiplier * order / (orbit_size * table_keys)
        all_query_samples = (ideal_rank_queries + 1) * ideal_query_samples
        total_samples = table_keys + all_query_samples
        unit_api_work = (table_keys * (table_noninversion_calls + table_calls["inv"]) +
                         all_query_samples * (query_noninversion_calls + query_calls["inv"]))
        inversion_weight_limit = (
            2 ** FIELD_OPERATION_GATE_LOG2 -
            table_keys * table_noninversion_calls -
            all_query_samples * query_noninversion_calls
        ) / (table_keys * table_calls["inv"] +
             all_query_samples * query_calls["inv"])
        conditional_python_years = (
            table_keys * full_bench["table_ns_per_sample"] +
            (ideal_rank_queries + 1) * ideal_query_samples *
            full_bench["query_ns_per_sample"]
        ) / 1e9 / (365.25 * 24 * 3600)
        rows.append({
            "hypothetical_distinct_zero_pair_orbit_keys": table_keys,
            "hypothetical_table_key_count_log2": math.log2(table_keys),
            "ideal_query_samples_per_target_for_95pct_match_probability": ideal_query_samples,
            "ideal_cold_table_plus_rank_rows_plus_one_target_pair_samples_log2": math.log2(total_samples),
            "field_operations_per_sample_at_2pow61_gate_ignoring_other_work":
                2 ** FIELD_OPERATION_GATE_LOG2 / total_samples,
            "conditional_field_api_unit_work_log2_if_inversion_one_unit": math.log2(unit_api_work),
            "maximum_inversion_weight_if_add_mul_square_each_one_unit_and_other_work_zero":
                inversion_weight_limit,
            "key_bits_only_memory_bytes_lower_bound": table_keys * 21,
            "illustrative_32byte_packed_entry_bytes": table_keys * 32,
            "conditional_one_core_python_years_at_measured_full_base_stage_rate":
                conditional_python_years,
        })
    report = {
        "kind": "n83_exact_base_conditional_quotient_table_memory_work_screen",
        "scope": "exact enumerated n83 base and measured bounded pair-sample cost; conditional cold-work tradeoff; no n83 relation, base logs, or DLP",
        "candidate_id": None, "curve_id": base["curve_id"],
        "curve_identity_record": base["curve_identity_record"],
        "isogeny": "none",
        "actual_usable_points_B_before_folding": B,
        "actual_signed_frobenius_columns": columns,
        "factor_base_enumerated_set_sha256": enumerated["factor_base"]["enumerated_set_sha256"],
        "pair_multisets": str(pair_domain),
        "full_signed_frobenius_orbit_size": orbit_size,
        "approximate_distinct_zero_pair_orbit_key_cap": approximate_key_cap,
        "target_match_probability_used_in_proxy": TARGET_SUCCESS_PROBABILITY,
        "conditional_ideal_rank_queries": ideal_rank_queries,
        "paired_n83_sample_base_B": n83_bench["stage_base_B_before_folding"],
        "paired_n83_quotient_step_median_ns": n83_bench["quotient_median_ns_per_step"],
        "paired_n83_quotient_to_direct_step_wall_ratio": n83_bench[
            "quotient_to_direct_step_wall_ratio"],
        "measured_n83_full_base_table_ns_per_sample": full_bench["table_ns_per_sample"],
        "measured_n83_full_base_query_ns_per_sample": full_bench["query_ns_per_sample"],
        "measured_n83_full_base_stage_table_samples": full_bench["table_samples"],
        "measured_n83_full_base_stage_query_samples": full_bench["query_samples"],
        "measured_n83_full_base_stage_key_hits": full_bench["query_table_key_hits"],
        "measured_n83_full_base_table_field_api_calls_per_sample": table_calls,
        "measured_n83_full_base_query_field_api_calls_per_sample": query_calls,
        "measured_n53_full_base_relation": {
            "curve_id": n53["curve_id"],
            "actual_B": n53["factor_base"]["actual_usable_points_B_before_folding"],
            "columns": n53["factor_base"]["signed_frobenius_columns"],
            "table_samples": n53["ordinary_query"]["table_samples"],
            "distinct_table_keys": n53["ordinary_query"]["table_distinct_keys"],
            "query_samples_to_verified_relation": n53["ordinary_query"]["query_samples"]},
        "tradeoff_rows": rows,
        "model": "M reusable distinct zero-pair quotient keys; each independent one-pair query matches with probability approximately 166*M/r; -ln(0.05) times the reciprocal gives a 95% per-target query proxy; K/0.95 rank queries plus one target are charged; table M is charged once",
        "assumptions_and_limits": [
            "The n83 factor base of 4,000,102 points and 24,097 orbit columns is independently verified, but its 24,097 base logs and target DLP are unknown.",
            "The approximation pair-domain/166 for maximum distinct zero-pair keys ignores short orbits and group-sum duplicates.",
            "Table construction is charged one pair sample per distinct key; duplicate sampling and any external sort or hash-build overhead are ignored.",
            "The 95% formula assumes independent uniform one-pair keys and a target whose valid four-point relation exists; fixed-target absence and correlated keys can defeat it.",
            "Every successful ordinary relation is assumed to add rank. Failed queries, rank dependencies, base and matrix work, and actual field-operation conversion are unmeasured.",
            "A key-only memory lower bound of 21 bytes excludes pair witnesses, hash-table overhead, and allocator overhead; 32 bytes is only an illustrative packed entry size.",
            "The full-base n83 pair-sample timing covers 100,000 table and 100,000 query samples; cache, storage, and concurrency behavior at the projected table sizes are unmeasured.",
            "The unit-call model counts each field addition, multiplication, squaring, and inversion as one unit and excludes nested Frobenius calls; it is an optimistic diagnostic, not a calibrated field-operation equivalence.",
        ],
        "measured_n83_relation_yield": None,
        "verified_n83_dlp": False,
        "complete_work_log2": None,
        "base_screen_sha256": sha(BASE_SCREEN),
        "base_receipt_sha256": sha(BASE_RECEIPT),
        "full_base_benchmark_sha256": sha(FULL_BENCH),
        "n53_relation_receipt_sha256": sha(N53_RELATION),
        "step_benchmark_sha256": sha(STEP_BENCH),
        "source_sha256": sha(Path(__file__)),
    }
    OUTPUT.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"curve_id": report["curve_id"],
                      "rows": [{"M_log2": row["hypothetical_table_key_count_log2"],
                                "total_pair_samples_log2": row[
                                    "ideal_cold_table_plus_rank_rows_plus_one_target_pair_samples_log2"],
                                "ops_per_sample_gate": row[
                                    "field_operations_per_sample_at_2pow61_gate_ignoring_other_work"]}
                               for row in rows]}))


if __name__ == "__main__":
    main()

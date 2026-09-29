#!/usr/bin/env python3
"""Conditional one-target n=83 work screen for a verified known-log base."""

import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE / "runs" / "n83_knownlog_orbit_base.json"
PERF = HERE / "runs" / "n83_knownlog_pair_perf.json"
N53 = HERE / "runs" / "n53_knownlog_one_target.json"
OUTPUT = HERE / "n83_knownlog_conditional_screen.json"
GATE_LOG2 = 61
TARGET_SUCCESS_PROBABILITY = 0.95


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    base = json.loads(BASE.read_text())
    perf = json.loads(PERF.read_text())
    n53 = json.loads(N53.read_text())
    assert base["curve_id"] == perf["curve_id"] == "EC1N83Ckb1h876c2921cb64"
    assert n53["verified_single_target_dlp"] is True
    record = base["factor_base"]
    order = base["curve_identity_record"]["curve"]["subgroup_order"]
    B = record["actual_usable_points_B_before_folding"]
    columns = record["signed_frobenius_columns"]
    orbit_size = record["signed_frobenius_orbit_size"]
    assert B == 4000102 and columns == 24097 and orbit_size == 166
    assert record["unknown_log_columns"] == 0
    pair_domain = math.comb(B + 1, 2)
    approximate_key_cap = pair_domain // orbit_size
    multiplier = -math.log(1 - TARGET_SUCCESS_PROBABILITY)
    table_calls = perf["table_field_api_calls_per_sample"]
    query_calls = perf["query_field_api_calls_per_sample"]
    table_noninversion = sum(table_calls[name] for name in ("add", "mul", "sqr"))
    query_noninversion = sum(query_calls[name] for name in ("add", "mul", "sqr"))
    rows = []
    for table_keys in (1 << 20, 1 << 24, 1 << 27, 1 << 30,
                       approximate_key_cap):
        if table_keys > approximate_key_cap:
            continue
        query_samples = multiplier * order / (orbit_size * table_keys)
        total_samples = table_keys + query_samples
        table_unit_calls = table_noninversion + table_calls["inv"]
        query_unit_calls = query_noninversion + query_calls["inv"]
        api_unit_work = table_keys * table_unit_calls + query_samples * query_unit_calls
        inversion_weight_limit = (
            2 ** GATE_LOG2 - table_keys * table_noninversion -
            query_samples * query_noninversion
        ) / (table_keys * table_calls["inv"] +
             query_samples * query_calls["inv"])
        python_years = (table_keys * perf["table_ns_per_sample"] +
                        query_samples * perf["query_ns_per_sample"]) / 1e9 / (
                            365.25 * 24 * 3600)
        rows.append({
            "hypothetical_distinct_table_keys": table_keys,
            "table_keys_log2": math.log2(table_keys),
            "ideal_query_samples_for_95pct_match": query_samples,
            "ideal_cold_table_plus_one_target_pair_samples_log2": math.log2(total_samples),
            "field_operations_per_pair_sample_at_2pow61_gate_ignoring_other_work":
                2 ** GATE_LOG2 / total_samples,
            "conditional_field_api_unit_work_log2_if_inversion_one_unit":
                math.log2(api_unit_work),
            "maximum_inversion_weight_if_add_mul_square_each_one_unit_and_other_work_zero":
                inversion_weight_limit,
            "key_bits_only_memory_bytes_lower_bound": table_keys * 21,
            "illustrative_32byte_packed_entry_bytes": table_keys * 32,
            "conditional_one_core_python_years_at_measured_full_base_stage_rate":
                python_years,
        })
    report = {
        "kind": "n83_exact_knownlog_base_conditional_one_target_quotient_table_work_screen",
        "scope": "exact known-log base and bounded measured pair costs; conditional target relation probability and complete DLP work",
        "candidate_id": None,
        "curve_id": base["curve_id"],
        "curve_identity_record": base["curve_identity_record"],
        "isogeny": "none",
        "actual_usable_points_B_before_folding": B,
        "actual_signed_frobenius_columns": columns,
        "initially_known_log_columns": record["initially_known_log_columns"],
        "unknown_log_columns": record["unknown_log_columns"],
        "factor_base_enumerated_set_sha256": record["enumerated_set_sha256"],
        "canonical_log_sha256": record["canonical_log_sha256"],
        "pair_multisets": str(pair_domain),
        "approximate_distinct_zero_pair_orbit_key_cap": approximate_key_cap,
        "uniform_independent_sum_expected_four_point_multisets":
            math.comb(B + 3, 4) / order,
        "target_match_probability_used_in_proxy": TARGET_SUCCESS_PROBABILITY,
        "measured_n83_full_base_table_ns_per_sample": perf["table_ns_per_sample"],
        "measured_n83_full_base_query_ns_per_sample": perf["query_ns_per_sample"],
        "measured_n83_full_base_table_field_api_calls_per_sample": table_calls,
        "measured_n83_full_base_query_field_api_calls_per_sample": query_calls,
        "measured_n83_stage_table_samples": perf["table_samples"],
        "measured_n83_stage_query_samples": perf["query_samples"],
        "measured_n83_stage_key_hits": perf["query_table_key_hits"],
        "verified_n53_complete_control_candidate_id": n53["candidate_id"],
        "verified_n53_complete_control_scalar": n53["recovered_scalar"],
        "tradeoff_rows": rows,
        "model": "M reusable distinct zero-pair quotient keys; each independent target-complement pair matches with probability approximately 166*M/r; -ln(0.05) times the reciprocal gives the 95% query proxy; all base-point logs are known, so no rank-collection or final matrix stage is needed",
        "assumptions_and_limits": [
            "The n83 known-log factor base is exact and independently verified; no ordinary n83 target relation has been found.",
            "The fixed public n83 target may have no four-point representation in this base; the uniform model gives an expectation, not a certificate of existence.",
            "The quotient-key hit model assumes independent uniform target-complement pair outputs and a table of M distinct keys. The approximate pair-domain/166 cap ignores short orbits and group-sum duplicates.",
            "Table build is charged one pair sample per distinct key; duplicate sampling, external sorting, hash-table overhead, and base construction operations are omitted from the ideal pair-sample count.",
            "Twenty-one bytes per key excludes pair witnesses and hash overhead. The 32-byte entry size is illustrative, not measured at large tables.",
            "The field API unit model counts each addition, multiplication, squaring, and inversion as one unit. Inversion cost in field-operation equivalents is uncalibrated.",
            "The bounded n83 full-base timing covers only 100,000 table and 100,000 target-side pair samples; large-table cache, memory, concurrency, and wall time are unmeasured.",
        ],
        "measured_n83_relation_yield": None,
        "verified_n83_dlp": False,
        "complete_work_log2": None,
        "base_receipt_sha256": sha(BASE),
        "stage_benchmark_sha256": sha(PERF),
        "n53_complete_control_sha256": sha(N53),
        "source_sha256": sha(Path(__file__)),
    }
    OUTPUT.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"curve_id": report["curve_id"],
                      "unknown_log_columns": 0,
                      "rows": [{"M_log2": row["table_keys_log2"],
                                "pair_samples_log2": row[
                                    "ideal_cold_table_plus_one_target_pair_samples_log2"],
                                "unit_api_work_log2": row[
                                    "conditional_field_api_unit_work_log2_if_inversion_one_unit"],
                                "key_only_gib": row[
                                    "key_bits_only_memory_bytes_lower_bound"] / 2 ** 30}
                               for row in rows]}))


if __name__ == "__main__":
    main()

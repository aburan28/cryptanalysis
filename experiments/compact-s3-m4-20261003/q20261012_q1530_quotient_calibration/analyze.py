#!/usr/bin/env python3
"""Calibrate quotient-pair match law and reprice the 84 frozen N131 cells."""
import hashlib
import json
import math
from fractions import Fraction
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_source(protocol: dict, name: str) -> dict:
    source = protocol["source_records"][name]
    path = PARENT / source["relative_path"]
    assert sha(path) == source["sha256"]
    return json.loads(path.read_text())


def log2q(x: Fraction) -> float:
    return math.log2(x.numerator) - math.log2(x.denominator)


def wilson(k: int, n: int) -> list[float]:
    z = 1.959963984540054
    p = k / n
    d = 1 + z*z/n
    mid = (p + z*z/(2*n))/d
    span = z*math.sqrt(p*(1-p)/n + z*z/(4*n*n))/d
    return [mid-span, mid+span]


def main() -> None:
    protocol = json.loads((HERE / "protocol.json").read_text())
    assert protocol["proposal_id"] == "Q1530"
    full_p = read_source(protocol, "n53_full_protocol")
    full = read_source(protocol, "n53_full_measurement")
    full_replay = read_source(protocol, "n53_full_replay")
    ordinary_p = read_source(protocol, "n53_ordinary_protocol")
    ordinary = read_source(protocol, "n53_ordinary_measurement")
    ordinary_a = read_source(protocol, "n53_ordinary_analysis")
    ordinary_replay = read_source(protocol, "n53_ordinary_replay")
    q1526 = read_source(protocol, "n131_q1526_sweep")
    q1529 = read_source(protocol, "n83_q1529_measurement")
    assert full_p["curve_id"] == ordinary_p["curve_id"] == protocol["curve_ids"]["n53"]
    assert full_p["factor_base_actual_B"] == ordinary_p["factor_base_actual_B"] == 24062
    assert full_p["factor_base_folded_columns_K"] == ordinary_p["factor_base_folded_columns_K"] == 227
    assert full_p["factor_base_enumerated_set_sha256"] == ordinary_p["factor_base_enumerated_set_sha256"]
    assert full["status"] == ordinary["status"] == "completed_query_cap"
    assert full_replay and ordinary_replay
    assert q1529["curve_id"] == protocol["curve_ids"]["n83"]
    assert q1526["curve_id"] == protocol["curve_ids"]["n131"]

    b53, r53 = full_p["factor_base_actual_B"], int(full_p["subgroup_order"])
    p_full = Fraction(b53*b53, 2*r53)
    full_queries = full["query_samples_processed"]
    full_positions = len({row[0] for row in full["matches"]})
    assert full_queries == 30000000 and full_positions == 399
    assert len(full["matches"]) == 400
    full_keys = full["table_distinct_keys"]
    partial_keys = ordinary["table_distinct_keys"]
    assert full_keys == 2730335 and partial_keys == 1418520
    ordinary_queries = ordinary_a["query_samples"]
    ordinary_positions = ordinary_a["matched_query_positions"]
    assert ordinary_queries == 1500000 and ordinary_positions == 11
    assert ordinary_a["verified_occurrences"] == 15
    calibrations = []
    for label, queries, matched, keys, workload in (
        ("generator_setup_full_table", full_queries, full_positions, full_keys, None),
        ("ordinary_random_2m_table", ordinary_queries, ordinary_positions,
         partial_keys, ordinary_p["workload_id"]),
    ):
        coverage = Fraction(keys, full_keys)
        predicted_p = p_full * coverage
        expected = predicted_p * queries
        observed_p = Fraction(matched, queries)
        ci = wilson(matched, queries)
        calibrations.append({
            "label": label, "workload_id": workload,
            "queries": queries, "matched_query_positions": matched,
            "distinct_table_keys": keys, "full_distinct_table_keys": full_keys,
            "distinct_key_coverage": float(coverage),
            "descriptor_fraction": (1.0 if label.startswith("generator") else
                                    ordinary["table_samples"] /
                                    full["table_states_generated"]),
            "predicted_match_probability_conditional": float(predicted_p),
            "predicted_matched_positions_conditional": float(expected),
            "observed_match_probability": float(observed_p),
            "observed_over_predicted": float(observed_p / predicted_p),
            "wilson95": ci,
            "prediction_within_wilson95": ci[0] <= float(predicted_p) <= ci[1],
        })

    r131 = int(q1526["subgroup_order_r"])
    rows = []
    for old in q1526["cells"]:
        b, k, j = old["B"], old["K"], old["table_fraction_binary_exponent"]
        table = Fraction(131*k*k, 2**j)
        lifted_queries = Fraction(k*2*r131*2**j, b*b)
        old_cost = table + 2*lifted_queries
        native_cost = table + Fraction(263, 262)*lifted_queries
        old_log = log2q(old_cost)
        assert abs(old_log - old["counted_pair_add_attempts_log2"]) < 1e-9
        matrix = 4*k*k
        assert abs(math.log2(matrix) - old["matrix_proxy_modular_events_log2"]) < 1e-9
        rows.append({
            "weight_bound": old["weight_bound"], "base_status": old["base_status"],
            "B": b, "K": k, "table_fraction": old["table_fraction"],
            "table_fraction_binary_exponent": j,
            "table_states_log2": log2q(table),
            "lifted_queries_log2": log2q(lifted_queries),
            "q1526_pair_additions_log2": old_log,
            "quotient_reuse_pair_additions_log2": log2q(native_cost),
            "quotient_reuse_saving_bits": old_log - log2q(native_cost),
            "quotient_reuse_gap_above_2pow61_bits": log2q(native_cost) - 61,
            "matrix_proxy_modular_events_log2": math.log2(matrix),
            "matrix_proxy_below_2pow61": matrix < 2**61,
        })
    assert len(rows) == 84
    best = min((row for row in rows if row["matrix_proxy_below_2pow61"]),
               key=lambda row: row["quotient_reuse_pair_additions_log2"])
    w7_full = next(row for row in rows if row["weight_bound"] == 7 and
                   row["table_fraction_binary_exponent"] == 0)
    assert best is w7_full
    assert abs(best["quotient_reuse_pair_additions_log2"] -
               q1529["conditional_N131_W7_quotient_reuse_pair_additions_log2"]) < 1e-9
    output = {
        "proposal_id": "Q1530", "candidate_id": None, "run_id": None,
        "isogeny": "none", "stage_code": "PDP4mitm",
        "protocol_sha256": sha(HERE / "protocol.json"),
        "source_sha256": sha(Path(__file__)),
        "calibration": calibrations, "cells": rows,
        "best_matrix_eligible_cell": best,
        "all_matrix_eligible_pair_addition_cells_above_2pow61":
            all(row["quotient_reuse_gap_above_2pow61_bits"] > 0
                for row in rows if row["matrix_proxy_below_2pow61"]),
        "w8_full_matrix_proxy_above_2pow61":
            next(row for row in rows if row["weight_bound"] == 8 and
                 row["table_fraction_binary_exponent"] == 0)[
                     "matrix_proxy_modular_events_log2"] > 61,
        "complete_N131_solve_work_log2": None,
        "single_target_online_speedup": None,
        "challenge_dispatch_allowed": False,
    }
    (HERE / "analysis.json").write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
    print("Q1530", len(rows), "cells; best eligible", best["weight_bound"],
          best["table_fraction"], best["quotient_reuse_pair_additions_log2"])
    print("N53 calibration", [(x["label"], x["observed_over_predicted"])
                              for x in calibrations])


if __name__ == "__main__":
    main()

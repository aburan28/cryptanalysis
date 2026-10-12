#!/usr/bin/env python3
"""Finite, exact-rational sweep of the existing quotient pair-index model."""
from __future__ import annotations

import hashlib
import json
import math
from fractions import Fraction
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
SOURCES = {
    "q1506_weight_surface_sha256": PARENT / "q20261012_n131_weight_scan_surface/analysis.json",
    "q1462_pair_budget_sha256": PARENT / "q20261011_n131_pair_budget/analysis.json",
    "q1447_weight7_measurement_sha256": PARENT / "q20261011_weight7_screen/measurement.json",
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def log2(value: Fraction | int) -> float:
    value = Fraction(value)
    return math.log2(value.numerator) - math.log2(value.denominator)


def make_row(weight: int, b: int, k: int, r: int, n: int, j: int,
             base_status: str) -> dict:
    f = Fraction(1, 1 << j)
    states = Fraction(n * k * k) * f
    queries = Fraction(2 * k * r, b * b) / f
    actions = states + 2 * queries
    return {
        "weight_bound": weight,
        "base_status": base_status,
        "B": b,
        "K": k,
        "table_fraction": f"1/{1 << j}",
        "table_fraction_binary_exponent": j,
        "table_states_log2": log2(states),
        "optimistic_queries_log2": log2(queries),
        "query_addition_floor_log2": log2(2 * queries),
        "counted_pair_add_attempts_log2": log2(actions),
        "matrix_proxy_modular_events_log2": log2(4 * k * k),
    }


def build() -> dict:
    protocol = json.loads((HERE / "protocol.json").read_text())
    for name, path in SOURCES.items():
        assert digest(path) == protocol["source_records"][name], name
    surface = json.loads(SOURCES["q1506_weight_surface_sha256"].read_text())
    q1462 = json.loads(SOURCES["q1462_pair_budget_sha256"].read_text())
    q1447 = json.loads(SOURCES["q1447_weight7_measurement_sha256"].read_text())
    n = protocol["field_degree_n"]
    r = int(surface["subgroup_order_r"])
    assert n == q1447["field_degree_n"] == 131
    assert surface["curve_id"] == q1462["curve_id"] == q1447["curve_id"] == protocol["curve_id"]
    assert protocol["table_fractions_binary_exponents"] == list(range(21))
    assert [row["weight_bound"] for row in surface["rows"]] == protocol["weight_bounds"]

    rows = []
    summary = []
    intervals = []
    for source in surface["rows"]:
        w, b, k = source["weight_bound"], source["B"], source["K"]
        assert b == 2 * n * k
        cells = [make_row(w, b, k, r, n, j, source["base_status"])
                 for j in protocol["table_fractions_binary_exponents"]]
        rows.extend(cells)
        best = min(cells, key=lambda cell: cell["counted_pair_add_attempts_log2"])
        summary.append({
            "weight_bound": w,
            "base_status": source["base_status"],
            "B": b,
            "K": k,
            "enumerated_set_sha256": source["enumerated_set_sha256"],
            "best_tested_fraction": best["table_fraction"],
            "best_tested_pair_add_attempts_log2": best["counted_pair_add_attempts_log2"],
            "query_addition_floor_at_full_table_log2": cells[0]["query_addition_floor_log2"],
            "matrix_proxy_modular_events_log2": cells[0]["matrix_proxy_modular_events_log2"],
            "pair_add_gap_above_2pow61_bits": best["counted_pair_add_attempts_log2"] - 61,
            "matrix_proxy_gap_above_2pow61_bits": cells[0]["matrix_proxy_modular_events_log2"] - 61,
        })
        for endpoint in (source.get("conditional_K_interval_endpoints", []) if w == 7 else []):
            assert endpoint["B"] == 2 * n * endpoint["K"]
            intervals.append(make_row(w, endpoint["B"], endpoint["K"], r, n, 0,
                                      endpoint["base_status"]))

    w7 = next(item for item in summary if item["weight_bound"] == 7)
    assert abs(w7["best_tested_pair_add_attempts_log2"] -
               q1462["conditional_full_table_counted_pair_add_attempts_log2"]) < 1e-9
    matrix_eligible = [item for item in summary
                       if item["matrix_proxy_modular_events_log2"] < 61]
    return {
        "proposal_id": "Q1526",
        "candidate_id": None,
        "run_id": None,
        "curve_id": protocol["curve_id"],
        "isogeny": "none",
        "stage_code": "PDP4mitm",
        "analysis_kind": protocol["analysis_kind"],
        "protocol_sha256": digest(HERE / "protocol.json"),
        "source_sha256": digest(Path(__file__)),
        "subgroup_order_r": str(r),
        "cells": rows,
        "weight_summary": summary,
        "conditional_interval_endpoints_full_table": intervals,
        "best_tested_weight_with_matrix_proxy_below_2pow61": min(
            matrix_eligible, key=lambda item: item["best_tested_pair_add_attempts_log2"])["weight_bound"],
        "all_full_table_query_addition_floors_above_2pow61": all(
            item["query_addition_floor_at_full_table_log2"] > 61 for item in summary),
        "complete_n131_solve_work_log2": None,
        "challenge_dispatch_allowed": False,
    }


if __name__ == "__main__":
    path = HERE / "analysis.json"
    assert not path.exists(), "frozen analysis already exists"
    result = build()
    path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    for row in result["weight_summary"]:
        print(row["weight_bound"], row["best_tested_pair_add_attempts_log2"],
              row["matrix_proxy_modular_events_log2"])

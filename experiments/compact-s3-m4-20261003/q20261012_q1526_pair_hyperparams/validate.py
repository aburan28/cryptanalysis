#!/usr/bin/env python3
"""Recheck frozen Q1526 arithmetic against independent source records."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent


def read(path: Path):
    return json.loads(path.read_text())


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def close(actual: float, expected: float) -> None:
    assert math.isclose(actual, expected, rel_tol=0, abs_tol=1e-9), (actual, expected)


def main() -> None:
    p, a = read(HERE / "protocol.json"), read(HERE / "analysis.json")
    sources = {
        "q1506_weight_surface_sha256": PARENT / "q20261012_n131_weight_scan_surface/analysis.json",
        "q1462_pair_budget_sha256": PARENT / "q20261011_n131_pair_budget/analysis.json",
        "q1447_weight7_measurement_sha256": PARENT / "q20261011_weight7_screen/measurement.json",
    }
    for key, path in sources.items():
        assert sha(path) == p["source_records"][key]
    assert a["protocol_sha256"] == sha(HERE / "protocol.json")
    assert a["source_sha256"] == sha(HERE / "analyze.py")
    surface = read(sources["q1506_weight_surface_sha256"])
    budget = read(sources["q1462_pair_budget_sha256"])
    assert a["curve_id"] == surface["curve_id"] == budget["curve_id"] == p["curve_id"]
    assert a["candidate_id"] is a["run_id"] is None and a["isogeny"] == "none"
    assert a["complete_n131_solve_work_log2"] is None
    assert a["challenge_dispatch_allowed"] is False
    assert len(a["cells"]) == 4 * 21
    r = int(surface["subgroup_order_r"])
    assert int(a["subgroup_order_r"]) == r
    n = p["field_degree_n"]
    saw = set()
    for row in a["cells"]:
        w, j = row["weight_bound"], row["table_fraction_binary_exponent"]
        source = next(x for x in surface["rows"] if x["weight_bound"] == w)
        b, k = source["B"], source["K"]
        assert (w, j) not in saw
        saw.add((w, j))
        assert 0 <= j <= 20 and b == 2 * n * k
        assert (row["B"], row["K"], row["base_status"]) == (b, k, source["base_status"])
        assert row["table_fraction"] == f"1/{1 << j}"
        table = n * k * k / (1 << j)
        q = 2 * k * r * (1 << j) / (b * b)
        close(row["table_states_log2"], math.log2(table))
        close(row["optimistic_queries_log2"], math.log2(q))
        close(row["query_addition_floor_log2"], math.log2(2 * q))
        close(row["counted_pair_add_attempts_log2"], math.log2(table + 2 * q))
        close(row["matrix_proxy_modular_events_log2"], math.log2(4 * k * k))
    assert saw == {(w, j) for w in (5, 6, 7, 8) for j in range(21)}
    for summary in a["weight_summary"]:
        w = summary["weight_bound"]
        cells = [row for row in a["cells"] if row["weight_bound"] == w]
        best = min(cells, key=lambda row: row["counted_pair_add_attempts_log2"])
        assert summary["best_tested_fraction"] == best["table_fraction"] == "1/1"
        close(summary["best_tested_pair_add_attempts_log2"], best["counted_pair_add_attempts_log2"])
        close(summary["query_addition_floor_at_full_table_log2"], cells[0]["query_addition_floor_log2"])
        assert cells[0]["query_addition_floor_log2"] > 61
        assert summary["enumerated_set_sha256"] == next(
            x for x in surface["rows"] if x["weight_bound"] == w)["enumerated_set_sha256"]
    w7 = next(x for x in a["weight_summary"] if x["weight_bound"] == 7)
    close(w7["best_tested_pair_add_attempts_log2"],
          budget["conditional_full_table_counted_pair_add_attempts_log2"])
    assert a["best_tested_weight_with_matrix_proxy_below_2pow61"] == 7
    assert a["all_full_table_query_addition_floors_above_2pow61"] is True
    assert len(a["conditional_interval_endpoints_full_table"]) == 2
    assert {x["weight_bound"] for x in a["conditional_interval_endpoints_full_table"]} == {7}
    proof = read(HERE / "lean/proof_receipt.json")
    assert proof["exit_code"] == 0 and proof["source_sha256"] == sha(HERE / "lean/PairBudget.lean")
    assert proof["stdout_sha256"] == sha(HERE / "lean/build.stdout.txt")
    assert proof["stderr_sha256"] == sha(HERE / "lean/build.stderr.txt")
    assert "does not depend on any axioms" in (HERE / "lean/build.stdout.txt").read_text()
    print("PASS Q1526 84 frozen cells, source hashes, Q1462 crosscheck, Lean receipt")


if __name__ == "__main__":
    main()

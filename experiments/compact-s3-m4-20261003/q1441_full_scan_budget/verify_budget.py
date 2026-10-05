#!/usr/bin/env python3
"""Independent exact-integer/decimal audit of Q1441's declared scan gate."""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal, ROUND_CEILING
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    protocol_path = HERE / "protocol.json"
    result_path = HERE / "result.json"
    protocol = json.loads(protocol_path.read_text())
    result = json.loads(result_path.read_text())
    q1414 = json.loads((PARENT / "runs/n131_q1414_exact_uniform_query_bound.json").read_text())
    q1437 = json.loads((PARENT / "q1437_weight7_frontier/sample.json").read_text())
    assert result["protocol_sha256"] == sha(protocol_path)
    assert result["candidate_id"] is None and result["isogeny"] == "none"
    assert result["complete_solve_work_log2"] is None
    cap = 1 << 61
    assert protocol["budget_abstract_work_units"] == result[
        "budget_abstract_work_units"] == cap
    rows = result["rows"]
    assert len(rows) == 4
    exact = rows[0]
    q = q1414["query_bounds"]["rank_success_95_percent"][
        "minimum_uniform_nonidentity_queries"]
    b = q1414["actual_usable_points_B_before_folding"]
    assert exact["minimum_queries_for_declared_policy"] == q
    assert exact["actual_usable_points_B_before_folding"] == b
    assert exact["one_full_scan_action_per_query_total"] == q * b
    assert q * b < cap < 2 * q * b
    assert exact["two_actions_per_scanned_point_total"] == 2 * q * b
    estimates = [*q1437["conditional_wilson_interval_endpoints"][:1],
                 q1437["conditional_estimate"],
                 q1437["conditional_wilson_interval_endpoints"][1]]
    checked = []
    for row, estimate in zip(rows[1:], estimates):
        k = Decimal(str(estimate["conditional_K"]))
        b = Decimal(str(estimate["conditional_B"]))
        q = int(k.to_integral_value(rounding=ROUND_CEILING))
        scan = Decimal(q) * b
        matrix = 4 * k * k
        assert row["actual_usable_points_B_before_folding"] is None
        assert row["actual_folded_columns_K"] is None
        assert row["base_set_sha256"] is None
        assert row["minimum_queries_for_declared_one_row_policy"] == q
        assert Decimal(row["one_full_scan_action_per_query_total_decimal"]) == scan
        assert Decimal(row["conditional_matrix_proxy_four_K_squared_decimal"]) == matrix
        assert Decimal(row["conditional_residual_after_matrix_proxy_decimal"]) == cap - matrix
        assert scan > cap and row["one_action_scan_below_budget"] is False
        checked.append({"base_status": row["base_status"],
                        "minimum_queries": q,
                        "one_action_full_scan_exceeds_budget": True})
    verified = {
        "kind": "q1441_independent_budget_arithmetic_audit",
        "status": "passed", "proposal_id": "Q1441",
        "candidate_id": None, "isogeny": "none",
        "exact_w6_two_action_scan_exceeds_budget": True,
        "conditional_w7_one_action_scan_exceeds_budget_at_all_sample_endpoints": True,
        "w7_rows": checked,
        "scope": "audits exact W6 integer products and conditional W7 decimal products; does not validate sample representativeness, work-unit calibration, or a complete solve projection",
        "protocol_sha256": sha(protocol_path),
        "result_sha256": sha(result_path),
        "source_sha256": sha(Path(__file__)),
    }
    path = HERE / "verification.json"
    assert not path.exists(), "refuse to overwrite audit evidence"
    path.write_text(json.dumps(verified, indent=2, sort_keys=True) + "\n")
    print(json.dumps(verified, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()

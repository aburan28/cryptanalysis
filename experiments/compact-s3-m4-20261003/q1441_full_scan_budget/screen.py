#!/usr/bin/env python3
"""Q1441 necessary one-row/full-base-scan affordability screen.

All costs share a declared abstract work-unit count. No field-operation,
CPU-wall, useful-relation, or complete-solve cost is inferred from this model.
"""

from __future__ import annotations

import argparse
import json
import math
from decimal import Decimal, ROUND_CEILING
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
ROOT = PARENT.parents[1]
PROTOCOL = HERE / "protocol.json"
RESULT = HERE / "result.json"
INPUTS = (
    PARENT / "runs/n131_q1414_exact_uniform_query_bound.json",
    PARENT / "runs/n131_q1413_projected_x_w6.json",
    PARENT / "q1437_weight7_frontier/protocol.json",
    PARENT / "q1437_weight7_frontier/sample.json",
    PARENT / "q1437_weight7_frontier/verification.json",
    PARENT / "protocol.json",
)


def sha(path):
    import hashlib
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def log2(value):
    assert value > 0
    return math.log2(float(value))


def frozen_protocol():
    return {
        "kind": "q1441_frozen_full_base_scan_budget_protocol",
        "proposal_id": "Q1441", "candidate_id": None, "isogeny": "none",
        "curve_id": "EC1N131Ckb1h6816f880945e",
        "budget_abstract_work_units": 1 << 61,
        "work_unit": "one abstract countable action; not calibrated to a field operation or CPU time",
        "w6_query_policy": "Q1414 necessary minimum for 95% probability of rank K, uniform nonidentity target marginal; every decomposition and row optimistically novel",
        "w7_query_policy": "at most one verified relation row returned per target query, so Q>=ceil(K); conditional estimated K and no unsampled projection collisions",
        "scan_policy": "one complete traversal of all B subgroup-usable factor-base points per query, each charged c abstract units; all other phases set to zero",
        "matrix_scenario": "optional 4*K^2 optimistic logical row-action proxy, only if calibrated into the same abstract unit; not a measured cost or lower bound",
        "scope": "necessary affordability gate for declared uniform-query/one-row/full-scan families only; guided queries, multirow queries, compressed scans, and different work units are outside this screen",
        "input_sha256": {str(path.relative_to(ROOT)): sha(path)
                         for path in INPUTS},
        "source_sha256": sha(Path(__file__)),
        "runtime_info_sha256": sha(HERE / "sage_runtime_info.json"),
    }


def inputs(protocol):
    assert protocol["proposal_id"] == "Q1441"
    assert protocol["candidate_id"] is None and protocol["isogeny"] == "none"
    assert protocol["source_sha256"] == sha(Path(__file__))
    assert protocol["runtime_info_sha256"] == sha(HERE / "sage_runtime_info.json")
    assert json.loads((HERE / "sage_runtime_info.json").read_text())[
        "status"] == "verified"
    for name, expected in protocol["input_sha256"].items():
        assert sha(ROOT / name) == expected
    q1414 = json.loads(INPUTS[0].read_text())
    w6 = json.loads(INPUTS[1].read_text())
    q1437_protocol = json.loads(INPUTS[2].read_text())
    w7 = json.loads(INPUTS[3].read_text())
    q1437_check = json.loads(INPUTS[4].read_text())
    parent = json.loads(INPUTS[5].read_text())
    assert q1414["curve_id"] == w6["curve_id"] == w7["curve_id"] == (
        protocol["curve_id"])
    assert q1414["isogeny"] == w6["isogeny"] == w7["isogeny"] == "none"
    assert q1414["actual_usable_points_B_before_folding"] == w6[
        "actual_usable_points_B_before_folding"]
    assert q1414["folded_columns_K"] == w6[
        "signed_frobenius_columns_K"]
    assert q1414["base_set_sha256"] == w6["enumerated_set_sha256"]
    assert q1414["base_receipt_sha256"] == sha(INPUTS[1])
    assert q1414["is_complete_solve_projection"] is False
    assert w7["actual_usable_points_B_before_folding"] is None
    assert w7["actual_signed_frobenius_columns_K"] is None
    assert w7["enumerated_set_sha256"] is None
    assert w7["sample_size"] == q1437_protocol["sample_size"] == 100000
    assert q1437_check["status"] == "passed"
    assert q1437_check["sample_sha256"] == sha(INPUTS[3])
    r = parent["degree_131_design"]["curve"]["subgroup_order"]
    assert int(q1414["nonidentity_subgroup_target_count"]) == r - 1
    return q1414, w6, w7


def w6_row(q1414, budget):
    q = q1414["query_bounds"]["rank_success_95_percent"][
        "minimum_uniform_nonidentity_queries"]
    b = q1414["actual_usable_points_B_before_folding"]
    k = q1414["folded_columns_K"]
    scan = q * b
    assert q >= k and scan < budget and 2 * scan > budget
    return {
        "base_status": "Q1413 exact W<=6",
        "degree_n": 131, "weight_bound": 6,
        "actual_usable_points_B_before_folding": b,
        "folded_columns_K": k,
        "base_set_sha256": q1414["base_set_sha256"],
        "minimum_queries_for_declared_policy": q,
        "minimum_query_proof_source": "Q1414 uniform-marginal 95% rank-success bound",
        "one_full_scan_action_per_query_total": scan,
        "one_full_scan_action_per_query_total_log2": log2(scan),
        "two_actions_per_scanned_point_total": 2 * scan,
        "two_actions_per_scanned_point_total_log2": log2(2 * scan),
        "maximum_actions_per_scanned_point_zero_other_cost": budget / scan,
        "maximum_actions_per_query_zero_other_cost": budget / q,
        "maximum_actions_per_query_zero_other_cost_log2": log2(budget / q),
        "one_action_scan_below_budget": True,
        "two_action_scan_below_budget": False,
        "complete_solve_work_log2": None,
    }


def w7_row(name, estimate, budget):
    b = Decimal(str(estimate["conditional_B"]))
    k = Decimal(str(estimate["conditional_K"]))
    q = int(k.to_integral_value(rounding=ROUND_CEILING))
    scan = Decimal(q) * b
    matrix = 4 * k * k
    residual = Decimal(budget) - matrix
    assert q > 0 and b > 0 and matrix < budget
    assert scan > budget  # one complete scan per one-row query already loses.
    return {
        "base_status": name,
        "degree_n": 131, "weight_bound": 7,
        "actual_usable_points_B_before_folding": None,
        "actual_folded_columns_K": None,
        "base_set_sha256": None,
        "conditional_B_decimal": str(b),
        "conditional_K_decimal": str(k),
        "minimum_queries_for_declared_one_row_policy": q,
        "minimum_query_proof_source": "at most one verified row per query, hence Q>=ceil(conditional K)",
        "one_full_scan_action_per_query_total_decimal": str(scan),
        "one_full_scan_action_per_query_total_log2": log2(scan),
        "maximum_actions_per_scanned_point_zero_other_cost": float(
            Decimal(budget) / scan),
        "maximum_actions_per_query_zero_other_cost_log2": log2(
            Decimal(budget) / Decimal(q)),
        "one_action_scan_below_budget": False,
        "conditional_matrix_proxy_four_K_squared_decimal": str(matrix),
        "conditional_matrix_proxy_log2": log2(matrix),
        "conditional_residual_after_matrix_proxy_decimal": str(residual),
        "conditional_max_actions_per_query_after_matrix_proxy_log2": log2(
            residual / Decimal(q)),
        "conditional_max_actions_per_scanned_point_after_matrix_proxy": float(
            residual / scan),
        "complete_solve_work_log2": None,
    }


def build(protocol):
    q1414, _, w7 = inputs(protocol)
    budget = protocol["budget_abstract_work_units"]
    rows = [w6_row(q1414, budget)]
    estimates = [("Q1437 conditional W<=7 Wilson lower endpoint",
                  w7["conditional_wilson_interval_endpoints"][0]),
                 ("Q1437 conditional W<=7 sample center",
                  w7["conditional_estimate"]),
                 ("Q1437 conditional W<=7 Wilson upper endpoint",
                  w7["conditional_wilson_interval_endpoints"][1])]
    rows.extend(w7_row(name, estimate, budget) for name, estimate in estimates)
    return {
        "kind": "q1441_full_base_scan_budget_screen",
        "proposal_id": "Q1441", "candidate_id": None,
        "curve_id": protocol["curve_id"], "isogeny": "none",
        "budget_abstract_work_units": budget,
        "work_unit": protocol["work_unit"],
        "w6_query_policy": protocol["w6_query_policy"],
        "w7_query_policy": protocol["w7_query_policy"],
        "scan_policy": protocol["scan_policy"],
        "matrix_scenario": protocol["matrix_scenario"],
        "scope": protocol["scope"],
        "rows": rows,
        "decision": "Under Q1414's uniform-marginal 95% rank floor, W<=6 full scans at two abstract actions per point already exceed 2^61 before any other cost. Under the conditional W<=7 base and a one-row-per-query policy, even one abstract action per point for a full scan exceeds 2^61 across the Wilson endpoints. These are declared-family screens, not complete solve projections or algorithm-independent lower bounds.",
        "natural_relation_yield_estimate": None,
        "calibrated_field_operation_cost": None,
        "complete_solve_work_log2": None,
        "challenge_dispatch_allowed": False,
        "protocol_sha256": sha(PROTOCOL),
        "source_sha256": sha(Path(__file__)),
        "input_sha256": protocol["input_sha256"],
        "runtime_info_sha256": protocol["runtime_info_sha256"],
    }


def main():
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--freeze", action="store_true")
    group.add_argument("--emit", action="store_true")
    group.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.freeze:
        assert not PROTOCOL.exists(), "refuse to overwrite frozen protocol"
        runtime = HERE / "sage_runtime_info.json"
        assert runtime.exists() and json.loads(runtime.read_text())["status"] == "verified"
        PROTOCOL.write_text(json.dumps(frozen_protocol(), indent=2,
                                       sort_keys=True) + "\n")
        print(json.dumps({"status": "frozen", "proposal_id": "Q1441",
                          "protocol_sha256": sha(PROTOCOL)}))
        return
    protocol = json.loads(PROTOCOL.read_text())
    serialized = json.dumps(build(protocol), indent=2, sort_keys=True) + "\n"
    if args.check:
        assert RESULT.read_text() == serialized
        print("PASS: Q1441 budget screen reproduced")
    else:
        assert not RESULT.exists(), "refuse to overwrite frozen screen"
        RESULT.write_text(serialized)
        print(json.dumps({"status": "emitted", "proposal_id": "Q1441",
                          "result_sha256": sha(RESULT)}))


if __name__ == "__main__":
    main()

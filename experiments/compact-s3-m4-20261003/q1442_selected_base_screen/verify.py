"""Independent arithmetic and provenance audit of the Q1442 model screen."""

from __future__ import annotations

import argparse
import hashlib
import json
from decimal import Decimal, localcontext
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition: bool, explanation: str) -> None:
    if not condition:
        raise ValueError(explanation)


def scan_cost(b: Decimal, nonidentity_targets: Decimal) -> Decimal:
    distinct_four = b * (b - 1) * (b - 2) * (b - 3) / 24
    occupancy = distinct_four / nonidentity_targets
    coverage = 1 - (-occupancy).exp()
    return b * (b / 262) / coverage


def audit() -> dict:
    protocol_path = HERE / "protocol.json"
    result_path = HERE / "result.json"
    protocol = json.loads(protocol_path.read_text())
    result = json.loads(result_path.read_text())
    source_path = HERE / "screen.py"
    require(protocol["source_sha256"] == digest(source_path), "source changed after freeze")
    require(result["source_sha256"] == digest(source_path), "result source hash mismatch")
    require(result["protocol_sha256"] == digest(protocol_path), "result protocol hash mismatch")
    for name, expected in protocol["input_sha256"].items():
        require(digest(ROOT / name) == expected, f"input changed: {name}")
    q1414 = json.loads((ROOT / "experiments/compact-s3-m4-20261003/runs/n131_q1414_exact_uniform_query_bound.json").read_text())
    q1437 = json.loads((ROOT / "experiments/compact-s3-m4-20261003/q1437_weight7_frontier/sample.json").read_text())
    require(protocol["proposal_id"] == result["proposal_id"] == "Q1442", "proposal mismatch")
    require(protocol["curve_id"] == result["curve_id"] == q1414["curve_id"] == q1437["curve_id"], "curve mismatch")
    require(protocol["isogeny"] == result["isogeny"] == "none", "isogeny mismatch")
    require(protocol["candidate_id"] is result["candidate_id"] is None, "stage has a candidate ID")
    for key in ("actual_selected_B", "actual_selected_K", "selected_base_set_sha256"):
        require(protocol[key] is result[key] is None, f"{key} wrongly populated")
    require(result["complete_solve_work_log2"] is None and result["challenge_dispatch_allowed"] is False,
            "complete-solve claim wrongly populated")
    rows = result["rows"]
    require(len(rows) == 3, "expected three geometry rows")
    b6 = Decimal(q1414["actual_usable_points_B_before_folding"])
    k6 = Decimal(q1414["folded_columns_K"])
    bselected = Decimal(rows[1]["B_model"])
    b7 = Decimal(str(q1437["conditional_estimate"]["conditional_B"]))
    require(b6 == 262 * k6, "exact W<=6 quotient mismatch")
    require([Decimal(row["B_model"]) for row in rows] == [b6, bselected, b7], "row B mismatch")
    require(bselected == 262 * result["selected_orbit_count_model"], "selected orbit rounding mismatch")
    require(b6 < bselected < b7, "selected point outside sampled capacity")
    target_count = Decimal(q1414["nonidentity_subgroup_target_count"])
    with localcontext() as ctx:
        ctx.prec = 65
        costs = [scan_cost(b, target_count) for b in (b6, bselected, b7)]
        for row, cost in zip(rows, costs):
            reported = Decimal(row["one_action_full_scan_total_model"])
            require(abs(cost - reported) / cost < Decimal("1e-22"), "scan cost mismatch")
            require(abs(Decimal(row["budget_actions_per_scanned_point_with_all_other_costs_zero_model"]) - Decimal(2**61) / cost) < Decimal("1e-16"), "budget ratio mismatch")
        require(costs[1] < costs[0] < costs[2], "selected model did not improve full scan")
        require(costs[1] < scan_cost(bselected - 262, target_count), "selected B not lower than previous orbit count")
        require(costs[1] < scan_cost(bselected + 262, target_count), "selected B not lower than next orbit count")
        require(Decimal(rows[1]["budget_actions_per_scanned_point_with_all_other_costs_zero_model"]) < 4,
                "selected model allowance changed materially")
    return {
        "kind": "q1442_independent_model_audit",
        "status": "passed",
        "proposal_id": "Q1442",
        "protocol_sha256": digest(protocol_path),
        "result_sha256": digest(result_path),
        "verification_source_sha256": digest(Path(__file__)),
        "selected_B_is_local_integer_orbit_minimum": True,
        "all_selected_base_actuals_remain_null": True,
        "complete_solve_work_log2": None,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--emit", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.emit == args.check:
        parser.error("choose --emit or --check")
    output = HERE / "verification.json"
    record = audit()
    if args.emit:
        if output.exists():
            raise FileExistsError(f"refusing to overwrite {output}")
        output.write_text(json.dumps(record, sort_keys=True, indent=2) + "\n")
    elif json.loads(output.read_text()) != record:
        raise ValueError("verification record changed")
    else:
        print("Q1442 independent audit passed")


if __name__ == "__main__":
    main()

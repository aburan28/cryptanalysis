"""Conditional N131 base-size screen; no measured PDP or ECDLP work."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from decimal import Decimal, localcontext
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
Q1414 = ROOT / "experiments/compact-s3-m4-20261003/runs/n131_q1414_exact_uniform_query_bound.json"
Q1437 = ROOT / "experiments/compact-s3-m4-20261003/q1437_weight7_frontier/sample.json"
PROTOCOL = HERE / "protocol.json"
RESULT = HERE / "result.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_new(path: Path, payload: dict) -> None:
    if path.exists():
        raise FileExistsError(f"refusing to overwrite {path}")
    path.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n")


def frozen_protocol() -> dict:
    return {
        "kind": "q1442_conditional_selected_base_protocol",
        "proposal_id": "Q1442",
        "candidate_id": None,
        "curve_id": "EC1N131Ckb1h6816f880945e",
        "isogeny": "none",
        "actual_selected_B": None,
        "actual_selected_K": None,
        "selected_base_set_sha256": None,
        "work_unit": "one abstract action per scanned usable point; not a calibrated field operation",
        "objective": "minimize B*(B/262)/(1-exp(-C(B,4)/(r-1))) over a hypothetical signed-Frobenius orbit selected W7 base",
        "assumptions": [
            "Every selected W7 orbit is subgroup-usable, contributes exactly 262 distinct signed-Frobenius points, and has no projection collision with any selected orbit or the exact W<=6 base.",
            "Distinct four-point subset sums act as independent uniform nonidentity subgroup samples, giving Poisson target coverage 1-exp(-C(B,4)/(r-1)).",
            "Every covered ordinary query yields exactly one verified novel row; failures are charged equally to successes and no matrix, setup, target descent, or verification work is included in scan actions.",
            "The continuous optimum uses lambda approximately B^4/(24*(r-1)); its selected integer B is rounded to a multiple of 262 before exact-binomial model evaluation.",
        ],
        "source_sha256": sha(Path(__file__)),
        "input_sha256": {
            str(Q1414.relative_to(ROOT)): sha(Q1414),
            str(Q1437.relative_to(ROOT)): sha(Q1437),
        },
    }


def dstr(value: Decimal, digits: int = 18) -> str:
    return format(value, f".{digits}g")


def model_row(label: str, b: Decimal, n_targets: Decimal, budget: Decimal) -> dict:
    k = b / Decimal(262)
    # Integer B is used for selected and exact W<=6 rows. The sampled full-W7
    # row is explicitly approximate, so this generalized binomial is a model.
    lam = b * (b - 1) * (b - 2) * (b - 3) / (Decimal(24) * n_targets)
    p = Decimal(1) - (-lam).exp()
    queries = k / p
    scans = b * queries
    return {
        "label": label,
        "B_model": dstr(b, 24),
        "K_model": dstr(k, 24),
        "mean_distinct_four_sums_per_uniform_target_model": dstr(lam),
        "poisson_coverage_model": dstr(p),
        "ideal_queries_for_K_novel_rows_model": dstr(queries, 24),
        "one_action_full_scan_total_model": dstr(scans, 24),
        "one_action_full_scan_log2_model": math.log2(float(scans)),
        "budget_actions_per_scanned_point_with_all_other_costs_zero_model": dstr(budget / scans),
        "optional_4K_squared_row_action_proxy_log2": math.log2(float(4 * k * k)),
    }


def compute(protocol: dict) -> dict:
    if protocol != frozen_protocol():
        raise ValueError("protocol or source/input hashes changed")
    q1414 = json.loads(Q1414.read_text())
    q1437 = json.loads(Q1437.read_text())
    if not (q1414["curve_id"] == q1437["curve_id"] == protocol["curve_id"]):
        raise ValueError("curve identity mismatch")
    b6 = int(q1414["actual_usable_points_B_before_folding"])
    k6 = int(q1414["folded_columns_K"])
    if b6 != 262 * k6:
        raise ValueError("unexpected exact W<=6 orbit size")
    n_targets = Decimal(q1414["nonidentity_subgroup_target_count"])
    budget = Decimal(2**61)
    with localcontext() as ctx:
        ctx.prec = 65
        lo, hi = Decimal(1), Decimal(2)
        for _ in range(220):
            mid = (lo + hi) / 2
            if mid.exp() - 1 < 2 * mid:
                lo = mid
            else:
                hi = mid
        lam_star = (lo + hi) / 2
        b_continuous = (Decimal(24) * n_targets * lam_star).sqrt().sqrt()
        k_selected = int((b_continuous / 262).to_integral_value())
        b_selected = 262 * k_selected
        b7_sample = Decimal(str(q1437["conditional_estimate"]["conditional_B"]))
        if not (b6 < b_selected < b7_sample):
            raise ValueError("selected model point outside sampled W7 capacity")
        rows = [
            model_row("exact_W_le_6_geometry_with_heuristic_coverage", Decimal(b6), n_targets, budget),
            model_row("selected_W7_conditional_model", Decimal(b_selected), n_targets, budget),
            model_row("full_W7_sample_center_conditional_model", b7_sample, n_targets, budget),
        ]
        return {
            "kind": "q1442_conditional_selected_base_screen",
            "proposal_id": "Q1442",
            "candidate_id": None,
            "curve_id": protocol["curve_id"],
            "isogeny": "none",
            "actual_selected_B": None,
            "actual_selected_K": None,
            "selected_base_set_sha256": None,
            "lambda_continuous_optimum_model": dstr(lam_star),
            "continuous_optimum_B_model": dstr(b_continuous, 24),
            "selected_orbit_count_model": k_selected,
            "rows": rows,
            "work_unit": protocol["work_unit"],
            "assumptions": protocol["assumptions"],
            "ordinary_query_relation_yield_measured": None,
            "calibrated_field_operation_cost": None,
            "complete_solve_work_log2": None,
            "challenge_dispatch_allowed": False,
            "decision": "The conditional Poisson/one-row scan model favors a selected W7 base near 12 billion points rather than the sampled full W7 base. The selected set has not been enumerated or measured. Even its optimistic full scan permits only about three abstract actions per tested point when all other costs are zero. A target-conditioned pair witness method and calibrated complete-stage charges remain necessary.",
            "protocol_sha256": sha(PROTOCOL),
            "source_sha256": sha(Path(__file__)),
        }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--freeze", action="store_true")
    parser.add_argument("--emit", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if sum((args.freeze, args.emit, args.check)) != 1:
        parser.error("choose one of --freeze, --emit, --check")
    if args.freeze:
        write_new(PROTOCOL, frozen_protocol())
        return
    protocol = json.loads(PROTOCOL.read_text())
    result = compute(protocol)
    if args.emit:
        write_new(RESULT, result)
    elif json.loads(RESULT.read_text()) != result:
        raise ValueError("result is not reproducible from frozen inputs")
    else:
        print("Q1442 result reproduces from pinned source and inputs")


if __name__ == "__main__":
    main()

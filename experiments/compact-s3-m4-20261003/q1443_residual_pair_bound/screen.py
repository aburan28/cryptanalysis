"""Exact pair-support bound for target-oblivious first-pair enumeration."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from decimal import Decimal, localcontext
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
EXP = ROOT / "experiments/compact-s3-m4-20261003"
PATHS = {
    "q1438_protocol": EXP / "q1438_dense_base/protocol.json",
    "n53_base": EXP / "q1438_dense_base/n53_w4_base.json",
    "n83_base": EXP / "q1438_dense_base/n83_w6_base.json",
    "n131_w6": EXP / "runs/n131_q1414_exact_uniform_query_bound.json",
    "selected_w7_model": EXP / "q1442_selected_base_screen/result.json",
}
PROTOCOL = HERE / "protocol.json"
RESULT = HERE / "result.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_new(path: Path, value: dict) -> None:
    if path.exists():
        raise FileExistsError(f"refusing to overwrite {path}")
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")


def ceiling_ratio(numerator: int, denominator: int) -> int:
    return (numerator + denominator - 1) // denominator


def frozen_protocol() -> dict:
    return {
        "kind": "q1443_residual_pair_support_protocol",
        "proposal_id": "Q1443",
        "candidate_id": None,
        "isogeny": "none",
        "budget_abstract_first_pair_trials": 2**61,
        "work_unit": "one tested first-pair candidate; not a field operation, SAT conflict, or CPU unit",
        "law": "Each target is uniform over nonidentity subgroup points. The first-pair candidate list is fixed independently of that target. The residual pair oracle is exact and may be free. Each trial is charged at least one abstract action; for the K-row bound each trial returns at most one verified row.",
        "scope": "Applies to target-oblivious first-pair enumeration followed by exact fixed-residual pair membership. Joint target-guided first-pair search, compressed batch queries, nonuniform guided targets, and multiple rows per trial are outside the corresponding bounds.",
        "proof": "For a base of B actual usable subgroup points, at most C(B+1,2) unordered point pairs, including repeated points, can contribute distinct residual sums. For a uniform nonidentity target and any fixed first-pair sum, pair membership has probability at most C(B+1,2)/(r-1). A fixed target-independent list of t first pairs covers at most t*C(B+1,2) target points, by the union bound. Across uniform target queries, expected one-row trial successes are at most T*C(B+1,2)/(r-1); Markov gives P(rank>=K)<=T*C(B+1,2)/(K*(r-1)).",
        "source_sha256": sha(Path(__file__)),
        "input_sha256": {
            str(path.relative_to(ROOT)): sha(path) for path in PATHS.values()
        },
    }


def row(label: str, curve_id: str, b: int, k: int, r: int,
        base_digest: str | None, conditional: bool) -> dict:
    pair_count = b * (b + 1) // 2
    target_count = r - 1
    one_95 = ceiling_ratio(19 * target_count, 20 * pair_count)
    rank_95 = ceiling_ratio(19 * k * target_count, 20 * pair_count)
    with localcontext() as ctx:
        ctx.prec = 50
        p_upper = Decimal(pair_count) / Decimal(target_count)
        budget_p_upper = min(Decimal(1), Decimal(2**61) * p_upper)
    return {
        "label": label,
        "curve_id": curve_id,
        "B_used_in_bound": b,
        "K_used_in_rank_bound": k,
        "actual_B": None if conditional else b,
        "actual_K": None if conditional else k,
        "base_set_sha256": base_digest,
        "conditional_base_model": conditional,
        "subgroup_order_r": str(r),
        "maximum_unordered_pair_count": str(pair_count),
        "one_residual_pair_support_probability_upper": str(p_upper),
        "one_residual_pair_support_log2_upper": math.log2(pair_count) - math.log2(target_count),
        "minimum_first_pair_trials_for_one_relation_95pct": str(one_95),
        "minimum_first_pair_trials_for_one_relation_95pct_log2": math.log2(one_95),
        "minimum_total_first_pair_trials_for_K_rows_95pct_one_row_policy": str(rank_95),
        "minimum_total_first_pair_trials_for_K_rows_95pct_log2_one_row_policy": math.log2(rank_95),
        "one_relation_success_probability_upper_at_2pow61_trials": str(budget_p_upper),
        "K_row_trial_bound_exceeds_2pow61": rank_95 > 2**61,
    }


def compute(protocol: dict) -> dict:
    if protocol != frozen_protocol():
        raise ValueError("source or input changed after protocol freeze")
    data = {key: json.loads(path.read_text()) for key, path in PATHS.items()}
    dense = data["q1438_protocol"]
    rows = []
    for n in (53, 83):
        instance = dense["instances"][str(n)]
        base = data[f"n{n}_base"]
        if base["curve_id"] != instance["curve_id"]:
            raise ValueError("exact base curve mismatch")
        rows.append(row(
            f"N{n}_exact_W_le_{instance['new_weight_bound']}",
            instance["curve_id"],
            int(base["actual_usable_points_B_before_folding"]),
            int(base["signed_frobenius_columns_K"]),
            int(instance["subgroup_order"]),
            base["enumerated_set_sha256"], False))
    w6 = data["n131_w6"]
    r131 = int(w6["nonidentity_subgroup_target_count"]) + 1
    rows.append(row("N131_exact_W_le_6", w6["curve_id"],
                    int(w6["actual_usable_points_B_before_folding"]),
                    int(w6["folded_columns_K"]), r131,
                    w6["base_set_sha256"], False))
    selected = data["selected_w7_model"]
    if selected["curve_id"] != w6["curve_id"]:
        raise ValueError("selected model curve mismatch")
    if any(selected[key] is not None for key in
           ("actual_selected_B", "actual_selected_K", "selected_base_set_sha256")):
        raise ValueError("selected base was unexpectedly promoted")
    model = selected["rows"][1]
    b_model = int(model["B_model"])
    k_model = int(model["K_model"])
    if b_model != 262 * k_model:
        raise ValueError("selected model orbit size mismatch")
    rows.append(row("N131_selected_W7_conditional_model", w6["curve_id"],
                    b_model, k_model, r131, None, True))
    return {
        "kind": "q1443_residual_pair_support_bound",
        "proposal_id": "Q1443",
        "candidate_id": None,
        "isogeny": "none",
        "budget_abstract_first_pair_trials": 2**61,
        "work_unit": protocol["work_unit"],
        "law": protocol["law"],
        "scope": protocol["scope"],
        "proof": protocol["proof"],
        "rows": rows,
        "ordinary_N83_relation_measured": False,
        "complete_solve_work_log2": None,
        "challenge_dispatch_allowed": False,
        "decision": "At the conditional selected-W7 size, even a free exact residual-pair oracle after target-oblivious first-pair trials needs more than 2^62.96 abstract trials for 95% chance of one relation. The one-row K-rank trial bound is above 2^88.4. Therefore this composition cannot support a sub-2^61 complete-work claim in its declared unit. Prioritize a joint target-conditioned four-point search that guides both pairs before enumerating first-pair candidates.",
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
        parser.error("choose --freeze, --emit, or --check")
    if args.freeze:
        write_new(PROTOCOL, frozen_protocol())
        return
    result = compute(json.loads(PROTOCOL.read_text()))
    if args.emit:
        write_new(RESULT, result)
    elif json.loads(RESULT.read_text()) != result:
        raise ValueError("result differs from pinned source and inputs")
    else:
        print("Q1443 exact residual-pair support screen reproduces")


if __name__ == "__main__":
    main()

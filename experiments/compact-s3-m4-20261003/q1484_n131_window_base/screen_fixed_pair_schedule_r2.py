#!/usr/bin/env python3
"""Exact Q1484 R2 rank-supply screen for Q1488-style fixed pair schedules.

This is a counting bound in pair-descriptor units, not a solver benchmark.
The conditional-uniform target law and target-independent pair schedules in
the pre-registered design are essential to the proof.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path


HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
DESIGN = HERE / "design_pair_schedule_screen.json"
RECEIPT = HERE / "runs/r2/receipt.json"
AUDIT = HERE / "archive_audit_r2.json"
BUDGET = HERE / "uniform_query_budget_r2.json"
Q1402 = PARENT / "screen_q1402_fixed_pair_family.py"
OUT = HERE / "fixed_pair_schedule_screen_r2.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ceil_ratio(numerator: int, denominator: int) -> int:
    assert numerator >= 0 and denominator > 0
    return (numerator + denominator - 1) // denominator


def log2_decimal(value: int) -> str:
    assert value > 0
    return f"{math.log2(value):.12f}"


def build() -> dict:
    design = json.loads(DESIGN.read_text())
    receipt = json.loads(RECEIPT.read_text())
    audit = json.loads(AUDIT.read_text())
    budget = json.loads(BUDGET.read_text())
    assert design["proposal_id"] == receipt["proposal_id"] == "Q1484"
    assert design["candidate_id"] is receipt["candidate_id"] is None
    assert design["run_id"] is receipt["run_id"] is None
    assert design["isogeny"] == receipt["isogeny"] == "none"
    assert design["curve_id"] == receipt["curve_id"] == audit["curve_id"]
    assert audit["status"] == "PASS"
    assert audit["full_status_bitmap_count_checked"] is True
    assert audit["r1_prefix_statuses_recomputed_and_compared"] == 19922944
    for label, path in (("r2_receipt", RECEIPT),
                        ("r2_archive_audit", AUDIT),
                        ("r2_uniform_query_budget", BUDGET),
                        ("q1402_counting_source", Q1402)):
        assert sha(path) == design["frozen_inputs_sha256"][label], label
    assert budget["base_receipt_sha256"] == sha(RECEIPT)
    assert budget["base_audit_sha256"] == sha(AUDIT)

    n = receipt["field_degree_n"]
    b = receipt["actual_usable_points_B_before_folding"]
    k = receipt["signed_frobenius_columns_K"]
    r = json.loads((HERE / "protocol.json").read_text())["subgroup_order"]
    assert n == design["field_degree_n"] == budget["field_degree_n"] == 131
    assert b == audit["actual_usable_B"] == budget[
        "actual_usable_points_B_before_folding"]
    assert k == audit["folded_K"] == budget["folded_columns_K"]
    assert b == 2 * n * k  # every archived projected orbit is full length
    assert r - 1 == int(budget["nonidentity_subgroup_target_count"])
    assert receipt["enumerated_set_sha256"] == budget["base_set_sha256"]
    assert audit["receipt_sha256"] == sha(RECEIPT)
    assert audit["status_bitmap_sha256"] == receipt[
        "status_bitmap_sha256"]

    # Give the pair method *every* unordered pair of full subgroup points,
    # including repeats, as a free reusable table. This overcounts quotient
    # pair orbits and therefore weakens (never strengthens) the lower bound.
    maximum_table_descriptors = b * (b + 1) // 2
    orientation_cap = 4 * n * n  # Q1402: at most 2n images on each side
    assert maximum_table_descriptors == math.comb(b + 1, 2)

    def minimum_probes(fraction: str, multiplier: int = 1) -> dict:
        numerator_text, denominator_text = fraction.split("/")
        numerator, denominator = int(numerator_text), int(denominator_text)
        assert 0 < numerator <= denominator
        count = ceil_ratio(
            numerator * multiplier * (r - 1),
            denominator * orientation_cap * maximum_table_descriptors)
        return {"fraction": fraction,
                "necessary_target_side_pair_descriptors": count,
                "necessary_target_side_pair_descriptors_log2":
                    log2_decimal(count)}

    direct = {fraction: minimum_probes(fraction)
              for fraction in design["direct_support_thresholds"]}
    full_rank = minimum_probes(design["rank_success_threshold"], k)
    required = full_rank["necessary_target_side_pair_descriptors"]
    work_cap = 1 << 61
    assert required > work_cap
    return {
        "kind": "q1484_r2_fixed_pair_schedule_rank_supply_screen",
        "proposal_id": "Q1484",
        "parent_counting_theorem_proposal_id": "Q1402",
        "matched_pair_table_stage_proposal_id": "Q1488",
        "candidate_id": None, "run_id": None, "isogeny": "none",
        "curve_id": receipt["curve_id"], "field_degree_n": n,
        "factor_base_actual_B_before_folding": b,
        "factor_base_folded_columns_K": k,
        "factor_base_set_sha256": receipt["enumerated_set_sha256"],
        "subgroup_order_r": r,
        "nonidentity_target_count": r - 1,
        "generous_complete_table_maximum_descriptors_M":
            maximum_table_descriptors,
        "generous_complete_table_maximum_descriptors_log2":
            log2_decimal(maximum_table_descriptors),
        "signed_frobenius_orientation_cap_per_descriptor_pair":
            orientation_cap,
        "direct_support_at_maximum_table": direct,
        "full_K_rank_95_percent": full_rank,
        "pair_probe_budget": work_cap,
        "necessary_probe_count_over_2pow61":
            f"{required / work_cap:.12f}",
        "necessary_probe_log2_gap_over_2pow61":
            f"{math.log2(required) - 61:.12f}",
        "proof": (
            "For each target-independent table descriptor and target-side "
            "descriptor, at most (2n)^2 signed-Frobenius oriented pair "
            "sums can equal a uniform nonidentity subgroup target. Thus "
            "expected oriented matches over all queries are at most "
            "4*n^2*M*sum(R_i)/(r-1). Novel rank is at most the match "
            "count. Markov gives P(rank>=K)<=E[matches]/K. Replace M by "
            "the generous complete table cap B*(B+1)/2 and solve for "
            "sum(R_i) at the pre-registered rank-success fraction."),
        "query_law": design["query_law"],
        "rank_goal": design["rank_goal"],
        "accounting_unit": design["accounting_unit"],
        "claim_boundary": design["claim_boundary"],
        "is_empirical_relation_yield": False,
        "is_complete_solve_projection": False,
        "complete_solve_work_log2": None,
        "challenge_dispatch_allowed": False,
        "design_sha256": sha(DESIGN),
        "source_sha256": sha(Path(__file__)),
        "r2_receipt_sha256": sha(RECEIPT),
        "r2_audit_sha256": sha(AUDIT),
        "r2_uniform_query_budget_sha256": sha(BUDGET),
        "q1402_counting_source_sha256": sha(Q1402),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    encoded = json.dumps(build(), indent=2, sort_keys=True) + "\n"
    if args.check:
        assert OUT.read_text() == encoded
        print("Q1484 R2 fixed pair schedule screen PASS (archived)")
    else:
        assert not OUT.exists(), "refusing to overwrite archived screen"
        OUT.write_text(encoded)
        result = json.loads(encoded)
        print(json.dumps({
            "status": "complete",
            "necessary_full_rank_pair_probes_log2": result[
                "full_K_rank_95_percent"]["necessary_target_side_pair_descriptors_log2"],
            "direct_10pct_pair_probes_log2": result[
                "direct_support_at_maximum_table"]["1/10"][
                    "necessary_target_side_pair_descriptors_log2"],
        }, sort_keys=True))


if __name__ == "__main__":
    main()

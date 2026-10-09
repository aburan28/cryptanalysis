#!/usr/bin/env python3
"""Exact conditional union bound for two fixed N131 pair prefixes."""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal, localcontext
from fractions import Fraction
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def quotient_decimal(value: Fraction, digits: int = 50) -> str:
    with localcontext() as ctx:
        ctx.prec = digits
        return str(Decimal(value.numerator) / Decimal(value.denominator))


def ceil_fraction(value: Fraction) -> int:
    return (value.numerator + value.denominator - 1) // value.denominator


def main() -> None:
    out = HERE / "bound.json"
    if out.exists():
        raise FileExistsError("preserve first exact-bound receipt")
    protocol_path = HERE / "protocol.json"
    freeze_path = HERE / "freeze.json"
    census_path = HERE / "n41_census.json"
    protocol = json.loads(protocol_path.read_text())
    freeze = json.loads(freeze_path.read_text())
    census = json.loads(census_path.read_text())
    frontier_path = (HERE / protocol["n131_frontier_source"]).resolve()
    frontier = json.loads(frontier_path.read_text())
    assert sha(protocol_path) == freeze["protocol_sha256"]
    assert sha(HERE / "census.cpp") == freeze["source_sha256"]
    assert sha(HERE / "census") == freeze["binary_sha256"]
    assert sha(HERE / protocol["n41_input"]) == freeze["input_sha256"]
    assert sha(frontier_path) == protocol["n131_frontier_sha256"]
    assert frontier["curve_id"] == protocol["n131_curve_id"]
    assert census["status"] == "COMPLETE_CENSUS"
    assert census["pair_list_sizes"] == [1956] * 4
    assert census["raw_completion_combinations"] == 1956**2
    assert census["distinct_completion_points"] == 1956**2
    assert census["complete_rows"] == 12

    r131 = int(frontier["subgroup_order"])
    slot_points = frontier["slot_usable_points_B"]
    pairs_upper = slot_points * (slot_points - 1) // 2
    assert pairs_upper == int(frontier["unordered_signed_point_pair_states_upper"])
    completion_support_upper = pairs_upper**2
    p131 = Fraction(completion_support_upper, r131 - 1)
    necessary_probes_50 = ceil_fraction(Fraction(1, 2) / p131)
    rate_600 = Fraction(necessary_probes_50, 600)

    r41 = census["subgroup_order"]
    support41 = census["distinct_completion_points"]
    p41 = Fraction(support41, r41 - 1)
    empirical_prefix_hit_fraction = Fraction(
        census["sumset_hits"], census["admissible_prefixes"])
    report = {
        "kind": "two_fixed_pair_completion_density_bound",
        "status": "EXACT_CONDITIONAL_BOUND_AND_N41_CENSUS",
        "proposal_id": protocol["proposal_id"],
        "candidate_id": None,
        "run_id": None,
        "n131": {
            "curve_id": protocol["n131_curve_id"],
            "subgroup_order": str(r131),
            "usable_signed_points_per_slot": slot_points,
            "unordered_pair_states_per_domain_upper": str(pairs_upper),
            "two_free_pair_completion_support_upper": str(completion_support_upper),
            "single_target_independent_prefix_success_upper_fraction": {
                "numerator": str(p131.numerator), "denominator": str(p131.denominator)},
            "single_target_independent_prefix_success_upper_decimal": quotient_decimal(p131),
            "prefixes_necessary_for_50_percent_success_by_union_bound":
                str(necessary_probes_50),
            "prefixes_per_second_necessary_in_600s_fraction": {
                "numerator": str(rate_600.numerator),
                "denominator": str(rate_600.denominator)},
            "prefixes_per_second_necessary_in_600s_decimal":
                quotient_decimal(rate_600),
        },
        "n41": {
            "curve_id": protocol["n41_curve_id"],
            "raw_completion_combinations": census["raw_completion_combinations"],
            "distinct_completion_points": support41,
            "completion_support_injective_on_pair_witness_combinations": True,
            "uniform_nonidentity_residual_hit_fraction": {
                "numerator": str(p41.numerator), "denominator": str(p41.denominator)},
            "uniform_nonidentity_residual_hit_decimal": quotient_decimal(p41),
            "fixed_public_target_admissible_prefixes": census["admissible_prefixes"],
            "fixed_public_target_sumset_hits": census["sumset_hits"],
            "fixed_public_target_hit_fraction": {
                "numerator": str(empirical_prefix_hit_fraction.numerator),
                "denominator": str(empirical_prefix_hit_fraction.denominator)},
            "fixed_public_target_hit_decimal": quotient_decimal(empirical_prefix_hit_fraction),
            "first_group_hit_prefix_index": census["first_hit_index"],
            "first_eight_column_row_prefix_index": census["first_valid_index"],
            "eight_column_rows": census["complete_rows"],
            "setup_ns": census["setup_ns"],
            "query_ns": census["query_ns"],
            "peak_rss_bytes": census["peak_rss_bytes"],
        },
        "source_sha256": {
            "protocol": sha(protocol_path), "freeze": sha(freeze_path),
            "n41_census": sha(census_path), "n131_frontier": sha(frontier_path),
            "source": sha(Path(__file__)),
        },
        "claim_boundary": protocol["claim_boundary"],
    }
    out.write_text(json.dumps(report, sort_keys=True, separators=(",", ":")) + "\n")
    print(json.dumps({"status": report["status"],
                      "n131_necessary_prefixes": str(necessary_probes_50),
                      "n41_completion_support": support41}))


if __name__ == "__main__":
    main()

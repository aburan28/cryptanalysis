#!/usr/bin/env python3
"""One-target support gate for the static normal-basis weight-five base."""

import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
import curves  # noqa: E402


def fourth_root_ceiling(value):
    low, high = 0, 1
    while high ** 4 < value:
        high *= 2
    while low + 1 < high:
        middle = (low + high) // 2
        if middle ** 4 >= value:
            high = middle
        else:
            low = middle
    return high


def main():
    degree = 131
    order = curves.curveOrder(degree)
    assert order % 4 == 0
    subgroup_order = order // 4
    x_cap = sum(math.comb(degree, weight) for weight in range(1, 6))
    # Each nonzero x has at most two points; cofactor projection cannot add
    # points.  This cap deliberately grants every x rationality and both signs.
    point_cap = 2 * x_cap
    numerator = min(point_cap ** 4, subgroup_order)
    # P(R in four-sum support) <= number of ordered quadruples / r when R is
    # uniform in the order-r subgroup, regardless of the solver used.
    lower_b_for_half = fourth_root_ceiling((subgroup_order + 1) // 2)
    report = {
        "kind": "uniform_one_target_static_base_four_sum_support_gate",
        "scope": "rigorous upper bound for four summands from normal-basis x weight <=5 after cofactor projection; does not constrain larger or adaptive bases",
        "candidate_id": None,
        "field_degree": degree,
        "curve_order": str(order),
        "subgroup_order": str(subgroup_order),
        "candidate_x_upper_bound": x_cap,
        "subgroup_usable_point_upper_bound_B": point_cap,
        "single_uniform_target_success_probability_upper_bound": f"{numerator}/{subgroup_order}",
        "single_uniform_target_success_probability_upper_log2": math.log2(numerator) - math.log2(subgroup_order),
        "minimum_B_necessary_for_half_success_by_union_bound": lower_b_for_half,
        "minimum_B_necessary_for_half_success_log2": math.log2(lower_b_for_half),
        "proof": "At most two curve points lie over each nonzero x. Projecting through the cofactor cannot increase the number of distinct points. Their ordered fourfold sums form a set of at most B^4 subgroup points. A uniform subgroup target lands in that set with probability at most min(1,B^4/r).",
        "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "curve_source_sha256": hashlib.sha256((HERE / "curves.py").read_bytes()).hexdigest(),
    }
    output = HERE / "weight5_support_gate.json"
    output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({key: report[key] for key in (
        "subgroup_order", "candidate_x_upper_bound",
        "subgroup_usable_point_upper_bound_B",
        "single_uniform_target_success_probability_upper_log2",
        "minimum_B_necessary_for_half_success_log2")}, indent=2))


if __name__ == "__main__":
    main()

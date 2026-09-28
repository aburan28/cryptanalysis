#!/usr/bin/env python3
"""Count or bound the distinct coefficient sums behind two-seed relations.

A cross-seed pair is a*G+b*Q for a,b in C.  Two such pairs sum to
u*G+v*Q with u,v in C+C, so the number of possible known-log query
scalars is at most |C+C|².  Counting pair probes as independent relation
opportunities would therefore overstate coverage.
"""

import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def coefficients(n, length, lam, order):
    result = {sign * pow(2, power, order) * pow(lam, shift, order) % order
              for sign in (1, -1)
              for power in range(length)
              for shift in range(n)}
    assert len(result) == 2 * n * length
    return result


def exact_two_sum_count(values, order):
    values = sorted(values)
    sums = set()
    for pos, left in enumerate(values):
        sums.update((left + right) % order for right in values[pos:])
    return len(sums)


def row(n, length, geometry_name, count_exact):
    geometry_path = HERE / "runs" / geometry_name
    geometry = json.loads(geometry_path.read_text())
    order = int(geometry["subgroup_order"])
    lam = int(geometry["frobenius_eigenvalue_mod_r"])
    values = coefficients(n, length, lam, order)
    c = len(values)
    pair_count = c * c
    upper = c * (c + 1) // 2
    exact = exact_two_sum_count(values, order) if count_exact else None
    support_cap = exact if exact is not None else upper
    probability_cap = min(1.0, support_cap * support_cap / (order - 1))
    expected_failed_scans_lower = (1 / probability_cap - 1)
    return {
        "degree": n, "curve_id": geometry["curve_id"],
        "doubling_window": length,
        "coefficient_set_cardinality": c,
        "cross_seed_pair_count": pair_count,
        "two_coefficient_sum_count_exact": exact,
        "two_coefficient_sum_count_upper": upper,
        "exact_two_sum_to_ordered_pair_ratio": (
            exact / pair_count if exact is not None else None),
        "query_scalar_support_count_upper": str(support_cap * support_cap),
        "uniform_known_log_query_hit_probability_upper": probability_cap,
        "iid_uniform_expected_failed_full_scans_lower": expected_failed_scans_lower,
        "iid_uniform_expected_failed_pair_probes_lower_log2": (
            math.log2(expected_failed_scans_lower * pair_count)
            if expected_failed_scans_lower > 0 else 0),
        "geometry_receipt_sha256": sha(geometry_path),
    }


def main():
    rows = [
        row(53, 16, "n53_dyadic_two_seed_geometry.json", True),
        row(83, 20, "n83_dyadic_base_geometry.json", True),
        row(83, 1000, "n83_dyadic_target_seed_geometry.json", False),
    ]
    report = {
        "kind": "two_seed_dyadic_four_sum_relation_support_screen",
        "proposal_ids": ["Q1019", "Q1020"], "candidate_id": None,
        "scope": "exact coefficient combinatorics at n53 and n83 L20; rigorous two-sum cardinality upper bound at n83 L1000; no measured n83 relation yield or complete DLP",
        "argument": "For one fixed public Q, a known-log query alpha*G admits a cross-seed four-sum only if alpha belongs to (C+C)+log_G(Q)*(C+C). Its support is at most |C+C|^2, even if every quotient lookup is perfect.",
        "n83_window20_role": "coefficient-collision diagnostic using the same ONB curve and Frobenius eigenvalue; it is not a relation-yield bound for the 100-seed Q1013 base",
        "query_probability_model": "alpha uniformly sampled independently from 1..r-1; p at most support/(r-1); expected complete failed scans at least 1/p-1",
        "rows": rows,
        "verified_complete_solve_work_log2": None,
        "source_sha256": sha(Path(__file__)),
    }
    out = HERE / "dyadic_coefficient_support.json"
    out.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"n53_probability_upper": rows[0][
        "uniform_known_log_query_hit_probability_upper"],
                      "n83_1000_probability_upper": rows[2][
        "uniform_known_log_query_hit_probability_upper"],
                      "n83_failed_probe_lower_log2": rows[2][
        "iid_uniform_expected_failed_pair_probes_lower_log2"]}))


if __name__ == "__main__":
    main()

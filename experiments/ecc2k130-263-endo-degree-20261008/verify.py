#!/usr/bin/env python3
"""Replay the exact endomorphism-order and two-summand capacity screen."""

import argparse
import hashlib
import json
from math import gcd
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ROUTE_PATH = ROOT / "experiments/koblitz-polynomial-w-pair-20260925/ecc2k130_degree263_route_manifest.json"
W24_PATH = ROOT / "experiments/ecc2k130-263-equal-w24-workload-20261005/CONFIG.json"
RESULT_PATH = Path(__file__).with_name("result.json")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha256_file(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def f2_point_count(coefficients):
    a1, a2, a3, a4, a6 = coefficients
    count = 1  # Identity.
    for x in (0, 1):
        for y in (0, 1):
            lhs = y * y + a1 * x * y + a3 * y
            rhs = x * x * x + a2 * x * x + a4 * x + a6
            count += (lhs - rhs) % 2 == 0
    return count


def norm(a, b, ell):
    """Norm of a + ell*b*tau, where tau^2 - tau + 2 = 0."""
    return a * a + ell * a * b + 2 * (ell * b) ** 2


def least_b_for_one_percent(nonidentity_targets):
    """Smallest B with 100 * binomial(B+1, 2) >= target count."""
    lo, hi = 0, 1
    while 50 * hi * (hi + 1) < nonidentity_targets:
        hi *= 2
    while lo < hi:
        mid = (lo + hi) // 2
        if 50 * mid * (mid + 1) >= nonidentity_targets:
            hi = mid
        else:
            lo = mid + 1
    return lo


def derive():
    route = json.loads(ROUTE_PATH.read_text())
    w24 = json.loads(W24_PATH.read_text())
    end = route["endomorphism"]
    source = route["curve_nodes"]["source"]
    descendant = route["curve_nodes"]["target"]
    ell = end["ell"]
    require(ell == 263, "unexpected route degree")
    require(route["isogeny"]["degree"] == ell, "route degree mismatch")
    require(route["isogeny"]["direction"] == "descending", "route is not descending")
    require(end["source_order_conductor"] == 1, "source conductor is not maximal")
    require(end["target_order_conductor"] == ell, "descendant conductor mismatch")
    require(source["curve_id"] == w24["source_curve_id"], "source curve mismatch")
    require(descendant["curve_id"] == w24["descendant_curve_id"], "descendant curve mismatch")
    require(sha256_file(ROUTE_PATH) == w24["route_manifest_sha256"], "route receipt mismatch")
    require(source["subgroup_order"] == descendant["subgroup_order"], "subgroup order mismatch")
    require(route["field"]["n"] == 131 and gcd(source["subgroup_order"], 4) == 1,
            "Frobenius orbit conditions mismatch")
    require(w24["selected_usable_points_B_each"] == 2 * w24["selected_signed_columns_each"],
            "W24 usable-point count mismatch")

    # The source is defined over F_2. Its Frobenius has trace -1, so
    # tau = -pi_2 satisfies tau^2 - tau + 2 = 0 and the field discriminant is -7.
    f2_points = f2_point_count(source["coefficients_a1_a2_a3_a4_a6"])
    trace = 3 - f2_points
    field_discriminant = trace * trace - 8
    require(f2_points == 4 and trace == -1 and field_discriminant == -7,
            "unexpected source F_2 Frobenius")
    descendant_discriminant = ell * ell * field_discriminant

    # 4*N(a+ell*b*tau) = (2*a+ell*b)^2 + 7*ell^2*b^2.
    minimum_degree = (1 + 7 * ell * ell) // 4
    require((1 + 7 * ell * ell) % 4 == 0, "minimum degree is nonintegral")
    minimizers = []
    for b in (-1, 1):
        for q in (-1, 1):
            a = (q - ell * b) // 2
            require(2 * a + ell * b == q, "minimum trace parity mismatch")
            require(norm(a, b, ell) == minimum_degree, "minimum norm mismatch")
            minimizers.append({"a": a, "b": b})
    require(7 * ell * ell > minimum_degree,
            "the |b| >= 2 lower bound does not exclude another minimum")
    require(norm(0, 1, 1) == 2, "source degree-two endomorphism mismatch")

    r = source["subgroup_order"]
    b_min = least_b_for_one_percent(r - 1)
    require(50 * (b_min - 1) * b_min < r - 1 <= 50 * b_min * (b_min + 1),
            "one-percent boundary is not minimal")
    orbit_max = 2 * route["field"]["n"]
    min_columns = (b_min + orbit_max - 1) // orbit_max
    one_bit_bytes = (min_columns + 7) // 8
    w24_b = w24["selected_usable_points_B_each"]
    w24_pairs = w24_b * (w24_b + 1) // 2

    return {
        "schema": "ecc2k130-263-endo-degree-screen-v1",
        "verifier_sha256": sha256_file(Path(__file__)),
        "inputs_sha256": {"route_manifest": sha256_file(ROUTE_PATH), "w24_config": sha256_file(W24_PATH)},
        "source_curve_id": source["curve_id"],
        "descendant_curve_id": descendant["curve_id"],
        "subgroup_order": r,
        "source_f2_point_count": f2_points,
        "source_frobenius_trace": trace,
        "source_order_discriminant": field_discriminant,
        "descendant_order_discriminant": descendant_discriminant,
        "source_smallest_nonscalar_degree": 2,
        "descendant_smallest_nonscalar_degree": minimum_degree,
        "descendant_degree_minimizers_a_plus_263b_tau": minimizers,
        "one_percent_two_summand_minimum_B": b_min,
        "one_percent_minimum_columns_at_orbit_size_262": min_columns,
        "one_percent_minimum_one_bit_column_bytes": one_bit_bytes,
        "w24_actual_B": w24_b,
        "w24_two_summand_support_upper_numerator": w24_pairs,
        "w24_two_summand_support_upper_denominator": r - 1,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, help="write a fresh result receipt")
    parser.add_argument("--check", action="store_true", help="compare with the committed receipt")
    args = parser.parse_args()
    require(not (args.out and args.check), "choose --out or --check")
    result = derive()
    if args.check:
        require(json.loads(RESULT_PATH.read_text()) == result, "committed receipt differs")
        print("PASS_EXACT_ENDOMORPHISM_AND_TWO_SUM_BOUNDS")
    elif args.out:
        args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    else:
        print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

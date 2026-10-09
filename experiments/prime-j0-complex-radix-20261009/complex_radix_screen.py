#!/usr/bin/env python3
"""Exact thirteen-window Eisenstein and fixed-slot capacity certificates."""

import hashlib
import json
from math import isqrt
from pathlib import Path


ORDER = int("FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141", 16)
SCALE = 10**30
WINDOWS = 13
CURRENT_RADIX = 943
POINT_BYTES = 72
COMPRESSED_POINT_BYTES = 32
MEMORY_CAP_BYTES = 140 * 1024**2
K = 1_925_782
HERE = Path(__file__).resolve().parent


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def radical_bounds(n):
    lower = isqrt(n * SCALE * SCALE)
    return lower, lower + 1


def uniform_certificate(norm):
    """Decide the strict sufficient inequality using directed integer bounds."""
    r_lo, r_hi = radical_bounds(norm)
    n_lo, n_hi = radical_bounds(ORDER)
    t_lo, t_hi = radical_bounds(3)
    left_lo = n_lo * SCALE**WINDOWS + sum(
        r_lo**k * SCALE ** (WINDOWS + 1 - k)
        for k in range(1, WINDOWS + 1)
    )
    left_hi = n_hi * SCALE**WINDOWS + sum(
        r_hi**k * SCALE ** (WINDOWS + 1 - k)
        for k in range(1, WINDOWS + 1)
    )
    right_lo = t_lo * r_lo**WINDOWS
    right_hi = t_hi * r_hi**WINDOWS
    passed = left_hi < right_lo
    failed = left_lo >= right_hi
    if passed == failed:
        raise AssertionError(f"insufficient radical precision for norm {norm}")
    return {
        "norm": norm,
        "status": "pass" if passed else "fail",
        "left_lower_scaled": str(left_lo),
        "left_upper_scaled": str(left_hi),
        "right_lower_scaled": str(right_lo),
        "right_upper_scaled": str(right_hi),
    }


def first_passing_norm():
    assert uniform_certificate(1)["status"] == "fail"
    assert uniform_certificate(CURRENT_RADIX**2)["status"] == "pass"
    lo, hi = 1, CURRENT_RADIX**2
    # Divide the inequality by r^13. Every negative-power term decreases
    # with r>1, so the predicate is monotone in positive N.
    while lo + 1 < hi:
        mid = (lo + hi) // 2
        if uniform_certificate(mid)["status"] == "pass":
            hi = mid
        else:
            lo = mid
    assert uniform_certificate(lo)["status"] == "fail"
    assert uniform_certificate(hi)["status"] == "pass"
    return lo, hi


def witnesses(norm, max_abs_b):
    result = []
    for b in range(-max_abs_b, max_abs_b + 1):
        c_squared = 4 * norm - 3 * b * b
        if c_squared < 0:
            continue
        c = isqrt(c_squared)
        if c * c != c_squared:
            continue
        for signed_c in sorted({-c, c}):
            if (signed_c + b) & 1:
                continue
            a = (signed_c + b) // 2
            assert a * a - a * b + b * b == norm
            result.append((a, b))
    return result


def orbit_count(norm):
    g2 = 4 if norm % 4 == 0 else 1
    g3 = 3 if norm % 3 == 0 else 1
    numerator = norm + g2 + 2 * g3 + 2
    assert numerator % 6 == 0
    return numerator // 6


def balanced_product(point_count, slots):
    q, extra = divmod(point_count, slots)
    return (1 + 6 * q) ** (slots - extra) * (1 + 6 * (q + 1)) ** extra


def capacity_threshold(slots):
    lo, hi = 0, 1
    while balanced_product(hi, slots) < ORDER:
        hi *= 2
    while lo + 1 < hi:
        mid = (lo + hi) // 2
        if balanced_product(mid, slots) >= ORDER:
            hi = mid
        else:
            lo = mid
    assert balanced_product(hi - 1, slots) < ORDER <= balanced_product(hi, slots)
    return {
        "slots": slots,
        "minimum_stored_nonidentity_points": hi,
        "product_at_previous": str(balanced_product(hi - 1, slots)),
        "product_at_minimum": str(balanced_product(hi, slots)),
        "point_bytes_at_72": hi * POINT_BYTES,
        "point_bytes_at_32": hi * COMPRESSED_POINT_BYTES,
        "fits_140_mib_at_72": hi * POINT_BYTES <= MEMORY_CAP_BYTES,
        "fits_140_mib_at_32": hi * COMPRESSED_POINT_BYTES <= MEMORY_CAP_BYTES,
    }


def main():
    previous_norm, threshold = first_passing_norm()
    max_abs_b = isqrt(4 * CURRENT_RADIX**2 // 3)
    represented = []
    for norm in range(threshold, CURRENT_RADIX**2 + 1):
        pairs = witnesses(norm, max_abs_b)
        if not pairs:
            continue
        slots = orbit_count(norm)
        preferred = min(pairs, key=lambda p: (abs(p[1]), abs(p[0]), p[0] < 0, p))
        represented.append((slots, norm, preferred, len(pairs)))
    assert represented
    first_norm = min(represented, key=lambda row: row[1])
    min_slots = min(row[0] for row in represented)
    # Choose the smallest shear coefficient among the equal-slot designs.
    best = min((row for row in represented if row[0] == min_slots),
               key=lambda row: (abs(row[2][1]), row[1], abs(row[2][0])))
    for slots, norm, (a, b), count in represented:
        assert count > 0 and slots == orbit_count(norm)
        assert a * a - a * b + b * b == norm

    sqrt3_floor = radical_bounds(3)[0]
    bound_left = (6 * K) ** WINDOWS * (4 * SCALE - 2 * sqrt3_floor)
    bound_right = WINDOWS**WINDOWS * ORDER * SCALE
    assert bound_left < bound_right
    lower_point_slots = K + 1
    current_slots = WINDOWS * (1 + (CURRENT_RADIX**2 - 1) // 6)
    assert current_slots == 1_926_717
    uniform_slots = WINDOWS * min_slots
    cap12, cap13 = capacity_threshold(12), capacity_threshold(13)
    assert cap13["minimum_stored_nonidentity_points"] == 1_835_553
    assert not cap12["fits_140_mib_at_72"]
    assert not cap12["fits_140_mib_at_32"]

    result = {
        "schema": 1,
        "model": "thirteen_window_nearest_residue_norm_certificate_and_fixed_slot_capacity",
        "subgroup_order_hex": f"{ORDER:064X}",
        "scale": str(SCALE),
        "windows": WINDOWS,
        "current_radix": CURRENT_RADIX,
        "current_point_slots": current_slots,
        "current_point_bytes": current_slots * POINT_BYTES,
        "uniform_norm_boundary": {
            "last_failing": uniform_certificate(previous_norm),
            "first_passing": uniform_certificate(threshold),
        },
        "eisenstein_norm_search": {
            "norm_interval_inclusive": [threshold, CURRENT_RADIX**2],
            "max_abs_b": max_abs_b,
            "representable_norm_count": len(represented),
            "first_representable": {
                "norm": first_norm[1], "orbit_slots_per_window": first_norm[0],
                "beta_a_plus_b_omega": list(first_norm[2]),
            },
            "minimum_orbit_slots_per_window": min_slots,
            "preferred_equal_slot_design": {
                "norm": best[1], "orbit_slots_per_window": best[0],
                "beta_a_plus_b_omega": list(best[2]),
            },
            "uniform_13_window_point_slots": uniform_slots,
            "uniform_13_window_point_bytes": uniform_slots * POINT_BYTES,
            "point_bytes_saved_vs_radix_943": (current_slots - uniform_slots) * POINT_BYTES,
        },
        "variable_radix_continuous_bound": {
            "tested_integer_K": K,
            "left": str(bound_left), "right": str(bound_right),
            "minimum_integer_point_slots": lower_point_slots,
            "minimum_point_bytes": lower_point_slots * POINT_BYTES,
            "maximum_point_bytes_savable_vs_radix_943":
                (current_slots - lower_point_slots) * POINT_BYTES,
        },
        "fixed_slot_capacity": {
            "memory_cap_bytes": MEMORY_CAP_BYTES,
            "twelve": cap12,
            "thirteen": cap13,
        },
        "source_sha256": {
            "protocol": sha256(HERE / "PROTOCOL.md"),
            "screen": sha256(Path(__file__)),
        },
        "cpu_timing_used": False,
    }
    output = HERE / "complex-radix-screen-result.json"
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "first_passing_norm": threshold,
        "first_representable_norm": first_norm[1],
        "minimum_uniform_point_slots": uniform_slots,
        "twelve_slot_minimum_points": cap12["minimum_stored_nonidentity_points"],
        "variable_bound_minimum_slots": lower_point_slots,
    }, sort_keys=True))


if __name__ == "__main__":
    main()

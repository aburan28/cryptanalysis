#!/usr/bin/env python3
"""Check one deferred-normalization tau step and shift-based balancing."""

import argparse
import hashlib
import json
from pathlib import Path
import random

import eisenstein_montgomery as field


R2 = field.R * field.R
C = R2 - field.P
ORDER = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141
GENERATOR = (
    0x79BE667EF9DCBBAC55A06295CE870B07029BFCDB2DCE28D959F2815B16F81798,
    0x483ADA7726A3C4655DA4FBFC0E1108A8FD17B448A68554199C47D08FFB10D4B8,
)


def raw_multiply(x, y):
    product = field.product(x, y)
    q = tuple(-u % field.R for u in field.product(product, field.PI_INVERSE_R))
    numerator = field.add(product, field.product(q, field.PI))
    assert all(u % field.R == 0 for u in numerator)
    return tuple(u // field.R for u in numerator)


def shifted_floor(t):
    """Exact floor(t/p) from arithmetic radix shift and one correction."""
    q = t // R2
    residue = t - q * field.P
    adjustment = 0
    if residue < 0:
        q -= 1
        adjustment = -1
    elif residue >= field.P:
        q += 1
        adjustment = 1
    assert 0 <= t - q * field.P < field.P
    assert q == t // field.P
    return q, adjustment


def balance_shifted(x):
    """Nearest lattice point without general integer division by p."""
    t = field.product(x, field.conjugate(field.PI))
    center_a, adjust_a = shifted_floor(t[0])
    center_b, adjust_b = shifted_floor(t[1])
    choices = ((a, b) for a in range(center_a, center_a + 2)
               for b in range(center_b, center_b + 2))
    correction = min(choices,
                     key=lambda q: (field.norm(field.sub(x, field.product(q, field.PI))), q))
    reduced = field.sub(x, field.product(correction, field.PI))
    assert 3 * field.norm(reduced) <= field.P
    return reduced, correction, (adjust_a, adjust_b)


def lazy_tau(x, y, z):
    x2 = raw_multiply(x, x)
    x3 = raw_multiply(x2, x)
    y2 = raw_multiply(y, y)
    rx = field.sub(field.times_small(4, y2),
                   field.times_small(3, x3))
    inner = field.sub(field.times_small(3, x3), field.times_small(2, rx))
    ry = raw_multiply(y, inner)
    tau_x = field.one_minus_omega(x)
    rz = raw_multiply(tau_x, z)
    return (rx, ry, rz), (x2, x3, y2, rx, inner, ry, tau_x, rz)


def point_add(a, b):
    if a is None:
        return b
    if b is None:
        return a
    x1, y1 = a
    x2, y2 = b
    if x1 == x2 and (y1 + y2) % field.P == 0:
        return None
    if a == b:
        slope = 3 * x1 * x1 * pow(2 * y1, -1, field.P) % field.P
    else:
        slope = (y2 - y1) * pow(x2 - x1, -1, field.P) % field.P
    x3 = (slope * slope - x1 - x2) % field.P
    return x3, (slope * (x1 - x3) - y1) % field.P


def point_multiply(k):
    result = None
    base = GENERATOR
    while k:
        if k & 1:
            result = point_add(result, base)
        base = point_add(base, base)
        k >>= 1
    return result


def verify_field_case(x, y, z):
    encoded = tuple(field.encode(u) for u in (x, y, z))
    raw, intermediates = lazy_tau(*encoded)
    corrected = tuple(balance_shifted(value) for value in raw)
    for value, (reduced, _, _) in zip(raw, corrected):
        assert reduced == field.balance(value)[0]
    x3 = pow(x, 3, field.P)
    rx = (4 * y * y - 3 * x3) % field.P
    ry = (y * (3 * x3 - 2 * rx)) % field.P
    rz = ((1 - field.BETA) * x * z) % field.P
    assert tuple(field.decode(item[0]) for item in corrected) == (rx, ry, rz)
    return raw, corrected, intermediates


def verify_point_case(point, z):
    assert point is not None
    x, y = point
    assert (y * y - x * x * x - 7) % field.P == 0
    z2 = z * z % field.P
    scaled = (x * z2 % field.P, y * z2 * z % field.P, z)
    raw, corrected, intermediates = verify_field_case(*scaled)
    rx, ry, rz = [field.decode(item[0]) for item in corrected]
    assert rz != 0
    inverse = pow(rz, -1, field.P)
    actual = (rx * inverse * inverse % field.P,
              ry * inverse * inverse * inverse % field.P)
    omega_point = (field.BETA * x % field.P, y)
    expected = point_add(point, (omega_point[0], -omega_point[1] % field.P))
    assert actual == expected
    return raw, intermediates


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--random-field", type=int, default=10_000)
    parser.add_argument("--random-points", type=int, default=32)
    args = parser.parse_args()
    if args.random_field < 0 or args.random_points < 0:
        parser.error("case counts must be nonnegative")
    assert 22 * C < field.P
    rng = random.Random(20261009)
    largest_coefficient_bits = 0
    largest_intermediate_bits = 0
    largest_t_coordinate_ratio = 0
    adjusted_quotients = 0
    boundary_floor_cases = 0
    boundary_floor_adjustments = 0
    for multiple in range(-20, 21):
        for offset in (-field.P, -1, 0, 1, field.P - 1, field.P):
            t = multiple * field.P + offset
            assert abs(t) < 22 * R2
            _, adjustment = shifted_floor(t)
            boundary_floor_cases += 1
            boundary_floor_adjustments += adjustment != 0
    field_cases = [(0, 0, 1), (1, 1, 1), (field.P - 1, field.P - 1, field.P - 1)]
    field_cases.extend(tuple(rng.randrange(field.P) for _ in range(3))
                       for _ in range(args.random_field))
    for x, y, z in field_cases:
        raw, corrected, intermediates = verify_field_case(x, y, z)
        largest_coefficient_bits = max(largest_coefficient_bits,
                                       *(abs(c).bit_length() for pair in raw for c in pair))
        largest_intermediate_bits = max(largest_intermediate_bits,
                                        *(abs(c).bit_length() for pair in intermediates for c in pair))
        assert all(abs(c) < 33 * field.R for pair in intermediates for c in pair)
        assert all(abs(c) < 22 * field.R for pair in raw for c in pair)
        for value, (_, _, adjustments) in zip(raw, corrected):
            t = field.product(value, field.conjugate(field.PI))
            largest_t_coordinate_ratio = max(largest_t_coordinate_ratio,
                                             *(abs(c) // R2 for c in t))
            adjusted_quotients += sum(a != 0 for a in adjustments)
    point_cases = [GENERATOR, point_add(GENERATOR, GENERATOR)]
    point_cases.extend(point_multiply(rng.randrange(1, ORDER))
                       for _ in range(args.random_points))
    for point in point_cases:
        z = rng.randrange(1, field.P)
        raw, intermediates = verify_point_case(point, z)
        largest_coefficient_bits = max(largest_coefficient_bits,
                                       *(abs(c).bit_length() for pair in raw for c in pair))
        largest_intermediate_bits = max(largest_intermediate_bits,
                                        *(abs(c).bit_length() for pair in intermediates for c in pair))
        assert all(abs(c) < 33 * field.R for pair in intermediates for c in pair)
        assert all(abs(c) < 22 * field.R for pair in raw for c in pair)
    print(json.dumps({
        "schema": 1, "status": "passed", "seed": 20261009,
        "field_cases": len(field_cases), "point_cases": len(point_cases),
        "raw_tau_montgomery_products": 5, "final_balances": 3,
        "largest_raw_coefficient_bits": largest_coefficient_bits,
        "largest_intermediate_coefficient_bits": largest_intermediate_bits,
        "largest_t_coordinate_floor_ratio": largest_t_coordinate_ratio,
        "shift_quotient_adjustments": adjusted_quotients,
        "boundary_floor_cases": boundary_floor_cases,
        "boundary_floor_adjustments": boundary_floor_adjustments,
        "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "reference_sha256": hashlib.sha256(Path(field.__file__).read_bytes()).hexdigest(),
    }, sort_keys=True))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""End-to-end 256-bit tau-adic scalar multiplication correctness prototype.

Run with /Volumes/SSD990/cryptanalysis/sage -python validate_scalar.py.
The evaluator is explicit Jacobian arithmetic; Sage scalar multiplication
is used only as an independent expected result.
"""

import hashlib
import json
import sys
from pathlib import Path

from sage.all import EllipticCurve, GF


HERE = Path(__file__).resolve().parent
FORMULAS = HERE.parent / "prime-j0-secp256k1-pair" / "validate.py"
sys.path.insert(0, str(FORMULAS.parent))
from validate import GX, GY, N, P, affine, jac_tau_pair  # noqa: E402


LABEL = "prime-j0-secp256k1-full-scalar-20261007-v1"
BASES = 4
SCALARS_PER_BASE = 8
# Coordinates in the Z[tau] basis, with tau = 1 - omega.
# The final two entries are sign and omega exponent.
UNIT_DIGITS = {
    0: ((0, 0, 0, 0),),
    1: ((1, 0, 1, 0), (1, -1, 1, 1), (-2, 1, 1, 2)),
    2: ((-1, 0, -1, 0), (-1, 1, -1, 1), (2, -1, -1, 2)),
}


def eisenstein_norm(a, b):
    return a * a + 3 * a * b + 3 * b * b


def round_div(numerator, denominator):
    assert denominator
    if denominator < 0:
        numerator, denominator = -numerator, -denominator
    if numerator < 0:
        return -((-numerator + denominator // 2) // denominator)
    return (numerator + denominator // 2) // denominator


def gauss_reduce(first, second):
    first, second = tuple(first), tuple(second)
    while True:
        if second[0] ** 2 + second[1] ** 2 < first[0] ** 2 + first[1] ** 2:
            first, second = second, first
        multiple = round_div(first[0] * second[0] + first[1] * second[1],
                             first[0] ** 2 + first[1] ** 2)
        if multiple == 0:
            return first, second
        second = (second[0] - multiple * first[0],
                  second[1] - multiple * first[1])


def short_representative(scalar, lambda_tau, basis):
    first, second = basis
    determinant = first[0] * second[1] - first[1] * second[0]
    assert abs(determinant) == N
    center_first = round_div(scalar * second[1], determinant)
    center_second = round_div(-scalar * first[1], determinant)
    options = []
    for offset_first in range(-2, 3):
        for offset_second in range(-2, 3):
            u, v = center_first + offset_first, center_second + offset_second
            a = scalar - u * first[0] - v * second[0]
            b = -u * first[1] - v * second[1]
            assert (a + b * lambda_tau - scalar) % N == 0
            options.append((eisenstein_norm(a, b), max(abs(a), abs(b)), a, b))
    _, _, a, b = min(options)
    return a, b


def recode(a, b):
    original = a, b
    digits = []
    while a or b:
        if len(digits) >= 512:
            raise ValueError("tau-adic recoding did not terminate")
        before_norm = eisenstein_norm(a, b)
        digit = min(UNIT_DIGITS[a % 3],
                    key=lambda item: eisenstein_norm(a - item[0], b - item[1]))
        reduced_a, reduced_b = a - digit[0], b - digit[1]
        assert reduced_a % 3 == 0
        # tau*(u + v*tau) = -3v + (u + 3v)*tau.
        a, b = reduced_b + reduced_a, -(reduced_a // 3)
        assert eisenstein_norm(a, b) < before_norm
        digits.append(digit)
    rebuilt_a = rebuilt_b = 0
    for digit_a, digit_b, _, _ in reversed(digits):
        rebuilt_a, rebuilt_b = -3 * rebuilt_b + digit_a, (
            rebuilt_a + 3 * rebuilt_b + digit_b)
    assert (rebuilt_a, rebuilt_b) == original
    return digits


def jac_double(jac):
    x, y, z = jac
    if z == 0 or y == 0:
        return 0, x.parent()(1), x.parent()(0)
    a, b = x**2, y**2
    c = b**2
    d = 2 * ((x + b)**2 - a - c)
    e = 3 * a
    rx = e**2 - 2 * d
    return rx, e * (d - rx) - 8 * c, 2 * y * z


def jac_add_mixed(jac, point):
    x, y, z = jac
    qx, qy = point
    if z == 0:
        return qx, qy, qx.parent()(1)
    zz = z**2
    u, s = qx * zz, qy * z * zz
    h, v = u - x, s - y
    if h == 0:
        return jac_double(jac) if v == 0 else (0, x.parent()(1), x.parent()(0))
    hh = h**2
    hhh, xhh = h * hh, x * hh
    rx = v**2 - hhh - 2 * xhh
    return rx, v * (xhh - rx) - y * hhh, z * h


def jac_tau_scaled(jac, z_constant):
    x, y, z = jac
    if z == 0 or x == 0:
        return 0, x.parent()(1), x.parent()(0)
    x3 = x**3
    rx = 4 * y**2 - 3 * x3
    return rx, y * (3 * x3 - 2 * rx), z_constant * x * z


def free_gauge(power, last):
    return min(range(3), key=lambda gauge:
               ((power + gauge) % 3 != 0) + (last and gauge != 0))


def paired_gauge(current, power, last):
    preferred = current if power is None else free_gauge(power, last)
    best_cost, best_gauge = 10, 0
    for gauge in range(3):
        change = (gauge - current) % 3
        cost = (change != 2)
        if power is not None:
            cost += (power + gauge) % 3 != 0
            cost += last and gauge != 0
        if cost < best_cost or cost == best_cost and gauge == preferred:
            best_cost, best_gauge = cost, gauge
    return best_gauge


def evaluate(curve, base, digits, beta):
    field = beta.parent()
    jac = field(0), field(1), field(0)
    counts = {"tau_steps": 0, "tau_pairs": 0, "cheap_z_pairs": 0,
              "mixed_adds": 0, "digit_rotations": 0, "final_rotations": 0}
    if not digits:
        return curve(0), counts
    lowest_nonzero = next(i for i, digit in enumerate(digits) if digit[2])
    gauge = 0
    index = len(digits) - 1
    while index >= 0:
        digit = digits[index]
        pair = jac[2] != 0 and digit[2] == 0 and index > 0
        if pair:
            index -= 1
            digit = digits[index]
        power = digit[3] if digit[2] else None
        last = index == lowest_nonzero
        next_gauge = (paired_gauge(gauge, power, last) if pair else
                      free_gauge(power, last) if power is not None else gauge)
        if jac[2] != 0:
            change = (next_gauge - gauge) % 3
            if pair:
                jac = jac_tau_pair(jac, beta, change)
                counts["tau_steps"] += 2
                counts["tau_pairs"] += 1
                counts["cheap_z_pairs"] += change == 2
            else:
                jac = jac_tau_scaled(jac, (1 - beta) * beta**change)
                counts["tau_steps"] += 1
        if power is not None or pair:
            gauge = next_gauge
        if power is not None:
            rotation = (power + gauge) % 3
            point = beta**rotation * base[0], digit[2] * base[1]
            jac = jac_add_mixed(jac, point)
            counts["mixed_adds"] += 1
            counts["digit_rotations"] += rotation != 0
        index -= 1
    if jac[2] != 0 and gauge:
        jac = beta ** ((3 - gauge) % 3) * jac[0], jac[1], jac[2]
        counts["final_rotations"] += 1
    return affine(curve, jac), counts


def deterministic_scalar(label):
    return int.from_bytes(hashlib.sha256(label.encode()).digest(), "big") % N


def main():
    field = GF(P)
    curve = EllipticCurve(field, [0, 7])
    generator = curve(GX, GY)
    assert N * generator == curve(0)
    beta = field(2) ** ((P - 1) // 3)
    omega_generator = curve(beta * generator[0], generator[1])
    lambda_omega = None
    for seed in range(2, 100):
        root = pow(seed, (N - 1) // 3, N)
        if root == 1:
            continue
        for candidate in (root, root * root % N):
            if candidate * generator == omega_generator:
                lambda_omega = candidate
                break
        if lambda_omega is not None:
            break
    assert lambda_omega is not None
    lambda_tau = (1 - lambda_omega) % N
    basis = gauss_reduce((N, 0), (-lambda_tau, 1))
    assert abs(basis[0][0] * basis[1][1] - basis[0][1] * basis[1][0]) == N

    # The one-digit and empty-position slice of the C gauge table.
    expected_pair_gauge = (
        ((0, 0), (2, 2), (1, 0), (2, 2)),
        ((0, 0), (2, 0), (1, 0), (0, 0)),
        ((0, 0), (2, 0), (1, 1), (1, 1)),
    )
    gauge_policy_checks = 0
    for current in range(3):
        for pattern in range(4):
            for last in range(2):
                power = None if pattern == 3 else pattern
                assert paired_gauge(current, power, last) == (
                    expected_pair_gauge[current][pattern][last])
                gauge_policy_checks += 1

    small_grid_checks = 0
    for small_a in range(-20, 21):
        for small_b in range(-20, 21):
            recode(small_a, small_b)
            small_grid_checks += 1

    cases = []
    totals = {"tau_steps": 0, "tau_pairs": 0, "cheap_z_pairs": 0,
              "mixed_adds": 0, "digit_rotations": 0, "final_rotations": 0}
    for base_index in range(BASES):
        base_scalar = 1 if base_index == 0 else deterministic_scalar(
            f"{LABEL}:base:{base_index}") or 1
        base = base_scalar * generator
        scalar_inputs = [0, 1, 2, N - 1] + [deterministic_scalar(
            f"{LABEL}:scalar:{base_index}:{j}") for j in range(SCALARS_PER_BASE - 4)]
        for scalar_index, scalar in enumerate(scalar_inputs):
            a, b = short_representative(scalar, lambda_tau, basis)
            digits = recode(a, b)
            actual, counts = evaluate(curve, base, digits, beta)
            expected = scalar * base
            assert actual == expected, (base_index, scalar_index, scalar)
            assert (a + b * lambda_tau - scalar) % N == 0
            for name in totals:
                totals[name] += counts[name]
            cases.append({
                "base_index": base_index, "scalar_index": scalar_index,
                "base_scalar_hex": f"{base_scalar:064x}",
                "scalar_hex": f"{scalar:064x}",
                "lattice_a_hex": hex(a), "lattice_b_hex": hex(b),
                "recode_length": len(digits),
                "recode_weight": sum(digit[2] != 0 for digit in digits),
                "counts": counts,
                "result_x_hex": None if actual == curve(0) else f"{int(actual[0]):064x}",
                "result_y_hex": None if actual == curve(0) else f"{int(actual[1]):064x}",
                "verified": True,
            })

    result = {
        "schema": 1, "kind": "full-256-bit-tau-adic-scalar-correctness",
        "label": LABEL, "curve": "secp256k1", "field_modulus_hex": f"{P:064x}",
        "subgroup_order_hex": f"{N:064x}",
        "lambda_omega_hex": f"{lambda_omega:064x}",
        "lambda_tau_hex": f"{lambda_tau:064x}",
        "lattice_basis": [[str(value) for value in row] for row in basis],
        "cases": cases, "totals": totals,
        "small_grid_checks": small_grid_checks,
        "gauge_policy_checks": gauge_policy_checks,
        "max_recode_length": max(case["recode_length"] for case in cases),
        "max_lattice_component_bits": max(
            abs(int(case[key], 16)).bit_length() for case in cases
            for key in ("lattice_a_hex", "lattice_b_hex")),
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "formula_source_sha256": hashlib.sha256(FORMULAS.read_bytes()).hexdigest(),
        "verified": True, "cpu_speedup_claim": None,
    }
    path = HERE / "result.json"
    if path.exists():
        raise SystemExit("result exists; refusing overwrite")
    path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"verified": True, "cases": len(cases),
                      "max_recode_length": result["max_recode_length"],
                      "totals": totals}, sort_keys=True))


if __name__ == "__main__":
    main()

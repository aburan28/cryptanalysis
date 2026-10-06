#!/usr/bin/env python3
"""Exact Eisenstein representative search; operation counts are diagnostics."""

import argparse
import hashlib
import json
from math import isqrt
from pathlib import Path
import random
import statistics


SEEDS = ((1, 0), (2, 0), (4, 0), (1, 1), (2, 2),
         (1, 2), (2, 4), (2, 1), (1, -2))
ORDERS = (51131959441, 157632877033, 42111239174233)
PANEL_SEED = 20261004
PANEL_SIZE = 10000
WEIGHTS = {"triple": 10, "mixed_add": 16, "unit_rotation": 1}


def nearest_quotient(a, b):
    if b < 0:
        a, b = -a, -b
    return -((-a + b // 2) // b) if a < 0 else (a + b // 2) // b


def lattice(n, lam):
    r0, r1, t0, t1 = n, lam, 0, 1
    while r1 > isqrt(n):
        q = r0 // r1
        r0, r1, t0, t1 = r1, r0 - q * r1, t1, t0 - q * t1
        if not r1:
            raise ValueError("degenerate lattice")
    v1, v2 = (r1, -t1), (r0, -t0)
    det = v1[0] * v2[1] - v2[0] * v1[1]
    if abs(det) != n:
        raise ValueError("lattice determinant does not match subgroup order")
    return v1, v2, det


def representatives(n, lam, k, radius=2):
    v1, v2, det = lattice(n, lam)
    u0 = nearest_quotient(k * v2[1], det)
    v0 = nearest_quotient(-k * v1[1], det)
    lam_tau = (1 - lam) % n
    for du in range(-radius, radius + 1):
        for dv in range(-radius, radius + 1):
            u, v = u0 + du, v0 + dv
            x = k - u * v1[0] - v * v2[0]
            y = -u * v1[1] - v * v2[1]
            a, b = x + y, -y  # x+y*omega = (x+y)-y*tau
            if (a + b * lam_tau - k) % n:
                raise AssertionError("representative changed the scalar")
            yield (abs(x) + abs(y), a, b)


def digit_table():
    table = {}
    for seed, (a0, b0) in enumerate(SEEDS):
        a, b = a0, b0
        for power in range(3):
            for sign in (-1, 1):
                x, y = sign * a, sign * b
                slot = (x % 9, y % 9)
                if slot[0] % 3 == 0 or slot in table:
                    raise AssertionError("invalid tau4 digit table")
                table[slot] = (x, y, seed, power, sign)
            a, b = a + 3 * b, -a - 2 * b  # multiply by omega
    if len(table) != 54:
        raise AssertionError("tau4 table must cover 54 unit residue classes")
    return table


TABLE = digit_table()


def recode(a, b):
    digits = []
    while a or b:
        if len(digits) >= 256:
            raise ValueError("tau expansion did not terminate")
        digit = None
        if a % 3:
            digit = TABLE[(a % 9, b % 9)]
            a -= digit[0]
            b -= digit[1]
        digits.append(digit)
        if a % 3:
            raise AssertionError("digit did not make tau division exact")
        a, b = a + b, -a // 3
    for low, high in zip(digits[::2], digits[1::2]):
        if low is not None and high is not None:
            raise AssertionError("width-4 pair has two nonzero digits")
    return digits


def expand(digits):
    """Recover (a,b) from least-significant-first tau digits exactly."""
    a = b = 0
    for digit in reversed(digits):
        a, b = -3 * b, a + 3 * b  # tau*(a+b*tau)
        if digit is not None:
            a += digit[0]
            b += digit[1]
    return a, b


def metrics(digits):
    nonzero = [(i, d) for i, d in enumerate(digits) if d is not None]
    if not nonzero:
        return {"triples": 0, "mixed_adds": 0, "unit_rotations": 0,
                "weighted_cost": 0, "digit_length": 0}
    triples = max(i // 2 for i, _ in nonzero)
    rotations = sum((d[3] + i // 2 % 3) % 3 != 0 for i, d in nonzero)
    cost = (WEIGHTS["triple"] * triples +
            WEIGHTS["mixed_add"] * len(nonzero) +
            WEIGHTS["unit_rotation"] * rotations)
    return {"triples": triples, "mixed_adds": len(nonzero),
            "unit_rotations": rotations, "weighted_cost": cost,
            "digit_length": len(digits)}


def select(n, lam, k):
    choices = []
    for l1, a, b in representatives(n, lam, k):
        digits = recode(a, b)
        if expand(digits) != (a, b):
            raise AssertionError("recode did not preserve representative")
        choices.append((l1, a, b, digits, metrics(digits)))
    baseline = min(choices, key=lambda c: c[0])
    optimized = min(choices, key=lambda c: (c[4]["weighted_cost"], c[0]))
    return baseline, optimized


def point_add(p, q, modulus, b):
    if p is None:
        return q
    if q is None:
        return p
    x1, y1 = p
    x2, y2 = q
    if x1 == x2 and (y1 + y2) % modulus == 0:
        return None
    slope = ((3 * x1 * x1) * pow(2 * y1, -1, modulus)
             if p == q else (y2 - y1) * pow((x2 - x1) % modulus, -1, modulus)) % modulus
    x3 = (slope * slope - x1 - x2) % modulus
    y3 = (slope * (x1 - x3) - y1) % modulus
    assert (y3 * y3 - x3 * x3 * x3 - b) % modulus == 0
    return x3, y3


def point_mul(p, k, modulus, b):
    out = None
    while k:
        if k & 1:
            out = point_add(out, p, modulus, b)
        p = point_add(p, p, modulus, b)
        k >>= 1
    return out


def toy_instance(b, expected_order):
    modulus = 97
    beta = next(x for x in range(2, modulus) if pow(x, 3, modulus) == 1)
    for x in range(modulus):
        for y in range(modulus):
            if (y * y - x * x * x - b) % modulus:
                continue
            p = (x, y)
            q = None
            for order in range(1, modulus + 2 * isqrt(modulus) + 2):
                q = point_add(q, p, modulus, b)
                if q is None:
                    break
            if order != expected_order or q is not None:
                continue
            omega_p = (beta * x % modulus, y)
            for lam in range(1, order):
                if point_mul(p, lam, modulus, b) == omega_p:
                    if (lam * lam + lam + 1) % order == 0:
                        return modulus, b, p, order, lam, beta
    raise AssertionError("toy j=0 subgroup not found")


def selftest():
    reports = []
    for b, expected_order in ((2, 13), (10, 103)):
        modulus, _, p, order, lam, beta = toy_instance(b, expected_order)
        rng = random.Random(719 + b)
        checks = list(range(order)) + [rng.randrange(order) for _ in range(1000)]
        tau_p = point_add(p, (beta * p[0] % modulus, -p[1] % modulus), modulus, b)
        for k in checks:
            want = point_mul(p, k, modulus, b)
            for choice in select(order, lam, k):
                acc = None
                for digit in reversed(choice[3]):
                    omega_acc = None if acc is None else (beta * acc[0] % modulus, acc[1])
                    neg_omega = None if omega_acc is None else (omega_acc[0], -omega_acc[1] % modulus)
                    acc = point_add(acc, neg_omega, modulus, b)  # tau=1-omega
                    if digit is not None:
                        da, db = digit[:2]
                        p1 = point_mul(p, abs(da), modulus, b)
                        p2 = point_mul(tau_p, abs(db), modulus, b)
                        if da < 0 and p1 is not None:
                            p1 = (p1[0], -p1[1] % modulus)
                        if db < 0 and p2 is not None:
                            p2 = (p2[0], -p2[1] % modulus)
                        acc = point_add(acc, point_add(p1, p2, modulus, b), modulus, b)
                if acc != want:
                    raise AssertionError((k, choice[1:3], acc, want))
        reports.append({"field": modulus, "curve_b": b, "subgroup_order": order,
                        "checks": len(checks)})
    print(json.dumps({"controls": reports, "representatives_per_scalar": 25,
                      "status": "pass"}, sort_keys=True))


def omega_eigenvalues(order):
    for seed in range(2, 100):
        lam = pow(seed, (order - 1) // 3, order)
        if lam != 1 and (lam * lam + lam + 1) % order == 0:
            return tuple(sorted((lam, lam * lam % order)))
    raise ValueError("no primitive cube root found modulo subgroup order")


def panel(output):
    rng = random.Random(PANEL_SEED)
    reports = []
    for order in ORDERS:
        scalars = [0, 1, 2, 3, order - 2, order - 1]
        scalars.extend(rng.randrange(order) for _ in range(PANEL_SIZE))
        for lam in omega_eigenvalues(order):
            differences = []
            counts = {"better": 0, "tie": 0, "worse": 0}
            baseline_costs = []
            candidate_costs = []
            for k in scalars:
                baseline, optimized = select(order, lam, k)
                base_cost = baseline[4]["weighted_cost"]
                opt_cost = optimized[4]["weighted_cost"]
                delta = base_cost - opt_cost
                differences.append(delta)
                counts["better" if delta > 0 else "tie" if delta == 0 else "worse"] += 1
                baseline_costs.append(base_cost)
                candidate_costs.append(opt_cost)
            reports.append({"order": order, "omega_eigenvalue": lam,
                            "scalars": len(scalars), "selection_counts": counts,
                            "mean_baseline_cost": statistics.mean(baseline_costs),
                            "mean_candidate_cost": statistics.mean(candidate_costs),
                            "median_saved_weight": statistics.median(differences),
                            "total_saved_weight": sum(differences)})
    result = {"schema": 1, "status": "operation_model_only",
              "seed": PANEL_SEED, "random_scalars_per_order": PANEL_SIZE,
              "weights": WEIGHTS, "reports": reports,
              "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("selftest", "panel"))
    parser.add_argument("--output", type=Path, default=Path(__file__).with_name("panel.json"))
    args = parser.parse_args()
    if args.action == "selftest":
        selftest()
    else:
        panel(args.output)


if __name__ == "__main__":
    main()

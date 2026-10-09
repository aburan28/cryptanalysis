#!/usr/bin/env python3
"""Replay paired width-two and width-three scalar paths without CPU timings."""

import argparse
import hashlib
import json
from pathlib import Path
import random
import subprocess

import lazy_tau_screen as curve
from check_eisenstein_scalar_fixed import LAMBDA_TAU, affine_from_native


HERE = Path(__file__).resolve().parent


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def replay(binary, mode, scalars):
    request = "".join(format(scalar, "x") + "\n" for scalar in scalars)
    process = subprocess.run(
        [str(binary), mode], input=request, text=True,
        capture_output=True, check=True, timeout=120,
    )
    rows = [json.loads(line) for line in process.stdout.splitlines()]
    assert len(rows) == len(scalars)
    return rows


def audit_small_state_termination():
    def omega(pair):
        a, b = pair
        return a + 3 * b, -a - 2 * b

    def norm(pair):
        a, b = pair
        return a * a + 3 * a * b + 3 * b * b

    digits = []
    for base in ((1, 0), (2, 0), (1, 1)):
        for _ in range(3):
            digits += [base, (-base[0], -base[1])]
            base = omega(base)
    residues = {(a % 9, b % 3): (a, b) for a, b in digits}
    assert len(residues) == 18
    terminal = set(digits)
    small = [(a, b) for a in range(-10, 11) for b in range(-10, 11)
             if norm((a, b)) <= 13]
    assert len(small) == 55
    max_steps = max_successor_norm = 0
    for start in small:
        state = start
        seen = set()
        while state != (0, 0) and state not in terminal:
            assert state not in seen, (start, state)
            seen.add(state)
            digit = ((0, 0) if state[0] % 3 == 0
                     else residues[(state[0] % 9, state[1] % 3)])
            a, b = state[0] - digit[0], state[1] - digit[1]
            assert a % 3 == 0
            state = a + b, -a // 3
            max_successor_norm = max(max_successor_norm, norm(state))
        max_steps = max(max_steps, len(seen))
    assert max_steps == 3 and max_successor_norm == 9
    return {"states": len(small), "max_steps": max_steps,
            "max_successor_norm": max_successor_norm}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path,
                        default=HERE / "target/release/eisenstein_fixed")
    parser.add_argument("--fixture", type=Path,
                        default=HERE / "eisenstein-pair-fixture.json")
    parser.add_argument("--random-scalars", type=int, default=128)
    args = parser.parse_args()
    if args.random_scalars < 0:
        parser.error("random-scalars must be nonnegative")
    binary = args.binary.resolve(strict=True)
    fixture_path = args.fixture.resolve(strict=True)
    fixture = json.loads(fixture_path.read_text())
    assert fixture["schema"] == 1 and len(fixture["cases"]) == 86
    small_state_audit = audit_small_state_termination()
    rng = random.Random(20261012)
    scalars = [int(row["scalar_hex"], 16) for row in fixture["cases"]]
    scalars += [rng.randrange(1, curve.ORDER) for _ in range(args.random_scalars)]
    w2 = replay(binary, "--scalar-w2", scalars)
    w3 = replay(binary, "--scalar-w3", scalars)
    sums = {"w2_tau_steps": 0, "w2_additions": 0,
            "w3_tau_steps": 0, "w3_mixed_additions": 0,
            "w3_cached_additions": 0}
    for index, (scalar, row2, row3) in enumerate(zip(scalars, w2, w3)):
        expected = curve.point_multiply(scalar % curve.ORDER)
        assert row2["radix"] == "unit-w2" and row3["radix"] == "orbit-w3"
        assert row2["representative"] == row3["representative"]
        a, b = map(int, row3["representative"])
        assert (a + b * LAMBDA_TAU - scalar) % curve.ORDER == 0
        assert affine_from_native(row2["point"]) == expected, (index, "w2")
        assert affine_from_native(row3["point"]) == expected, (index, "w3")
        assert sum(row3["orbit_counts"]) == row3["nonzero_digits"]
        if index < len(fixture["cases"]):
            frozen = fixture["cases"][index]
            assert expected == (int(frozen["expected_x_hex"], 16),
                                int(frozen["expected_y_hex"], 16))
            sums["w2_tau_steps"] += row2["tau_steps"]
            sums["w2_additions"] += row2["nonzero_digits"]
            sums["w3_tau_steps"] += row3["tau_steps"]
            sums["w3_mixed_additions"] += row3["orbit_counts"][0]
            sums["w3_cached_additions"] += sum(row3["orbit_counts"][1:])
    # Five tau products, eleven mixed-add products, fourteen cached-add
    # products, and 7+11+4 setup products per width-three scalar.
    w2_products = 5 * sums["w2_tau_steps"] + 11 * sums["w2_additions"]
    w3_products = (5 * sums["w3_tau_steps"]
                   + 11 * sums["w3_mixed_additions"]
                   + 14 * sums["w3_cached_additions"]
                   + 22 * len(fixture["cases"]))
    print(json.dumps({
        "schema": 1, "status": "passed", "frozen_cases": len(fixture["cases"]),
        "random_cases": args.random_scalars,
        "verified_outputs": 2 * len(scalars),
        "small_state_audit": small_state_audit,
        "frozen_counts": sums,
        "w2_field_product_proxy": w2_products,
        "w3_field_product_proxy": w3_products,
        "proxy_saving": w2_products - w3_products,
        "binary_sha256": digest(binary),
        "fixture_sha256": digest(fixture_path),
        "checker_sha256": digest(Path(__file__)),
        "field_reference_sha256": digest(HERE / "eisenstein_montgomery.py"),
        "curve_reference_sha256": digest(HERE / "lazy_tau_screen.py"),
    }, sort_keys=True))


if __name__ == "__main__":
    main()

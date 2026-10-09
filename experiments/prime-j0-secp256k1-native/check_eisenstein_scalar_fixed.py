#!/usr/bin/env python3
"""Independently replay native Eisenstein tau scalar multiplication on secp256k1."""

import argparse
import hashlib
import json
from pathlib import Path
import random
import subprocess

import eisenstein_montgomery as field
import lazy_tau_screen as curve


LAMBDA_TAU = int(
    "ac9c52b33fa3cf1f5ad9e3fd77ed9ba4a880b9fc8ec739c2e0cfc810b51283d0", 16
)


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def scalar_text(scalar):
    return ("-" if scalar < 0 else "") + format(abs(scalar), "x")


def affine_from_native(point):
    if point is None:
        return None
    assert len(point) == 3
    pairs = [tuple(map(int, pair)) for pair in point]
    for pair in pairs:
        assert field.balance(pair)[0] == pair, ("not balanced", pair)
    x, y, z = (field.decode(pair) for pair in pairs)
    assert z != 0
    inverse = pow(z, -1, field.P)
    affine = (x * inverse * inverse % field.P,
              y * inverse * inverse * inverse % field.P)
    assert (affine[1] * affine[1] - affine[0] ** 3 - 7) % field.P == 0
    return affine


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    directory = Path(__file__).resolve().parent
    parser.add_argument("--binary", type=Path,
                        default=directory / "target/release/eisenstein_fixed")
    parser.add_argument("--random-scalars", type=int, default=48)
    args = parser.parse_args()
    if args.random_scalars < 0:
        parser.error("random-scalars must be nonnegative")
    binary = args.binary.resolve(strict=True)
    rng = random.Random(20261011)
    n = curve.ORDER
    scalars = [0, 1, -1, 2, -2, 3, 4, 5, 7, 8, 9, 16, 27,
               n - 1, n, n + 1, 2 * n - 1, 2 * n + 1,
               1 << 64, (1 << 128) - 1, 1 << 128, (1 << 128) + 1,
               1 << 255, (1 << 256) - 1, LAMBDA_TAU]
    edge_count = len(scalars)
    scalars.extend(rng.randrange(n) for _ in range(args.random_scalars))
    request = "".join(scalar_text(scalar) + "\n" for scalar in scalars)
    process = subprocess.run([str(binary), "--scalar"], input=request,
                             text=True, capture_output=True, check=True,
                             timeout=max(120, 10 * len(scalars)))
    rows = [json.loads(line) for line in process.stdout.splitlines()]
    assert len(rows) == len(scalars), (len(rows), len(scalars))
    max_steps = max_nonzero = 0
    total_steps = total_nonzero = 0
    random_steps = random_nonzero = 0
    for index, (scalar, row) in enumerate(zip(scalars, rows)):
        a, b = map(int, row["representative"])
        assert (a + b * LAMBDA_TAU - scalar) % n == 0, index
        assert max(abs(a), abs(b)).bit_length() <= 129, index
        steps, nonzero = row["tau_steps"], row["nonzero_digits"]
        assert 0 <= nonzero <= steps <= 512, (index, steps, nonzero)
        actual = affine_from_native(row["point"])
        expected = curve.point_multiply(scalar % n)
        assert actual == expected, (index, scalar, actual, expected)
        max_steps = max(max_steps, steps)
        max_nonzero = max(max_nonzero, nonzero)
        total_steps += steps
        total_nonzero += nonzero
        if index >= edge_count:
            random_steps += steps
            random_nonzero += nonzero
    print(json.dumps({
        "schema": 1, "status": "passed", "seed": 20261011,
        "scalar_cases": len(scalars), "random_scalars": args.random_scalars,
        "max_tau_steps": max_steps, "max_nonzero_digits": max_nonzero,
        "total_tau_steps": total_steps, "total_nonzero_digits": total_nonzero,
        "random_tau_steps": random_steps, "random_nonzero_digits": random_nonzero,
        "binary_sha256": sha256(binary),
        "verifier_sha256": sha256(Path(__file__)),
        "field_reference_sha256": sha256(directory / "eisenstein_montgomery.py"),
        "curve_reference_sha256": sha256(directory / "lazy_tau_screen.py"),
    }, sort_keys=True))


if __name__ == "__main__":
    main()

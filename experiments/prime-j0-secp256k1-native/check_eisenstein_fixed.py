#!/usr/bin/env python3
"""Replay fixed-width Eisenstein operations against the exact Python reference."""

import argparse
import hashlib
import json
from pathlib import Path
import random
import subprocess

import eisenstein_montgomery as reference


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    directory = Path(__file__).resolve().parent
    parser.add_argument("--binary", type=Path,
                        default=directory / "target/release/eisenstein_fixed")
    parser.add_argument("--random-pairs", type=int, default=1_000)
    args = parser.parse_args()
    if args.random_pairs < 0:
        parser.error("random-pairs must be nonnegative")
    binary = args.binary.resolve(strict=True)

    rng = random.Random(20261009)
    edges = [0, 1, 2, 3, reference.P - 1, reference.P - 2,
             reference.BETA, reference.R - 1, reference.R,
             reference.R + 1, reference.P // 2]
    cases = [(x, y) for x in edges for y in edges]
    cases.extend((rng.randrange(reference.P), rng.randrange(reference.P))
                 for _ in range(args.random_pairs))
    encoded = [(reference.encode(x), reference.encode(y)) for x, y in cases]
    request = "".join(f"{a[0]} {a[1]} {b[0]} {b[1]}\n" for a, b in encoded)
    process = subprocess.run([str(binary)], input=request, text=True,
                             capture_output=True, check=True, timeout=120)
    rows = [json.loads(line) for line in process.stdout.splitlines()]
    assert len(rows) == len(cases), (len(rows), len(cases))
    for index, ((x, y), (a, b), row) in enumerate(zip(cases, encoded, rows)):
        expected = {
            "mul": reference.multiply(a, b),
            "add": reference.balance(reference.add(a, b))[0],
            "sub": reference.balance(reference.sub(a, b))[0],
            "omega": reference.omega(a),
            "tau_constant": reference.balance(reference.one_minus_omega(a))[0],
        }
        for operation, want in expected.items():
            got = tuple(map(int, row[operation]))
            assert got == want, (index, operation, got, want)
        assert reference.decode(tuple(map(int, row["mul"]))) == x * y % reference.P
    print(json.dumps({
        "schema": 1,
        "status": "passed",
        "seed": 20261009,
        "edge_pairs": len(edges) ** 2,
        "random_pairs": args.random_pairs,
        "cases": len(cases),
        "operations_per_case": 5,
        "binary_sha256": sha256(binary),
        "reference_sha256": sha256(directory / "eisenstein_montgomery.py"),
        "verifier_sha256": sha256(Path(__file__)),
    }, sort_keys=True))


if __name__ == "__main__":
    main()

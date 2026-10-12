#!/usr/bin/env python3
"""Replay native deferred-normalization tau against field and group oracles."""

import argparse
import hashlib
import json
from pathlib import Path
import random
import subprocess

import eisenstein_montgomery as field
import lazy_tau_screen as control


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    directory = Path(__file__).resolve().parent
    parser.add_argument("--binary", type=Path,
                        default=directory / "target/release/eisenstein_fixed")
    parser.add_argument("--random-field", type=int, default=2_000)
    parser.add_argument("--random-points", type=int, default=32)
    args = parser.parse_args()
    if args.random_field < 0 or args.random_points < 0:
        parser.error("case counts must be nonnegative")
    binary = args.binary.resolve(strict=True)
    rng = random.Random(20261010)

    field_cases = [(0, 0, 1), (1, 1, 1),
                   (field.P - 1, field.P - 1, field.P - 1)]
    field_cases.extend(tuple(rng.randrange(field.P) for _ in range(3))
                       for _ in range(args.random_field))
    point_cases = [control.GENERATOR, control.point_add(control.GENERATOR, control.GENERATOR)]
    point_cases.extend(control.point_multiply(rng.randrange(1, control.ORDER))
                       for _ in range(args.random_points))
    cases = [(values, None) for values in field_cases]
    for point in point_cases:
        z = rng.randrange(1, field.P)
        z2 = z * z % field.P
        x, y = point
        cases.append(((x * z2 % field.P, y * z2 * z % field.P, z), point))

    encoded = [tuple(field.encode(x) for x in values) for values, _ in cases]
    request = "".join(" ".join(str(c) for pair in triples for c in pair) + "\n"
                      for triples in encoded)
    process = subprocess.run([str(binary), "--tau"], input=request, text=True,
                             capture_output=True, check=True, timeout=120)
    rows = [json.loads(line) for line in process.stdout.splitlines()]
    assert len(rows) == len(cases), (len(rows), len(cases))
    for index, ((values, point), triples, row) in enumerate(zip(cases, encoded, rows)):
        raw, _ = control.lazy_tau(*triples)
        expected = tuple(control.balance_shifted(x)[0] for x in raw)
        got = tuple(tuple(map(int, pair)) for pair in row["tau"])
        assert got == expected, (index, got, expected)
        x, y, z = values
        x3 = pow(x, 3, field.P)
        rx = (4 * y * y - 3 * x3) % field.P
        ry = y * (3 * x3 - 2 * rx) % field.P
        rz = (1 - field.BETA) * x * z % field.P
        decoded = tuple(field.decode(pair) for pair in got)
        assert decoded == (rx, ry, rz), (index, decoded, (rx, ry, rz))
        if point is not None:
            inverse = pow(rz, -1, field.P)
            affine = (rx * inverse * inverse % field.P,
                      ry * inverse * inverse * inverse % field.P)
            omega_point = (field.BETA * point[0] % field.P, point[1])
            expected_point = control.point_add(
                point, (omega_point[0], -omega_point[1] % field.P))
            assert affine == expected_point, (index, affine, expected_point)
    print(json.dumps({
        "schema": 1, "status": "passed", "seed": 20261010,
        "field_cases": len(field_cases), "point_cases": len(point_cases),
        "checked_tau_coordinates": 3 * len(cases),
        "binary_sha256": sha256(binary),
        "verifier_sha256": sha256(Path(__file__)),
        "reference_sha256": sha256(directory / "eisenstein_montgomery.py"),
        "lazy_screen_sha256": sha256(directory / "lazy_tau_screen.py"),
    }, sort_keys=True))


if __name__ == "__main__":
    main()

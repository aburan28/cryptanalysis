#!/usr/bin/env python3
"""Replay radix-943 and U14 on the frozen scalar law and independent points."""

import argparse
import hashlib
import json
from pathlib import Path
import random
import subprocess

from check_eisenstein_scalar_fixed import affine_from_native, scalar_text
import lazy_tau_screen as curve
from radix943_screen import ORDER, LAMBDA_TAU, RADIX, SEED, CASES


HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(binary, mode, scalars):
    process = subprocess.run(
        [str(binary), mode],
        input="".join(scalar_text(scalar) + "\n" for scalar in scalars),
        capture_output=True, text=True, check=True, timeout=1800,
    )
    rows = [json.loads(line) for line in process.stdout.splitlines()]
    assert len(rows) == len(scalars)
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("output exists")
    binary = args.binary.resolve(strict=True)
    screen = json.loads((HERE / "radix943-screen-result.json").read_text())
    assert screen["scalar_seed"] == SEED and screen["random_cases"] == CASES
    assert screen["radix"] == RADIX and screen["inequality_verified"]
    boundaries = [0, 1, 2, ORDER - 2, ORDER - 1]
    rng = random.Random(SEED)
    scalars = boundaries + [rng.getrandbits(256) % ORDER for _ in range(CASES)]
    input_digest = hashlib.sha256(b"".join(k.to_bytes(32, "big") for k in scalars)).hexdigest()
    assert input_digest == screen["scalar_input_sha256"]
    fixture = json.loads((HERE / "tau6-comb13-bench-fixture.json").read_text())
    assert len(fixture["cases"]) == 129
    fixture_start = len(scalars)
    scalars.extend(int(case["scalar_hex"], 16) for case in fixture["cases"])

    reference = run(binary, "--scalar-unit-orbit-windows-fixed", scalars)
    candidate = run(binary, "--scalar-unit-orbit-radix943-fixed", scalars)
    digest = hashlib.sha256()
    independent = 0
    sums = {"u14_additions": 0, "radix943_additions": 0}
    retained = candidate[0]["retained_bytes"]
    assert 138_723_624 <= retained < 140 * (1 << 20)
    for index, (k, old, new) in enumerate(zip(scalars, reference, candidate)):
        old_point = affine_from_native(old["point"])
        new_point = affine_from_native(new["point"])
        assert old_point == new_point, index
        assert new["retained_bytes"] == retained and new["tau_steps"] == 0
        assert 0 <= new["nonzero_digits"] <= 12
        a, b = map(int, new["representative"])
        assert (a + b * LAMBDA_TAU - k) % ORDER == 0
        if index < 5 or 5 <= index < 261:
            assert new_point == curve.point_multiply(k % ORDER), index
            independent += 1
        if index >= fixture_start:
            case = fixture["cases"][index - fixture_start]
            expected = None if case["expected_identity"] else (
                int(case["expected_x_hex"], 16), int(case["expected_y_hex"], 16))
            assert new_point == expected, index
        sums["u14_additions"] += old["nonzero_digits"]
        sums["radix943_additions"] += new["nonzero_digits"]
        digest.update(("identity" if new_point is None else
                       f"{new_point[0]:064x}:{new_point[1]:064x}").encode() + b"\n")

    result = {
        "schema": 1, "status": "passed", "cases": len(scalars),
        "screen_cases": fixture_start, "fixture_cases": len(fixture["cases"]),
        "independent_point_checks": independent,
        "scalar_input_sha256": input_digest,
        "point_digest_sha256": digest.hexdigest(),
        "retained_bytes": retained,
        "operation_totals": sums,
        "binary_sha256": sha(binary),
        "source_sha256": {name: sha(HERE / name) for name in (
            "src/bin/eisenstein_fixed.rs",
            "src/bin/eisenstein_fixed/unit_orbit_windows.rs")},
        "screen_sha256": sha(HERE / "radix943-screen-result.json"),
        "fixture_sha256": sha(HERE / "tau6-comb13-bench-fixture.json"),
        "verified_wall_time_ms": None,
    }
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: result[key] for key in (
        "status", "cases", "independent_point_checks", "retained_bytes", "operation_totals")},
        sort_keys=True))


if __name__ == "__main__":
    main()

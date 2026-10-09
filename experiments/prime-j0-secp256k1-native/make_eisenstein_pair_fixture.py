#!/usr/bin/env python3
"""Freeze exact fixed-generator scalar points for paired native replay."""

import hashlib
import json
from pathlib import Path
import random

import lazy_tau_screen as curve


HERE = Path(__file__).resolve().parent
TARGET = HERE / "eisenstein-pair-fixture.json"
SEED = 20261009


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def scalar_hex(value):
    return ("-" if value < 0 else "") + format(abs(value), "x")


def main():
    if TARGET.exists():
        raise SystemExit("fixture exists; refusing overwrite")
    n = curve.ORDER
    edges = [
        1, -1, 2, -2, 3, 4, 5, 7, 8, 9, 16, 27,
        n - 1, n + 1, 2 * n - 1, 2 * n + 1,
        1 << 64, (1 << 128) - 1, 1 << 128, (1 << 128) + 1,
        1 << 255, (1 << 256) - 1,
    ]
    rng = random.Random(SEED)
    scalars = edges + [rng.randrange(1, n) for _ in range(64)]
    assert len(scalars) == len(set(scalars))
    cases = []
    for index, scalar in enumerate(scalars):
        point = curve.point_multiply(scalar % n)
        assert point is not None
        x, y = point
        assert (y * y - x * x * x - 7) % curve.field.P == 0
        cases.append({
            "index": index,
            "base_x_hex": f"{curve.GENERATOR[0]:064x}",
            "base_y_hex": f"{curve.GENERATOR[1]:064x}",
            "scalar_hex": scalar_hex(scalar),
            "expected_identity": False,
            "expected_x_hex": f"{x:064x}",
            "expected_y_hex": f"{y:064x}",
        })
    fixture = {
        "schema": 1,
        "kind": "paired-fixed-generator-native-scalar",
        "curve": "secp256k1",
        "beta_hex": f"{curve.field.BETA:064x}",
        "seed": SEED,
        "edge_cases": len(edges),
        "random_cases": 64,
        "reference_sha256": sha(HERE / "lazy_tau_screen.py"),
        "generator_sha256": sha(Path(__file__)),
        "cases": cases,
    }
    TARGET.write_text(json.dumps(fixture, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"cases": len(cases), "fixture_sha256": sha(TARGET)}, sort_keys=True))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Check every frozen CLI field against the independent fixture."""

import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
FIXTURE = HERE.parent / "prime-j0-secp256k1-native/tau6-comb13-bench-fixture.json"
MODE = "unit_orbit_u256_sector14_xyzz_canonical_solinas_fixed"


def normalized(value):
    return value.lower().removeprefix("0x")


def main():
    cases = json.loads(FIXTURE.read_text())["cases"]
    lines = (HERE / "cli-fixture.txt").read_text().splitlines()
    assert len(cases) == len(lines) == 129
    for index, (case, line) in enumerate(zip(cases, lines)):
        fields = dict(item.split("=", 1) for item in line.split())
        expected_point = (
            "identity" if case["expected_identity"] else
            normalized(case["expected_x_hex"]) + ":" +
            normalized(case["expected_y_hex"])
        )
        expected = {
            "verified": "1",
            "mode": MODE,
            "scalar": normalized(case["scalar_hex"]),
            "base_x": normalized(case["base_x_hex"]),
            "base_y": normalized(case["base_y_hex"]),
            "point": expected_point,
        }
        for field, value in expected.items():
            assert fields[field] == value, (index, field)
    print("129/129 exact scalar, base, point, mode, and verification checks passed")


if __name__ == "__main__":
    main()

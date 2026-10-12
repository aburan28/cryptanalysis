#!/usr/bin/env python3
"""Independently replay the compact A1 witness over the declared binary field."""

import hashlib
import json
from pathlib import Path
import sys

from sage.all import EllipticCurve, GF, PolynomialRing


HERE = Path(__file__).resolve().parent
ORDER = 21_044_858_204_113


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(output):
    if output.exists():
        raise FileExistsError(output)
    fixture_path = HERE / "fixtures/single_hit.json"
    fixture = json.loads(fixture_path.read_text())
    assert fixture["field_degree"] == 53 and fixture["curve_a"] == 0
    polynomial = PolynomialRing(GF(2), "z")
    z = polynomial.gen()
    field = GF(2**53, name="a", modulus=z**53 + z**6 + z**2 + z + 1)
    alpha = field.gen()
    curve = EllipticCurve(field, [1, 0, 0, 0, 1])

    def element(bits):
        value = field(0)
        power = field(1)
        for i in range(53):
            if (bits >> i) & 1:
                value += power
            power *= alpha
        return value

    def point(coords):
        return curve(element(coords[0]), element(coords[1]))

    def frobenius(p, shift):
        return curve(p[0] ** (2**shift), p[1] ** (2**shift))

    generator = point(fixture["generator"])
    query = point(fixture["query_point"])
    target = point(fixture["target_point"])
    third = point(fixture["third_base_point"])
    reps = {int(i): point(value["point"])
            for i, value in fixture["representatives"].items()}
    seeds = [point(coords) for coords in fixture["seed_points"]]
    logs = fixture["seed_logs"]
    assert seeds[0] == generator
    assert all(logs[i] * generator == seeds[i] for i in range(6))
    assert all(value["scalar"] * seeds[value["seed_index"]] == reps[int(i)]
               for i, value in fixture["representatives"].items())
    assert frobenius(reps[90], fixture["third_frobenius_shift"]) == third
    assert fixture["third_sign"] == 1

    left, right, relative, side = fixture["pair_record"]
    pair = reps[left] + side * frobenius(reps[right], relative)
    difference = query - third
    matches = [(shift, sign)
               for shift in range(53) for sign in (1, -1)
               if sign * frobenius(pair, shift) == difference]
    assert matches == [(fixture["expected_global_shift"],
                        fixture["expected_global_sign"])]
    row = fixture["expected_row"]
    assert sum((row[i] * seeds[i] for i in range(6)), curve(0)) == query
    scalar = (sum(row[i] * logs[i] for i in range(6))
              - fixture["offset_scalar"]) % ORDER
    assert scalar == fixture["recovered_scalar"]
    assert scalar * generator == target
    assert query == target + fixture["offset_scalar"] * generator

    receipt = {
        "status": "verified", "field_degree": 53, "subgroup_order": ORDER,
        "fixture_sha256": digest(fixture_path), "source_sha256": digest(Path(__file__)),
        "pair_record": fixture["pair_record"], "alignment": matches[0],
        "weighted_row": row, "recovered_scalar": scalar,
        "target_point": fixture["target_point"],
    }
    output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": "verified", "recovered_scalar": scalar}))


if __name__ == "__main__":
    assert len(sys.argv) == 2
    main(Path(sys.argv[1]))

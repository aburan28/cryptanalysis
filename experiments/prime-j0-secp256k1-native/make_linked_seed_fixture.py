#!/usr/bin/env python3
"""Independently calculate the three linked native seed points with Sage."""

import hashlib
import json
from pathlib import Path

from sage.all import EllipticCurve, GF


HERE = Path(__file__).resolve().parent
FILENAMES = ("fixture.json", "edge-fixture.json", "linked-fresh-fixture.json")


def encoded(point):
    assert not point.is_zero()
    return [f"{int(point[0]):064x}", f"{int(point[1]):064x}"]


def main():
    output = HERE / "linked-seed-fixture.json"
    if output.exists():
        raise SystemExit("linked seed fixture exists; refusing overwrite")
    first = json.loads((HERE / FILENAMES[0]).read_bytes())
    p = int("fffffffffffffffffffffffffffffffffffffffffffffffffffffffefffffc2f", 16)
    curve = EllipticCurve(GF(p), [0, 7])
    beta = curve.base_field()(int(first["beta_hex"], 16))
    records = {}
    for filename in FILENAMES:
        raw = (HERE / filename).read_bytes()
        fixture = json.loads(raw)
        assert fixture["beta_hex"] == first["beta_hex"]
        cases = []
        for case in fixture["cases"]:
            x8, y8 = (int(value, 16) for value in case["seed_affine"][8])
            seed8 = curve(x8, y8)
            x4, y4 = (int(value, 16) for value in case["seed_affine"][4])
            seed4 = curve(x4, y4)
            base = curve(int(case["base_x_hex"], 16),
                         int(case["base_y_hex"], 16))
            omega_base = curve(beta * base[0], base[1])
            tau_base = base - omega_base
            assert seed8 == base - 2 * tau_base
            assert seed4 == 2 * (base + tau_base)
            # The old fixture supplies an independently checked Sage seed 8;
            # Sage's group law calculates its two successors anew.
            cases.append({"base_x_hex": case["base_x_hex"],
                          "scalar_hex": case["scalar_hex"],
                          "seed5": encoded(2 * seed8),
                          "seed6": encoded(4 * seed8),
                          "seed7": encoded(2 * seed4)})
        records[filename] = {"source_sha256": hashlib.sha256(raw).hexdigest(),
                             "cases": cases}
    result = {"schema": 1, "curve": "secp256k1",
              "beta_hex": first["beta_hex"],
              "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "fixtures": records}
    output.write_text(json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n")
    print(json.dumps({"cases": sum(len(value["cases"]) for value in records.values()),
                      "fixture_sha256": hashlib.sha256(output.read_bytes()).hexdigest()},
                     sort_keys=True))


if __name__ == "__main__":
    main()

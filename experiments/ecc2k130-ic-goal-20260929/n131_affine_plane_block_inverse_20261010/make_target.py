#!/usr/bin/env sage -python
"""Construct one independent N41 public-point fixture outside online timing."""

import hashlib
import json
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing

HERE = Path(__file__).resolve().parent
R = 549756390943
SEED = b"n41-affine-plane-fouratom-fresh-target-20261010-v1"


def main():
    base = PolynomialRing(GF(2), "t")
    t = base.gen()
    field = GF(2**41, name="t", modulus=t**41+t**3+1)
    curve = EllipticCurve(field, [1, 0, 0, 0, 1])

    def decode(value):
        return field(base([(int(value) >> i) & 1 for i in range(41)]))

    def encode(value):
        return sum(int(bit) << i for i, bit in enumerate(value.polynomial().list()))

    generator = curve(decode(2056947637384), decode(1635505394702))
    assert R * generator == curve(0)
    scalar = int.from_bytes(hashlib.sha256(SEED).digest(), "big") % R
    assert scalar != 0
    point = scalar * generator
    target = [encode(point[0]), encode(point[1])]
    assert R * point == curve(0)
    fixture = {"status": "PASS_INDEPENDENT_N41_TARGET_FIXTURE",
               "seed_label": SEED.decode(), "scalar_kept_out_of_worker_input": scalar,
               "target": target, "generator": [2056947637384,1635505394702]}
    public = {"curve_id": "EC1N41Ckb1h023d9a38bbf7",
              "target": target, "target_count": 1,
              "input_law": "SHA-256-derived nonzero scalar fixture, public point supplied without scalar"}
    for name, value in (("target_fixture.json", fixture), ("public_target.json", public)):
        with (HERE / name).open("x") as out:
            json.dump(value, out, indent=2, sort_keys=True)
            out.write("\n")
    print(json.dumps({"status": fixture["status"], "target": target}))


if __name__ == "__main__":
    main()

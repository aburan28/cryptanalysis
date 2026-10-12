#!/usr/bin/env python3
"""Symbolically screen simultaneous degree-seven conjugates and doubling."""

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
P = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFFC2F
FIXTURES = (HERE / "fixture.json", HERE / "linked-fresh-fixture.json")
SCALES = (1, 2, 3, 7)


class Field:
    def __init__(self):
        self.multiplications = 0
        self.squarings = 0

    def m(self, a, b):
        self.multiplications += 1
        return a * b % P

    def s(self, a):
        self.squarings += 1
        return a * a % P


def rho(field, x, y, z, a, b, aa, bb, c, d):
    xx = field.m(x, -3 * aa - field.m(b + 3 * d, 2 * a - b + c))
    yy = field.m(y, field.m(3 * aa, a - 4 * c + 7 * d)
                    + field.m(bb, b - 3 * a - 9 * c))
    zz = field.m(z, 2 * a - b + c - d)
    return xx, yy, zz


def conjugates_and_double(x, y, z, beta):
    field = Field()
    x2 = field.s(x)
    x3 = field.m(x2, x)
    y2 = field.s(y)
    a, b = 3 * x3 % P, 4 * y2 % P
    aa, bb = field.s(a), field.s(b)
    c, d = field.m(beta, a), field.m(beta, b)
    left = rho(field, x, y, z, a, b, aa, bb, c, d)
    # beta^2 = -1-beta. Thus beta^2*A and beta^2*B need no field product.
    right = rho(field, x, y, z, a, b, aa, bb,
                (-a-c) % P, (-b-d) % P)
    # The linked table requires omega((2-omega^2)P), not the conjugate
    # itself. Projective omega rotates only its X coordinate.
    right = field.m(beta, right[0]), right[1], right[2]
    y4 = field.s(y2)
    doubled = (field.m(x, 3 * a - 2 * b),
               field.m(3 * a, b - a) - 8 * y4,
               field.m(2 * y, z))
    assert (field.multiplications, field.squarings) == (19, 5)
    return left, right, doubled


def affine(point):
    x, y, z = point
    assert z % P != 0
    iz = pow(z, P - 2, P)
    iz2 = iz * iz % P
    return x * iz2 % P, y * iz2 * iz % P


def main():
    panels = []
    outputs = hashlib.sha256()
    for path in FIXTURES:
        raw = path.read_bytes()
        fixture = json.loads(raw)
        beta = int(fixture["beta_hex"], 16)
        assert beta**3 % P == 1 and beta != 1
        cases = fixture["cases"]
        for case in cases:
            x = int(case["base_x_hex"], 16)
            y = int(case["base_y_hex"], 16)
            expected = [tuple(int(value, 16) for value in case["seed_affine"][index])
                        for index in (3, 8, 1)]
            for scale in SCALES:
                z = scale
                projective_x = x * z * z % P
                projective_y = y * z * z * z % P
                results = conjugates_and_double(projective_x, projective_y,
                                                z, beta)
                for result, want in zip(results, expected):
                    got = affine(result)
                    assert got == want, f"{path.name}:{case['index']}:{scale}"
                    outputs.update(got[0].to_bytes(32, "big"))
                    outputs.update(got[1].to_bytes(32, "big"))
        panels.append({"fixture": path.name,
                       "fixture_sha256": hashlib.sha256(raw).hexdigest(),
                       "cases": len(cases),
                       "projective_scales": list(SCALES),
                       "point_checks": len(cases) * len(SCALES) * 3})
    result = {"schema": 1, "verified": True, "panels": panels,
              "field_products_per_three_outputs": 19,
              "field_squares_per_three_outputs": 5,
              "source_M_plus_S_per_three_outputs": 24,
              "compared_twin_M_plus_S_per_three_outputs": 26,
              "output_digest_sha256": outputs.hexdigest(),
              "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "cpu_speedup_claim": None, "academic_novelty_claim": None}
    target = HERE / "conjugate-rho-design-screen.json"
    if target.exists():
        raise SystemExit("conjugate rho screen exists; refusing overwrite")
    target.write_text(json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n")
    print(json.dumps({"verified": True,
                      "point_checks": sum(p["point_checks"] for p in panels),
                      "file_sha256": hashlib.sha256(target.read_bytes()).hexdigest()},
                     sort_keys=True))


if __name__ == "__main__":
    main()

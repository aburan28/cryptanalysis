#!/usr/bin/env sage -python
"""Test a trace formula for the W15 source point's 4E coset."""

import json
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing

HERE = Path(__file__).resolve().parent
SUPPORT = HERE.parent / "n131_w15_coupled_sixpair_20261010" / "support_w15.tsv"
ORDER = 680564733841876926932320129493409985129


def halftrace(value):
    total = value.parent().zero()
    term = value
    for _ in range(66):
        total += term
        term = term**4
    assert total**2 + total == value
    return total


def main():
    ring = PolynomialRing(GF(2), "t")
    t = ring.gen()
    field = GF(2**131, "t", modulus=t**131+t**13+t**2+t+1)
    curve = EllipticCurve(field, [1, 0, 0, 0, 1])
    torsion = curve(field.zero(), field.one())
    masks = [int(row.split()[0]) for row in SUPPORT.read_text().splitlines()]
    chosen = masks[:32] + masks[-32:] + masks[::max(1, len(masks)//64)][:64]
    basis = [field.gen()**i for i in range(1, 16)]
    observations = []
    for mask in chosen:
        w = sum((basis[i] for i in range(15) if mask >> i & 1), field.zero())
        assert w != 0 and w.trace() == 0
        v = halftrace(w**2)
        predicted = int((v/w).trace())
        point = curve.lift_x(1/w)
        class_point = ORDER*point
        observed = 0 if class_point == curve(0) else 1 if class_point == torsion else -1
        observations.append([mask, predicted, observed])
        assert predicted == observed, (mask, predicted, observed)
    print(json.dumps({"status": "PASS_COFACTOR_TRACE_FORMULA_SAMPLES",
                      "samples": len(observations),
                      "class_zero": sum(row[1] == 0 for row in observations),
                      "class_one": sum(row[1] == 1 for row in observations)}))


if __name__ == "__main__":
    main()

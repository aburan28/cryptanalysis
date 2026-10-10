#!/usr/bin/env python3
"""Construct mixed-rotation four-atom controls from archived raw points."""

import hashlib
import json
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing

here = Path(__file__).resolve().parent
old = here.parent / "n131_w14_coupled_fouratom_inverse_20261010" / "inputs.json"
inputs = json.loads(old.read_text())["panels"]


def field(n, exponents):
    ring = PolynomialRing(GF(2), "t")
    t = ring.gen()
    F = GF(2**n, name="t", modulus=sum(t**e for e in exponents))

    def decode(v):
        return F(ring([(int(v)>>i)&1 for i in range(n)]))

    def encode(v):
        return sum(int(bit)<<i for i,bit in enumerate(v.polynomial().list()))

    return F,decode,encode


result = {"status": "PASS_MIXED_ROTATION_CONTROLS", "panels": {},
          "source_sha256": {
              "prepare.py": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "archived_inputs.json": hashlib.sha256(old.read_bytes()).hexdigest()}}
for n,r1,r2 in [(41,10,15),(131,26,39)]:
    panel = inputs[str(n)]
    F,decode,encode = field(n,panel["field_modulus_exponents"])
    E = EllipticCurve(F,[1,0,0,0,1])
    points = [E(decode(x),decode(y)) for x,y in panel["raw_diagonal_atoms"]]
    def rotate(point,steps):
        x,y = point.xy()
        for _ in range(steps):
            x,y=x*x,y*y
        return E(x,y)
    rotated = [rotate(p,r1 if i<2 else r2) for i,p in enumerate(points)]
    pair1 = rotated[0]+rotated[1]
    pair2 = rotated[2]+rotated[3]
    total = pair1+pair2
    assert pair1 != E(0) and pair2 != E(0) and total != E(0)
    assert all(p[0] != 0 for p in (pair1,pair2,total))
    s = decode(panel["source_sum_field"])
    p,q = [decode(v) for v in panel["pair_products"]]
    s1,s2 = s**(2**r1),s**(2**r2)
    p1,p2 = p**(2**r1),q**(2**r2)
    c,d,z = [~point[0] for point in (pair1,pair2,total)]
    assert (1+p1*p1)*c*c+p1*c+s1*s1 == 0
    assert (1+p2*p2)*d*d+p2*d+s2*s2 == 0
    assert (1+c*c*d*d)*z*z+c*d*z+(c+d)**2 == 0
    projected = 4*total
    assert projected != E(0)
    assert int(panel["subgroup_order"])*projected == E(0)
    result["panels"][str(n)] = {
        "field_degree": n, "source_dimension": panel["source_dimension"],
        "curve_id": panel["curve_id"],
        "rotations": [r1,r2], "seed_sum": panel["source_sum_field"],
        "source_masks": panel["masks"], "source_products": panel["pair_products"],
        "pair_outputs_reciprocal": [encode(c),encode(d)],
        "positive_z": encode(z),
        "trace_zero_control_z": panel["trace_zero_control_z"],
        "raw_sum": [encode(v) for v in total.xy()],
        "projected_sum": [encode(v) for v in projected.xy()],
        "group_replay": True,
        "pair_equations": True,
        "upper_s3_equation": True,
    }
(here / "inputs.json").write_text(json.dumps(result, indent=2, sort_keys=True)+"\n")
print(json.dumps({"status":result["status"],
                  "positive_z": {n:p["positive_z"] for n,p in result["panels"].items()}},
                 sort_keys=True))

#!/usr/bin/env sage -python
"""Replay rotated resultant on the N41 public row and N131 constructed row."""

import hashlib
import json
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
RESULTANT = HERE / "resultant.json"
N41_SCREEN = BASE / "n41_n131_diagonal_atom_20261010/screen.json"
N41_HIT = BASE / "n131_w15_cross_block_seed_offset_20261010/n41_hit.json"
N131_LIFT = BASE / "n131_w15_coupled_sixpair_20261010/control_group_lift.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


freeze = json.loads((HERE / "control_protocol.json").read_text())
assert freeze["status"] == "FROZEN_BEFORE_ROTATED_RESULTANT_CONTROLS"
assert freeze["source_sha256"] == {
    "control.py": sha(Path(__file__)), "resultant": sha(RESULTANT),
    "n41_screen": sha(N41_SCREEN), "n41_hit": sha(N41_HIT),
    "n131_lift": sha(N131_LIFT),
    "sage_runtime_info": sha(HERE / "sage_runtime_info.json")}
assert not (HERE / "control_result.json").exists()
terms = json.loads(RESULTANT.read_text())["terms"]


def field_and_curve(n):
    ring = PolynomialRing(GF(2), "t")
    t = ring.gen()
    modulus = t**41+t**3+1 if n == 41 else t**131+t**13+t**2+t+1
    field = GF(2**n, "t", modulus=modulus)
    return ring, field, EllipticCurve(field, [1, 0, 0, 0, 1])


def decode(ring, field, n, value):
    return field(ring([(int(value) >> i) & 1 for i in range(n)]))


def encode(value):
    return sum(int(bit) << i for i, bit in enumerate(value.polynomial().list()))


def source_w(field, d, mask):
    return sum((field.gen()**(i+1) for i in range(d) if mask >> i & 1), field.zero())


def coefficients(a, b, z):
    ap = [a**i for i in range(9)]
    bp = [b**i for i in range(9)]
    zp = [z**i for i in range(9)]
    coeff = [[a.parent().zero() for _ in range(9)] for _ in range(9)]
    for ea, eb, ep, eq, ez in terms:
        coeff[eq][ep] += ap[ea]*bp[eb]*zp[ez]
    return coeff


def evaluate(coeff, p, q):
    result = p.parent().zero()
    for i in range(8, -1, -1):
        row = p.parent().zero()
        for j in range(8, -1, -1):
            row = row*p + coeff[i][j]
        result = result*q + row
    return result


def make_case(n, d, rotations, masks, raw_points, descriptor):
    ring, field, curve = field_and_curve(n)
    points = [curve(decode(ring, field, n, x), decode(ring, field, n, y))
              for x, y in raw_points]
    assert len(points) == 4 and all(point != curve(0) for point in points)
    seeds = [masks[0]^masks[1], masks[2]^masks[3]]
    assert seeds[0] == seeds[1] and seeds[0] != 0
    s = source_w(field, d, seeds[0])
    a, b = [s**(2**rotation) for rotation in rotations]
    products = [source_w(field, d, masks[i])*source_w(field, d, masks[i+1])
                for i in (0, 2)]
    p, q = [products[i]**(2**rotations[i]) for i in (0, 1)]
    pair_points = [points[0]+points[1], points[2]+points[3]]
    assert all(point != curve(0) and point[0] != 0 for point in pair_points)
    c, e = [1/point[0] for point in pair_points]
    four = sum(points, curve(0))
    assert four != curve(0) and four[0] != 0
    z = 1/four[0]
    assert (1+p**2)*c**2+p*c+a**2 == 0
    assert (1+q**2)*e**2+q*e+b**2 == 0
    assert (1+c**2*e**2)*z**2+c*e*z+(c+e)**2 == 0
    positive = evaluate(coefficients(a,b,z), p,q)
    assert positive == 0
    control_z = field.gen()+1
    control_eval = evaluate(coefficients(a,b,control_z), p,q)
    assert control_eval != 0
    # All distinct values of w(w+s), after the appropriate Frobenius rotations.
    if n == 41:
        products_base = {source_w(field,d,mask)*(source_w(field,d,mask)+s)
                         for mask in range(1 << d)}
        assert len(products_base) == 32
        left = sorted((value**(2**rotations[0]) for value in products_base), key=encode)
        right = sorted((value**(2**rotations[1]) for value in products_base), key=encode)
        positive_coeff = coefficients(a,b,z)
        control_coeff = coefficients(a,b,control_z)
        positive_hits = [(encode(x),encode(y)) for x in left for y in right
                         if evaluate(positive_coeff,x,y) == 0]
        control_hits = [(encode(x),encode(y)) for x in left for y in right
                        if evaluate(control_coeff,x,y) == 0]
        assert (encode(p),encode(q)) in positive_hits
    else:
        positive_hits = [(encode(p),encode(q))]
        control_hits = []
    return {
        "descriptor": descriptor, "field_degree": n, "source_dimension": d,
        "pair_rotations": rotations, "masks": masks, "seed_mask": seeds[0],
        "rotated_seed_coordinates": [encode(a),encode(b)],
        "rotated_pair_products": [encode(p),encode(q)],
        "pair_reciprocal_outputs": [encode(c),encode(e)],
        "four_atom_reciprocal_output": encode(z),
        "four_atom_projected_point": [encode((4*four)[0]), encode((4*four)[1])],
        "positive_resultant_zero": True,
        "independent_field_control_z": encode(control_z),
        "known_product_control_resultant_nonzero": True,
        "positive_algebraic_product_hits": positive_hits,
        "control_algebraic_product_hits": control_hits,
        "product_family_states_checked": 1024 if n == 41 else None,
    }


screen = json.loads(N41_SCREEN.read_text())
hit = json.loads(N41_HIT.read_text())
raw_by_mask = {row["mask"]: row for row in screen["raw_audit"]}
ring41, F41, E41 = field_and_curve(41)
n41_points = []
for block in (2,3):
    rotation = block*5
    for local in range(2):
        i = 2*block+local
        mask, sign = hit["masks"][i], hit["signs"][i]
        slot = next(row for row in screen["slots"][block]
                    if row["mask"] == mask and row["sign"] == sign)
        leaf = E41(decode(ring41,F41,41,slot["point"][0]),
                   decode(ring41,F41,41,slot["point"][1]))
        source = raw_by_mask[mask]
        raw = E41(decode(ring41,F41,41,source["raw_pair_point"][0]),
                  decode(ring41,F41,41,source["raw_pair_point"][1]))
        for _ in range(rotation):
            raw = E41(raw[0]**2, raw[1]**2)
        if 4*raw != leaf:
            raw = -raw
        assert 4*raw == leaf
        n41_points.append([encode(raw[0]), encode(raw[1])])
n41_case = make_case(41,6,[10,15],hit["masks"][4:8],n41_points,
                     "frozen N41 public-point twelve-column relation, constrained block A")

lift = json.loads(N131_LIFT.read_text())["solutions"][0]
n131_case = make_case(131,15,[26,39],lift["masks"][4:8],lift["raw_leaves"][4:8],
                      "archived N131 constructed twelve-column witness, constrained block A")

record = {"status": "PASS_ROTATED_RESULTANT_N41_PUBLIC_ROW_AND_N131_CONTROL",
          "n41": n41_case, "n131": n131_case,
          "protocol_sha256": sha(HERE / "control_protocol.json"),
          "source_sha256": freeze["source_sha256"]}
with (HERE / "control_result.json").open("x") as output:
    json.dump(record, output, sort_keys=True, indent=2)
    output.write("\n")
print({"status": record["status"],
       "n41_positive_hits": len(n41_case["positive_algebraic_product_hits"]),
       "n41_control_hits": len(n41_case["control_algebraic_product_hits"]),
       "n131_seed": n131_case["seed_mask"]})

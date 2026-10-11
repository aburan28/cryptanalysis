#!/usr/bin/env python3
"""Independent positive/negative Sage check of the symbolic bucket GCD."""

import hashlib
import json
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
GEOMETRY = BASE / "n41_two_free_pair_occupancy_20261009/geometry_snapshot.json"
PRIOR = BASE / "n41_seed_sum_s3_bucket_norm_20261010/batch_result.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def decode(field, value):
    return sum((field.gen()**i for i in range(41) if value >> i & 1),
               field.zero())


def encode(value):
    return sum(int(bit) << i for i, bit in enumerate(value.polynomial()))


def selected(values, mask):
    return sum((v for i, v in enumerate(values) if mask >> i & 1),
               values[0].parent().zero())


def bucket(field, ring, basis_bits, seed):
    basis = [decode(field, x) for x in basis_bits]
    us = selected(basis, seed)
    ws = us*us+us
    w_basis = [u*u+u for u in basis]
    products = {selected(w_basis, mask)**2+ws*selected(w_basis, mask)
                for mask in range(64)}
    assert len(products) == 32
    X = ring.gen()
    polynomial = ring.one()
    for p in products:
        polynomial *= (1+p)*X*X+p*X+us*us
    return polynomial, us*us, products


def target_norm(ring, t, u2, products):
    X = ring.gen()
    C = (X*X+X)*(t*t+t)
    D = (X+t)**2
    result = ring.one()
    for p in products:
        M = (1+C)*u2+(1+p)*D
        result *= M*M+(p+C)*(C*u2+p*D)
    return result


def main():
    protocol_path = HERE / "protocol.json"
    protocol = json.loads(protocol_path.read_text())
    profile_path = HERE / "profile.json"
    profile = json.loads(profile_path.read_text())
    assert len(profile["profile"]) == 16
    assert sha(GEOMETRY) == protocol["sha256"]["geometry"]
    binary = PolynomialRing(GF(2), "T")
    T = binary.gen()
    field = GF(2**41, "T", modulus=T**41+T**3+1)
    curve = EllipticCurve(field, [1, 0, 0, 0, 1])
    ring = PolynomialRing(field, "X")
    geometry = json.loads(GEOMETRY.read_text())["n41"]
    left, _, _ = bucket(field, ring, geometry["window_basis_halftrace"][2], 16)
    right, right_u2, right_products = bucket(
        field, ring, geometry["window_basis_halftrace"][3], 5)
    torsion = curve(field.one(), field.zero())
    target_points = {}
    for kind in ("positive", "negative"):
        projected = curve(*(decode(field, x) for x in protocol[kind+"_residual"]))
        inv4 = pow(4, -1, geometry["subgroup_order"])
        target_points[kind] = [inv4*projected+j*torsion for j in range(4)]
        assert all(4*p == projected for p in target_points[kind])
    results = []
    for kind in ("positive", "negative"):
        for option, point in enumerate(target_points[kind]):
            t = 1/(point[0]+1)
            norm = target_norm(ring, t, right_u2, right_products)
            common = left.gcd(norm)
            expected = next(row for row in profile["profile"] if row["kind"] == kind
                            and row["option"] == option and row["right_seed"] == 5)
            if common.degree() != expected["gcd_degree"]:
                raise AssertionError("independent direct resultant disagrees with compact norm")
            results.append({"kind": kind, "option": option,
                            "gcd_degree": int(common.degree()),
                            "roots": [encode(x) for x in common.roots(multiplicities=False)]})
    positive = next(row for row in results if row["kind"] == "positive" and row["option"] == 3)
    if positive["gcd_degree"] != 1:
        raise AssertionError("expected positive pair family lost")
    z = decode(field, positive["roots"][0])
    point = target_points["positive"][3]
    t = 1/(point[0]+1)
    C = (z*z+z)*(t*t+t)
    D = (z+t)**2
    right_roots = [x for x in right.roots(multiplicities=False)
                   if (1+C)*x*x+C*x+D == 0]
    if not right_roots:
        raise AssertionError("positive left root lacks rational right output")
    group_witness = None
    for b in right_roots:
        L = curve.lift_x(1+1/z)
        R = curve.lift_x(1+1/b)
        for l in (L, -L):
            for r in (R, -R):
                if l+r == point:
                    group_witness = {"left": [encode(l[0]), encode(l[1])],
                                     "right": [encode(r[0]), encode(r[1])],
                                     "target": [encode(point[0]), encode(point[1])],
                                     "left_reciprocal": encode(z),
                                     "right_reciprocal": encode(b)}
                    break
            if group_witness is not None:
                break
        if group_witness is not None:
            break
    if group_witness is None:
        raise AssertionError("positive S3 root lacks exact group lift")
    prior = json.loads(PRIOR.read_text())["cases"][0]["first_group_witness"]
    if 4*curve(*(decode(field, x) for x in group_witness["left"])) != curve(
            *(decode(field, x) for x in prior["left_pair_point"])):
        raise AssertionError("positive raw left point does not project to archived witness")
    if 4*curve(*(decode(field, x) for x in group_witness["right"])) != curve(
            *(decode(field, x) for x in prior["right_pair_point"])):
        raise AssertionError("positive raw right point does not project to archived witness")
    audit = {"status": "PASS_EXACT_TWO_BUCKET_CONTROL", "candidate_id": None,
             "source_sha256": sha(Path(__file__)), "protocol_sha256": sha(protocol_path),
             "profile_sha256": sha(profile_path), "geometry_sha256": sha(GEOMETRY),
             "prior_witness_sha256": sha(PRIOR), "direct_case_checks": results,
             "positive_raw_group_witness": group_witness,
             "projected_pair_witness_match": True}
    with (HERE / "audit.json").open("x") as stream:
        json.dump(audit, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"status": audit["status"], "direct_cases": len(results),
                      "positive_right_root": group_witness["right_reciprocal"]}))


if __name__ == "__main__":
    main()

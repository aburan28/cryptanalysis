#!/usr/bin/env python3
"""Independent Sage replay by enumerating right polynomial roots and S3 links."""

import hashlib
import json
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
GEOMETRY = BASE / "n41_two_free_pair_occupancy_20261009/geometry_snapshot.json"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def elem(field, number):
    t = field.gen()
    return sum((t**i for i in range(41) if number >> i & 1), field.zero())


def number(element):
    return sum(int(bit) << i for i, bit in enumerate(element.polynomial()))


def coord(values, mask):
    return sum((v for i, v in enumerate(values) if mask >> i & 1),
               values[0].parent().zero())


def quadratic_roots(a, b, c):
    """Enumerate the roots in the odd-degree binary field without factoring."""
    field = c.parent()
    if a == 0:
        if b == 0:
            raise AssertionError("degenerate bucket factor")
        return [c/b]
    if b == 0:
        return [(c/a)**(1 << 40)]
    v = a*c/(b*b)
    if v.trace() != 0:
        return []
    h = field.zero()
    current = v
    for _ in range(21):
        h += current
        current = current**4
    scale = b/a
    roots = [scale*h, scale*(h+1)]
    if any(a*r*r+b*r+c != 0 for r in roots):
        raise AssertionError("independent quadratic solve failed")
    return roots


def main():
    protocol = json.loads((HERE / "protocol.json").read_text())
    result_path = HERE / "result.json"
    result = json.loads(result_path.read_text())
    if result["source_sha256"] != protocol["sha256"]["source"]:
        raise AssertionError("producer changed after freeze")
    if digest(GEOMETRY) != protocol["sha256"]["geometry"]:
        raise AssertionError("geometry changed after freeze")
    ring2 = PolynomialRing(GF(2), "T")
    T = ring2.gen()
    field = GF(2**41, "T", modulus=T**41+T**3+1)
    curve = EllipticCurve(field, [1, 0, 0, 0, 1])
    geometry = json.loads(GEOMETRY.read_text())["n41"]
    u = [elem(field, bits) for bits in geometry["window_basis_halftrace"][3]]
    w = [v*v+v for v in u]
    buckets = {}
    for seed in range(1, 64):
        us = coord(u, seed)
        ws = coord(w, seed)
        products = {coord(w, a)*coord(w, a ^ seed) for a in range(64)}
        if len(products) != 32:
            raise AssertionError("right product image changed")
        roots = set()
        for p in products:
            roots.update(quadratic_roots(1+p, p, us*us))
        if not roots:
            raise AssertionError("empty right output bucket")
        buckets[seed] = roots
    witness = result["constructed_group_witness"]
    L = curve(elem(field, witness["left"][0]), elem(field, witness["left"][1]))
    R = curve(elem(field, witness["right"][0]), elem(field, witness["right"][1]))
    M = curve(elem(field, witness["sum"][0]), elem(field, witness["sum"][1]))
    if L+R != M or 1/(L[0]+1) != elem(field, witness["left_reciprocal"]):
        raise AssertionError("constructed group witness invalid")
    if 1/(R[0]+1) != elem(field, witness["right_reciprocal"]):
        raise AssertionError("right witness reciprocal invalid")
    points = {(row["kind"], row["option"]):
              curve(elem(field, row["point"][0]), elem(field, row["point"][1]))
              for row in result["case_points"]}
    torsion = curve(field.one(), field.zero())
    for kind in ("positive_residual", "negative_residual"):
        projected = curve(*(elem(field, v) for v in protocol[kind]))
        for option in range(4):
            if 4*points[kind, option] != projected:
                raise AssertionError("raw residual lift failed")
    for row in result["cases"]:
        point = points[row["kind"], row["target_option"]]
        z = {"witness_left": elem(field, witness["left_reciprocal"]),
             "field_one": field.one(), "field_generator": field.gen()}[row["left_coordinate"]]
        t = 1/(point[0]+1)
        C = (z*z+z)*(t*t+t)
        D = (z+t)**2
        hits = [seed for seed, roots in buckets.items()
                if any((1+C)*B*B+C*B+D == 0 for B in roots)]
        if hits != row["seed_hits"]:
            raise AssertionError("right root census disagrees with span gate")
    audit = {"status": "INDEPENDENT_EXACT_REPLAY", "result_sha256": digest(result_path),
             "audit_source_sha256": digest(Path(__file__)),
             "right_bucket_count": len(buckets),
             "roots_per_right_bucket_min": min(map(len, buckets.values())),
             "roots_per_right_bucket_max": max(map(len, buckets.values())),
             "case_count": len(result["cases"]),
             "bucket_decisions": sum(row["checked_buckets"] for row in result["cases"]),
             "constructed_group_sum_verified": True,
             "fourfold_residual_lifts_verified": 8}
    with (HERE / "audit.json").open("x") as stream:
        json.dump(audit, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps(audit, sort_keys=True))


if __name__ == "__main__":
    main()

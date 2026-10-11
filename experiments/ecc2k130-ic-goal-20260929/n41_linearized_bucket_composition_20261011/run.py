#!/usr/bin/env python3
"""Check a linearized, target-conditioned S3 resultant for N41 pair buckets."""

import hashlib
import json
import resource
import sys
import time
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
GEOMETRY = BASE / "n41_two_free_pair_occupancy_20261009/geometry_snapshot.json"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def integer(x):
    return sum(int(bit) << i for i, bit in enumerate(x.polynomial()))


def element(field, bits):
    t = field.gen()
    answer = field.zero()
    while bits:
        bit = (bits & -bits).bit_length() - 1
        answer += t**bit
        bits &= bits - 1
    return answer


def mask_sum(values, mask):
    answer = values[0].parent().zero()
    for i, value in enumerate(values):
        if mask >> i & 1:
            answer += value
    return answer


def independent(values):
    pivots = {}
    output = []
    for value in values:
        x = integer(value)
        while x:
            pivot = x.bit_length() - 1
            if pivot not in pivots:
                pivots[pivot] = x
                output.append(value)
                break
            x ^= pivots[pivot]
    return output


def in_span(values, target):
    pivots = {}
    for value in values:
        x = integer(value)
        while x:
            pivot = x.bit_length() - 1
            if pivot not in pivots:
                pivots[pivot] = x
                break
            x ^= pivots[pivot]
    x = integer(target)
    while x:
        pivot = x.bit_length() - 1
        if pivot not in pivots:
            return False
        x ^= pivots[pivot]
    return True


def subspace_polynomial_at(basis, target):
    """L_span(basis)(target), built by adjoining one independent vector."""
    coefficients = [target.parent().one()]
    for value in basis:
        at_value = sum((c * value ** (1 << i)
                        for i, c in enumerate(coefficients)), value.parent().zero())
        raised = [value.parent().zero()] + [c**2 for c in coefficients]
        for i, c in enumerate(coefficients):
            raised[i] += at_value * c
        coefficients = raised
    return sum((c * target ** (1 << i) for i, c in enumerate(coefficients)),
               target.parent().zero())


def seed_data(w_basis, u_basis, seed):
    w_seed = mask_sum(w_basis, seed)
    u2 = mask_sum(u_basis, seed)**2
    image_basis = independent([w**2 + w_seed*w for w in w_basis])
    assert len(image_basis) == len(w_basis) - 1
    products = {mask_sum(w_basis, a)**2 + w_seed*mask_sum(w_basis, a)
                for a in range(1 << len(w_basis))}
    assert len(products) == 1 << len(image_basis)
    return u2, image_basis, products


def pair_polynomial(ring, u2, products):
    Z = ring.gen()
    result = ring.one()
    for p in products:
        result *= (1+p)*Z**2 + p*Z + u2
    return result


def test_bucket(z, t, u2, image_basis, products):
    """Compare the exact product resultant with a linearized span test."""
    c = (z**2 + z)*(t**2 + t)
    d = (z+t)**2
    alpha = 1+c
    a = (alpha*u2+d)**2 + c*c*u2
    b = c*(u2+d)
    e = d*d+d
    transformed = [b*v+e*v*v for v in image_basis]
    transformed_basis = independent(transformed)
    via_span = in_span(transformed_basis, a)
    via_linearized = subspace_polynomial_at(transformed_basis, a) == 0
    direct = z.parent().one()
    for p in products:
        m = alpha*u2+(1+p)*d
        direct *= m*m+(p+c)*(c*u2+p*d)
    via_product = direct == 0
    if not (via_span == via_linearized == via_product):
        raise AssertionError("linearized resultant disagrees with direct product")
    return {"hit": via_span, "rank": len(transformed_basis),
            "kernel_multiplicity": 1 << (len(image_basis)-len(transformed_basis)),
            "direct_value": integer(direct)}


def rss_bytes():
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return value if sys.platform == "darwin" else value*1024


def main():
    protocol_path = HERE / "protocol.json"
    protocol = json.loads(protocol_path.read_text())
    for key, path in (("source", Path(__file__)), ("geometry", GEOMETRY),
                      ("runtime", HERE / "sage_runtime_info.json")):
        if digest(path) != protocol["sha256"][key]:
            raise ValueError("frozen digest mismatch: " + key)
    binary = PolynomialRing(GF(2), "t")
    x = binary.gen()
    field = GF(2**41, "t", modulus=x**41+x**3+1)
    curve = EllipticCurve(field, [1, 0, 0, 0, 1])
    ring = PolynomialRing(field, "Z")
    geometry = json.loads(GEOMETRY.read_text())["n41"]
    u_bases = [[element(field, bits) for bits in row]
               for row in geometry["window_basis_halftrace"]]
    w_bases = [[u*u+u for u in row] for row in u_bases]
    left = {s: seed_data(w_bases[2], u_bases[2], s) for s in range(1, 64)}
    right = {s: seed_data(w_bases[3], u_bases[3], s) for s in range(1, 64)}
    # Prove the compact root polynomial equals the independent factor product.
    # Sage's polynomial representation gives an exact equality, not samples.
    polynomial_checks = 0
    for data in (left, right):
        for u2, basis, products in data.values():
            Z = ring.gen()
            compact = (Z*Z+Z)**(1 << len(basis)) * ring.zero()
            # Homogenize L_V((Z^2+u^2)/(Z^2+Z)) without division.
            coefficients = [field.one()]
            for v in basis:
                at_v = sum((c*v**(1 << i) for i, c in enumerate(coefficients)), field.zero())
                raised = [field.zero()] + [c*c for c in coefficients]
                for i, c in enumerate(coefficients):
                    raised[i] += at_v*c
                coefficients = raised
            A, D = Z*Z+u2, Z*Z+Z
            degree = 1 << len(basis)
            compact = sum((c*A**(1 << i)*D**(degree-(1 << i))
                           for i, c in enumerate(coefficients)), ring.zero())
            if compact != pair_polynomial(ring, u2, products):
                raise AssertionError("compact pair-output polynomial mismatch")
            polynomial_checks += 1
    # Construct a witness from two independently enumerated exact root sets.
    z_left = left[16]
    z_right = right[5]
    left_root = pair_polynomial(ring, z_left[0], z_left[2]).roots(multiplicities=False)[0]
    right_root = pair_polynomial(ring, z_right[0], z_right[2]).roots(multiplicities=False)[0]
    left_point = curve.lift_x(1+1/left_root)
    right_point = curve.lift_x(1+1/right_root)
    target = left_point+right_point
    if target == curve(0) or target[0] == 1:
        raise AssertionError("exceptional constructed target")
    target_coordinate = 1/(target[0]+1)
    assert test_bucket(left_root, target_coordinate, *z_right)["hit"]
    cases = []
    points = []
    for kind in ("constructed", "positive_residual", "negative_residual"):
        if kind == "constructed":
            targets = [target]
        else:
            xy = protocol[kind]
            projected = curve(element(field, xy[0]), element(field, xy[1]))
            torsion = curve(field.one(), field.zero())
            inverse_four = pow(4, -1, geometry["subgroup_order"])
            targets = [inverse_four*projected+j*torsion for j in range(4)]
            assert all(4*p == projected for p in targets)
        for option, point in enumerate(targets):
            if point[0] == 1:
                continue
            t = 1/(point[0]+1)
            for z_label, z in (("witness_left", left_root),
                               ("field_one", field.one()),
                               ("field_generator", field.gen())):
                start = time.monotonic_ns()
                hits = []
                rank_histogram = {}
                for seed, (u2, basis, products) in right.items():
                    answer = test_bucket(z, t, u2, basis, products)
                    rank_histogram[str(answer["rank"])] = rank_histogram.get(str(answer["rank"]), 0)+1
                    if answer["hit"]:
                        hits.append(seed)
                cases.append({"kind": kind, "target_option": option,
                              "left_coordinate": z_label, "seed_hits": hits,
                              "rank_histogram": rank_histogram,
                              "checked_buckets": 63,
                              "elapsed_ns": time.monotonic_ns()-start})
            points.append({"kind": kind, "option": option, "point": [integer(point[0]), integer(point[1])]})
    if rss_bytes() > protocol["rss_cap_bytes"]:
        raise MemoryError("frozen RSS cap exceeded")
    result = {"status": "COMPLETE_EXACT_COMPONENT", "candidate_id": None,
              "proposal_id": protocol["proposal_id"], "target_count": 0,
              "protocol_sha256": digest(protocol_path), "source_sha256": digest(Path(__file__)),
              "polynomial_identity_checks": polynomial_checks,
              "constructed_group_witness": {
                  "left": [integer(left_point[0]), integer(left_point[1])],
                  "right": [integer(right_point[0]), integer(right_point[1])],
                  "sum": [integer(target[0]), integer(target[1])],
                  "left_seed": 16, "right_seed": 5,
                  "left_reciprocal": integer(left_root), "right_reciprocal": integer(right_root)},
              "case_points": points, "cases": cases, "peak_rss_bytes": rss_bytes()}
    with (HERE / "result.json").open("x") as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"status": result["status"], "polynomial_checks": polynomial_checks,
                      "case_count": len(cases), "bucket_checks": sum(c["checked_buckets"] for c in cases),
                      "peak_rss_bytes": result["peak_rss_bytes"]}))


if __name__ == "__main__":
    main()

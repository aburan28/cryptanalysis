#!/usr/bin/env python3
"""Independent quadratic-resultant and source-bound degree audit."""

import hashlib
import json
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
GEOMETRY = BASE / "n41_two_free_pair_occupancy_20261009/geometry_snapshot.json"
PREVIOUS = BASE / "n41_w6_subspace_norm_20261010/result.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def lift(F, value):
    t = F.gen()
    out = F.zero()
    i = 0
    while value:
        if value & 1:
            out += t**i
        value >>= 1
        i += 1
    return out


def coordinate(values, mask):
    return sum((values[i] for i in range(len(values)) if mask >> i & 1),
               values[0].parent().zero())


def main():
    output = HERE / "sage_audit.json"
    if output.exists():
        raise FileExistsError(output)
    v1 = json.loads((HERE / "result.json").read_text())
    v2 = json.loads((HERE / "batch_result.json").read_text())
    prior = json.loads(PREVIOUS.read_text())
    assert v1["status"] == v2["status"] == "CENSORED_DIAGNOSTIC"
    assert v1["left_polynomial_degree"] == v2["left_polynomial_degree"] == 4032
    assert all(row["status"] == "CENSORED_TIME"
               for record in (v1, v2) for row in record["cases"])
    binary = PolynomialRing(GF(2), "t")
    t0 = binary.gen()
    F = GF(2**41, "t", modulus=t0**41+t0**3+1)
    E = EllipticCurve(F, [1, 0, 0, 0, 1])
    poly = PolynomialRing(F, "B")
    B = poly.gen()
    geometry = json.loads(GEOMETRY.read_text())["n41"]
    basis = [lift(F, value) for value in geometry["window_basis_halftrace"][3]]
    witness = prior["cases"][0]["hits"][0]
    projected = E(lift(F, 332635421840), lift(F, 2054854538524))
    torsion = E(F.one(), F.zero())
    target = pow(4, -1, geometry["subgroup_order"])*projected+3*torsion
    a = 1/(lift(F, witness["a"])+1)
    b = 1/(lift(F, witness["exact_b"][0])+1)
    z = 1/(target[0]+1)
    C = (a**2+a)*(z**2+z)
    D = (a+z)**2
    f = (1+C)*B**2+C*B+D
    s = witness["right_sum"]
    us = coordinate(basis, s)
    ws = us**2+us
    w = [u**2+u for u in basis]
    products = {coordinate(w, mask)**2+ws*coordinate(w, mask)
                for mask in range(64)}
    assert len(products) == 32 and f(b) == 0
    resultants_checked = 0
    right_product_hit = False
    for p in products:
        g = (1+p)*B**2+p*B+us**2
        M = (1+C)*us**2+(1+p)*D
        L = p+C
        N = C*us**2+p*D
        if f.resultant(g) != M**2+L*N:
            raise AssertionError("quadratic resultant identity failed")
        resultants_checked += 1
        if g(b) == 0:
            right_product_hit = True
    if not right_product_hit:
        raise AssertionError("positive right product missing")
    # W14 uses w_i=t^i, 1<=i<=14. Products have degree 2..28 in the
    # degree-131 polynomial basis, so p=1 is absent and every bucket
    # polynomial retains degree 2^14.
    m = 14
    n = 131
    per_bucket_degree = 1 << m
    seed_buckets = (1 << m)-1
    global_degree = seed_buckets*per_bucket_degree
    dense_min_bytes = ((global_degree+1)*n+7)//8
    assert global_degree == 268419072
    assert dense_min_bytes > 4*(1 << 30)
    result = {"status": "PASS", "source_sha256": sha(Path(__file__)),
              "geometry_sha256": sha(GEOMETRY),
              "v1_result_sha256": sha(HERE / "result.json"),
              "v2_result_sha256": sha(HERE / "batch_result.json"),
              "previous_result_sha256": sha(PREVIOUS),
              "runtime_sha256": sha(HERE / "sage_runtime_info_v2.json"),
              "quadratic_resultants_checked": resultants_checked,
              "positive_s3_and_pair_product": True,
              "n41_global_left_degree": 4032,
              "n131_w14_per_bucket_degree": per_bucket_degree,
              "n131_w14_nonzero_seed_buckets": seed_buckets,
              "n131_w14_expanded_global_degree": global_degree,
              "n131_dense_coefficient_bits": (global_degree+1)*n,
              "n131_dense_min_bytes": dense_min_bytes,
              "four_gib_bytes": 4*(1 << 30)}
    with output.open("x") as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps(result))


if __name__ == "__main__":
    main()

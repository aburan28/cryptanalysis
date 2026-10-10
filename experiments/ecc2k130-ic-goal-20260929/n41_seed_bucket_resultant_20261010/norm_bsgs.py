#!/usr/bin/env python3
"""Baby-step/giant-step evaluation of the quadratic seed-bucket norm."""

import hashlib
import json
import math
import resource
import sys
import time
from pathlib import Path

from sage.all import GF, PolynomialRing

from run import Field, build_bucket, encode

HERE = Path(__file__).resolve().parent
GEOMETRY = HERE.parent / "n41_two_free_pair_occupancy_20261009/geometry_snapshot.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bsgs_bucket_norm(left, right, target):
    ring = left.parent()
    x = ring.gen()
    a = (x + target)**2 % left
    if a.gcd(left).degree() != 0:
        raise ValueError("nonunit S3 leading coefficient")
    inverse = a.inverse_mod(left)
    alpha = (target*x*inverse) % left
    beta = (((target*x)**2+1)*inverse) % left
    m = int(right.degree())
    block_width = max(1, math.isqrt((5*m+1)//2))
    products = 0

    def modular_mul(u, v):
        nonlocal products
        products += 1
        return (u*v) % left

    def by_y(pair):
        u, v = pair
        return modular_mul(v, beta), u + modular_mul(v, alpha)

    def multiply(pair, other):
        u, v = pair
        w, z = other
        uw = modular_mul(u, w)
        vz = modular_mul(v, z)
        cross = modular_mul(u+v, w+z) + uw + vz
        return uw + modular_mul(beta, vz), cross + modular_mul(alpha, vz)

    baby = [(ring.one(), ring.zero())]
    for _ in range(1, block_width):
        baby.append(by_y(baby[-1]))
    giant = by_y(baby[-1])
    coefficients = right.list()
    blocks = []
    for offset in range(0, len(coefficients), block_width):
        u = ring.zero()
        v = ring.zero()
        for coeff, (bu, bv) in zip(coefficients[offset:offset+block_width], baby):
            if coeff:
                u += coeff*bu
                v += coeff*bv
        blocks.append((u, v))
    value = blocks[-1]
    for block in reversed(blocks[:-1]):
        u, v = multiply(value, giant)
        value = u + block[0], v + block[1]
    u, v = value
    norm = (modular_mul(u,u) + modular_mul(alpha, modular_mul(u,v)) +
            modular_mul(beta, modular_mul(v,v))) % left
    return left.gcd(norm), norm, {"block_width": block_width,
                                 "baby_powers": len(baby), "blocks": len(blocks),
                                 "modular_polynomial_products": products}


def main():
    protocol_path = HERE / "bsgs_protocol.json"
    protocol = json.loads(protocol_path.read_text())
    for name, path in (("source", Path(__file__)), ("helper", HERE / "run.py"),
                       ("geometry", GEOMETRY), ("generic", HERE / "result.json"),
                       ("horner", HERE / "norm_result.json"),
                       ("runtime", HERE / "sage_runtime_info.json")):
        assert sha(path) == protocol["sha256"][name], name
    assert not (HERE / "bsgs_result.json").exists()
    started = time.monotonic_ns()
    geometry = json.loads(GEOMETRY.read_text())["n41"]
    reference = json.loads((HERE / "norm_result.json").read_text())
    f = Field()
    binary = PolynomialRing(GF(2), "t")
    t = binary.gen()
    field = GF(2**41, name="t", modulus=t**41+t**3+1)

    def decode(value):
        return field(binary([(value >> i) & 1 for i in range(41)]))

    ring = PolynomialRing(field, "X")
    x = ring.gen()
    target = decode(protocol["residual"][0])
    cases = []
    for label, seeds in protocol["cases"].items():
        setup_start = time.monotonic_ns()
        left_keys = build_bucket(f, geometry["point_rows_by_unique_rotation"]["20"], seeds[0])
        right_keys = build_bucket(f, geometry["point_rows_by_unique_rotation"]["30"], seeds[1])
        left = ring.prod(x+decode(key) for key in left_keys)
        right = ring.prod(x+decode(key) for key in right_keys)
        setup_ns = time.monotonic_ns()-setup_start
        query_start = time.monotonic_ns()
        gcd, norm, operations = bsgs_bucket_norm(left, right, target)
        query_ns = time.monotonic_ns()-query_start
        roots = sorted(encode(root) for root, mult in gcd.roots() if mult >= 1)
        old = next(case for case in reference["cases"] if case["label"] == label)
        assert roots == old["gcd_roots"]
        cases.append({"label": label, "seeds": seeds, "left_degree": int(left.degree()),
                      "right_degree": int(right.degree()), "gcd_degree": int(gcd.degree()),
                      "gcd_roots": roots, "norm_remainder_degree": int(norm.degree()),
                      "setup_ns": setup_ns, "target_bsgs_norm_gcd_ns": query_ns,
                      "horner_target_norm_gcd_ns": old["target_norm_gcd_ns"], **operations})
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    peak = peak if sys.platform == "darwin" else peak*1024
    result = {"status": "COMPLETE_BUCKET_DIAGNOSTIC", "proposal_id": protocol["proposal_id"],
              "candidate_id": None, "target_count": 1, "curve_id": geometry["curve_id"],
              "source_sha256": sha(Path(__file__)), "protocol_sha256": sha(protocol_path),
              "horner_result_sha256": sha(HERE / "norm_result.json"),
              "public_target_q": protocol["public_target_q"], "residual": protocol["residual"],
              "cases": cases, "elapsed_wall_ns": time.monotonic_ns()-started,
              "peak_rss_bytes": peak}
    assert result["elapsed_wall_ns"] < protocol["wall_cap_seconds"]*10**9
    assert peak < protocol["rss_cap_bytes"]
    with (HERE / "bsgs_result.json").open("x") as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"status": result["status"], "cases": [{"label": case["label"],
                      "gcd_roots": case["gcd_roots"], "products": case["modular_polynomial_products"],
                      "query_ns": case["target_bsgs_norm_gcd_ns"]} for case in cases]}))


if __name__ == "__main__":
    main()

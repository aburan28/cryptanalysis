#!/usr/bin/env python3
"""Compute pair-bucket compatibility as a norm modulo the left image."""

import hashlib
import json
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


def bucket_norm(left, right, target):
    """Return gcd(left, Res_Y(right, S3(X,Y,target))) without a resultant.

    Work in A=K[X]/left.  For S3=aY^2+bY+c with unit a, put
    alpha=b/a and beta=c/a.  Horner reduction yields right(Y)=u+vY;
    its norm is u^2+alpha*u*v+beta*v^2 in A.  The omitted factor a^deg(right)
    is a unit modulo left, so the gcd is unchanged.
    """
    ring = left.parent()
    x = ring.gen()
    a = (x + target)**2 % left
    if a.gcd(left).degree() != 0:
        raise ValueError("nonunit leading S3 coefficient: generic fallback required")
    inv = a.inverse_mod(left)
    alpha = (target * x * inv) % left
    beta = (((target * x)**2 + 1) * inv) % left
    u = ring.zero()
    v = ring.zero()
    for coefficient in reversed(right.list()):
        u, v = (v * beta + coefficient) % left, (u + v * alpha) % left
    norm = (u*u + alpha*u*v + beta*v*v) % left
    return left.gcd(norm), norm


def main():
    protocol_path = HERE / "norm_protocol.json"
    protocol = json.loads(protocol_path.read_text())
    for name, path in (("source", Path(__file__)), ("helper", HERE / "run.py"),
                       ("geometry", GEOMETRY), ("generic", HERE / "result.json"),
                       ("runtime", HERE / "sage_runtime_info.json")):
        assert sha(path) == protocol["sha256"][name], name
    assert not (HERE / "norm_result.json").exists()
    started = time.monotonic_ns()
    geometry = json.loads(GEOMETRY.read_text())["n41"]
    generic = json.loads((HERE / "result.json").read_text())
    f = Field()
    binary = PolynomialRing(GF(2), "t")
    t = binary.gen()
    field = GF(2**41, name="t", modulus=t**41 + t**3 + 1)

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
        left = ring.prod(x + decode(key) for key in left_keys)
        right = ring.prod(x + decode(key) for key in right_keys)
        setup_ns = time.monotonic_ns() - setup_start
        query_start = time.monotonic_ns()
        gcd, norm = bucket_norm(left, right, target)
        query_ns = time.monotonic_ns() - query_start
        roots = sorted(encode(root) for root, multiplicity in gcd.roots()
                       if multiplicity >= 1)
        old = next(c for c in generic["cases"] if c["label"] == label)
        assert roots == old["gcd_roots"]
        assert int(gcd.degree()) == old["gcd_degree"]
        cases.append({"label": label, "seeds": seeds, "left_degree": int(left.degree()),
                      "right_degree": int(right.degree()), "gcd_degree": int(gcd.degree()),
                      "gcd_roots": roots, "norm_remainder_degree": int(norm.degree()),
                      "setup_ns": setup_ns, "target_norm_gcd_ns": query_ns,
                      "generic_target_resultant_gcd_ns": old["target_resultant_ns"] +
                                                          old["target_gcd_ns"]})
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    peak = peak if sys.platform == "darwin" else peak * 1024
    result = {"status": "COMPLETE_BUCKET_DIAGNOSTIC", "proposal_id": protocol["proposal_id"],
              "candidate_id": None, "target_count": 1, "curve_id": geometry["curve_id"],
              "public_target_q": protocol["public_target_q"], "residual": protocol["residual"],
              "source_sha256": sha(Path(__file__)), "protocol_sha256": sha(protocol_path),
              "generic_result_sha256": sha(HERE / "result.json"), "cases": cases,
              "elapsed_wall_ns": time.monotonic_ns() - started, "peak_rss_bytes": peak}
    assert result["elapsed_wall_ns"] < protocol["wall_cap_seconds"] * 10**9
    assert peak < protocol["rss_cap_bytes"]
    with (HERE / "norm_result.json").open("x") as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"status": result["status"],
                      "cases": [{"label": c["label"], "gcd_degree": c["gcd_degree"],
                                 "target_norm_gcd_ns": c["target_norm_gcd_ns"]}
                                for c in cases]}), flush=True)


if __name__ == "__main__":
    main()

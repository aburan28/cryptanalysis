#!/usr/bin/env python3
"""Eliminate both unfiltered W6 pair-output families in an N41 S3 link."""

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
PRIOR = BASE / "n41_seed_sum_s3_bucket_norm_20261010/batch_result.json"
PREVIOUS = BASE / "n41_w6_subspace_norm_20261010/result.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def encode(value):
    return sum(int(c) << i for i, c in enumerate(value.polynomial()))


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


def product(values):
    values = list(values)
    if not values:
        raise ValueError("empty product")
    while len(values) > 1:
        values = [values[i]*values[i+1] if i+1 < len(values) else values[i]
                  for i in range(0, len(values), 2)]
    return values[0]


def seed_bucket(F, basis_u, s):
    us = coordinate(basis_u, s)
    ws = us**2+us
    basis_w = [u**2+u for u in basis_u]
    values = {coordinate(basis_w, a)**2+ws*coordinate(basis_w, a)
              for a in range(64)}
    if len(values) != 32:
        raise AssertionError("seed-product image dimension changed")
    return us**2, sorted(values, key=encode)


def pair_output_polynomial(ring, u2, products):
    Z = ring.gen()
    return product((1+p)*Z**2+p*Z+u2 for p in products)


def target_resultant(ring, t, u2, products):
    # Res_B((1+C)B^2+CB+D, (1+p)B^2+pB+u2)
    # = M^2+L*N, with M=(1+C)u2+(1+p)D,
    # L=p+C, N=C*u2+p*D.  This is a polynomial in the left coordinate Z.
    Z = ring.gen()
    C = (Z**2+Z)*(t**2+t)
    D = (Z+t)**2
    alpha = 1+C
    return product(((alpha*u2+(1+p)*D)**2
                    +(p+C)*(C*u2+p*D)) for p in products)


def rss_bytes():
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return value if sys.platform == "darwin" else value*1024


def main():
    output = HERE / "result.json"
    if output.exists():
        raise FileExistsError(output)
    protocol_path = HERE / "protocol.json"
    protocol = json.loads(protocol_path.read_text())
    for key, path in (("source", Path(__file__)), ("geometry", GEOMETRY),
                      ("prior", PRIOR), ("previous", PREVIOUS),
                      ("runtime", HERE / "sage_runtime_info.json")):
        if sha(path) != protocol["sha256"][key]:
            raise ValueError("frozen digest mismatch: " + key)
    binary = PolynomialRing(GF(2), "t")
    t0 = binary.gen()
    F = GF(2**41, "t", modulus=t0**41+t0**3+1)
    E = EllipticCurve(F, [1, 0, 0, 0, 1])
    ring = PolynomialRing(F, "Z")
    geometry = json.loads(GEOMETRY.read_text())["n41"]
    bases = [[lift(F, value) for value in row]
             for row in geometry["window_basis_halftrace"]]
    started_setup = time.monotonic_ns()
    left_buckets = [seed_bucket(F, bases[2], s) for s in range(1, 64)]
    right_buckets = [seed_bucket(F, bases[3], s) for s in range(1, 64)]
    left_polynomials = [pair_output_polynomial(ring, u2, values)
                        for u2, values in left_buckets]
    left_global = product(left_polynomials)
    setup_ns = time.monotonic_ns()-started_setup
    if rss_bytes() > protocol["rss_cap_bytes"]:
        raise MemoryError("setup exceeded frozen RSS cap")
    cases = []
    torsion = E(F.one(), F.zero())
    if 4*torsion != E(0):
        raise AssertionError("order-four point changed")
    inverse_four = pow(4, -1, geometry["subgroup_order"])
    for kind in ("positive", "negative"):
        case_started = time.monotonic_ns()
        transport_started = time.monotonic_ns()
        residual = protocol[kind+"_residual"]
        projected = E(lift(F, residual[0]), lift(F, residual[1]))
        target_options = [inverse_four*projected+j*torsion for j in range(4)]
        if len(set(target_options)) != 4 or any(4*P != projected for P in target_options):
            raise AssertionError("target preimage fiber changed")
        transport_ns = time.monotonic_ns()-transport_started
        norm_ns = gcd_ns = root_ns = 0
        status = "COMPLETE"
        completed = 0
        hits = []
        for option, target in enumerate(target_options):
            if target[0] == 1:
                raise AssertionError("exceptional transformed target")
            t = 1/(target[0]+1)
            for right_sum, (u2, values) in enumerate(right_buckets, 1):
                begin = time.monotonic_ns()
                norm = target_resultant(ring, t, u2, values)
                norm_ns += time.monotonic_ns()-begin
                begin = time.monotonic_ns()
                common = norm.gcd(left_global)
                gcd_ns += time.monotonic_ns()-begin
                completed += 1
                if common.degree() > 0:
                    begin = time.monotonic_ns()
                    roots = common.roots(multiplicities=False)
                    root_ns += time.monotonic_ns()-begin
                    hits.append({"target_preimage": option, "right_sum": right_sum,
                                 "gcd_degree": int(common.degree()),
                                 "rational_root_count": len(roots),
                                 "raw_left_x": [None if z == 0 else encode(1+1/z)
                                                for z in roots]})
                if (time.monotonic_ns()-case_started >
                        protocol["case_wall_cap_seconds"]*10**9):
                    status = "CENSORED_TIME"
                    break
                if rss_bytes() > protocol["rss_cap_bytes"]:
                    status = "CENSORED_MEMORY"
                    break
            if status != "COMPLETE":
                break
        elapsed_ns = time.monotonic_ns()-case_started
        cases.append({"kind": kind, "status": status,
                      "right_bucket_target_preimage_checks": completed,
                      "hits": hits, "transport_ns": transport_ns,
                      "norm_build_ns": norm_ns, "gcd_ns": gcd_ns,
                      "root_ns": root_ns,
                      "other_ns": elapsed_ns-transport_ns-norm_ns-gcd_ns-root_ns,
                      "query_wall_ns": elapsed_ns,
                      "peak_rss_bytes": rss_bytes()})
    result = {"status": "COMPLETE_DIAGNOSTIC" if all(
        row["status"] == "COMPLETE" for row in cases) else "CENSORED_DIAGNOSTIC",
              "candidate_id": None, "proposal_id": protocol["proposal_id"],
              "target_count": 0, "source_sha256": sha(Path(__file__)),
              "protocol_sha256": sha(protocol_path),
              "left_polynomial_degree": int(left_global.degree()),
              "left_bucket_degree_min": min(int(p.degree()) for p in left_polynomials),
              "left_bucket_degree_max": max(int(p.degree()) for p in left_polynomials),
              "setup_ns": setup_ns, "cases": cases,
              "peak_rss_bytes": rss_bytes()}
    with output.open("x") as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"status": result["status"],
                      "left_degree": result["left_polynomial_degree"],
                      "cases": [{"kind": x["kind"], "status": x["status"],
                                 "checks": x["right_bucket_target_preimage_checks"],
                                 "hits": len(x["hits"]),
                                 "wall_s": round(x["query_wall_ns"]/1e9, 3)}
                                for x in cases]}))


if __name__ == "__main__":
    main()

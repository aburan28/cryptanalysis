#!/usr/bin/env python3
"""Test two free fixed-seed pair families by a compact S3 norm and GCD."""

import argparse
import hashlib
import importlib.util
import json
import resource
import sys
import time
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
PREVIOUS = BASE / "n41_linearized_bucket_composition_20261011/run.py"
GEOMETRY = BASE / "n41_two_free_pair_occupancy_20261009/geometry_snapshot.json"

spec = importlib.util.spec_from_file_location("compact_bucket_control", PREVIOUS)
control = importlib.util.module_from_spec(spec)
spec.loader.exec_module(control)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compact_pair_polynomial(ring, u2, basis):
    coefficients = [ring.base_ring().one()]
    for value in basis:
        at_value = sum((c*value**(1 << i) for i, c in enumerate(coefficients)),
                       ring.base_ring().zero())
        raised = [ring.base_ring().zero()] + [c*c for c in coefficients]
        for i, c in enumerate(coefficients):
            raised[i] += at_value*c
        coefficients = raised
    Z = ring.gen()
    A, D = Z*Z+u2, Z*Z+Z
    degree = 1 << len(basis)
    return sum((c*A**(1 << i)*D**(degree-(1 << i))
                for i, c in enumerate(coefficients)), ring.zero())


def compact_target_norm(ring, target, u2, basis):
    """Product of all S3 right factors by division-free subspace doubling."""
    Z = ring.gen()
    C = (Z*Z+Z)*(target*target+target)
    D = (Z+target)**2
    alpha = 1+C
    A = (alpha*u2+D)**2+C*C*u2
    B = C*(u2+D)
    E = D*D+D
    values = [A] + [B*v+E*v*v for v in basis]
    updates = 0
    for i in range(len(basis)):
        pivot = values[i+1]
        values[0] = values[0]*values[0]+pivot*values[0]
        updates += 1
        for j in range(i+2, len(values)):
            values[j] = values[j]*values[j]+pivot*values[j]
            updates += 1
    assert updates == len(basis)*(len(basis)+1)//2
    return values[0], updates


def direct_target_norm(ring, target, u2, products):
    Z = ring.gen()
    C = (Z*Z+Z)*(target*target+target)
    D = (Z+target)**2
    alpha = 1+C
    answer = ring.one()
    for p in products:
        m = alpha*u2+(1+p)*D
        answer *= m*m+(p+C)*(C*u2+p*D)
    return answer


def rss_bytes():
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return value if sys.platform == "darwin" else value*1024


def setup():
    binary = PolynomialRing(GF(2), "t")
    t0 = binary.gen()
    field = GF(2**41, "t", modulus=t0**41+t0**3+1)
    curve = EllipticCurve(field, [1, 0, 0, 0, 1])
    ring = PolynomialRing(field, "Z")
    geometry = json.loads(GEOMETRY.read_text())["n41"]
    u_bases = [[control.element(field, bits) for bits in row]
               for row in geometry["window_basis_halftrace"]]
    w_bases = [[u*u+u for u in row] for row in u_bases]
    left = {s: control.seed_data(w_bases[2], u_bases[2], s) for s in range(1, 64)}
    right = {s: control.seed_data(w_bases[3], u_bases[3], s) for s in range(1, 64)}
    polynomials = {s: compact_pair_polynomial(ring, data[0], data[1])
                   for s, data in left.items()}
    assert all(p.degree() <= 64 for p in polynomials.values())
    return field, curve, ring, geometry, left, right, polynomials


def raw_targets(field, curve, geometry, projected_xy):
    projected = curve(*(control.element(field, v) for v in projected_xy))
    torsion = curve(field.one(), field.zero())
    inverse_four = pow(4, -1, geometry["subgroup_order"])
    points = [inverse_four*projected+j*torsion for j in range(4)]
    assert all(4*point == projected for point in points)
    return points


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", action="store_true")
    args = parser.parse_args()
    protocol_path = HERE / "protocol.json"
    protocol = json.loads(protocol_path.read_text())
    for key, path in (("source", Path(__file__)), ("previous", PREVIOUS),
                      ("geometry", GEOMETRY), ("runtime", HERE / "sage_runtime_info.json")):
        if sha(path) != protocol["sha256"][key]:
            raise ValueError("frozen digest mismatch: " + key)
    setup_start = time.monotonic_ns()
    field, curve, ring, geometry, left, right, left_polys = setup()
    setup_ns = time.monotonic_ns()-setup_start
    if args.profile:
        checks = []
        for kind in ("positive", "negative"):
            points = raw_targets(field, curve, geometry, protocol[kind+"_residual"])
            for option, point in enumerate(points):
                if point[0] == 1:
                    continue
                target = 1/(point[0]+1)
                for right_seed in (5, 17):
                    u2, basis, products = right[right_seed]
                    start = time.monotonic_ns()
                    norm, updates = compact_target_norm(ring, target, u2, basis)
                    assert norm == direct_target_norm(ring, target, u2, products)
                    common = norm.gcd(left_polys[16])
                    checks.append({"kind": kind, "option": option,
                                   "right_seed": right_seed,
                                   "left_seed": 16, "norm_degree": int(norm.degree()),
                                   "gcd_degree": int(common.degree()),
                                   "updates": updates,
                                   "elapsed_ms": (time.monotonic_ns()-start)/1e6})
        print(json.dumps({"profile": checks, "setup_ms": setup_ns/1e6,
                          "peak_rss_bytes": rss_bytes()}))
        return
    rows = []
    for kind in ("positive", "negative"):
        targets = raw_targets(field, curve, geometry, protocol[kind+"_residual"])
        for option, point in enumerate(targets):
            started = time.monotonic_ns()
            norm_ns = gcd_ns = root_ns = 0
            completed_right_seeds = 0
            completed_bucket_pairs = 0
            hits = []
            status = "COMPLETE"
            if point[0] == 1:
                raise AssertionError("exceptional target reciprocal")
            target = 1/(point[0]+1)
            for right_seed, (u2, basis, products) in right.items():
                begin = time.monotonic_ns()
                norm, updates = compact_target_norm(ring, target, u2, basis)
                norm_ns += time.monotonic_ns()-begin
                for left_seed, left_poly in left_polys.items():
                    begin = time.monotonic_ns()
                    common = norm.gcd(left_poly)
                    gcd_ns += time.monotonic_ns()-begin
                    completed_bucket_pairs += 1
                    if common.degree() > 0:
                        begin = time.monotonic_ns()
                        roots = [control.integer(z) for z in common.roots(multiplicities=False)]
                        root_ns += time.monotonic_ns()-begin
                        hits.append({"left_seed": left_seed,
                                     "right_seed": right_seed,
                                     "common_degree": int(common.degree()),
                                     "left_roots": roots})
                completed_right_seeds += 1
                if rss_bytes() >= protocol["rss_cap_bytes"]:
                    status = "CENSORED_MEMORY"
                    break
                if time.monotonic_ns()-started >= protocol["raw_option_wall_cap_seconds"]*10**9:
                    status = "CENSORED_TIME"
                    break
            wall_ns = time.monotonic_ns()-started
            rows.append({"kind": kind, "raw_target_option": option,
                         "raw_target": [control.integer(point[0]), control.integer(point[1])],
                         "status": status, "right_seeds": completed_right_seeds,
                         "bucket_pairs": completed_bucket_pairs, "hits": hits,
                         "norm_ns": norm_ns, "gcd_ns": gcd_ns, "root_ns": root_ns,
                         "other_ns": wall_ns-norm_ns-gcd_ns-root_ns,
                         "wall_ns": wall_ns, "peak_rss_bytes": rss_bytes()})
            print(json.dumps({"kind": kind, "option": option, "status": status,
                              "bucket_pairs": completed_bucket_pairs,
                              "hits": len(hits), "wall_s": wall_ns/1e9}), flush=True)
    result = {"status": "COMPLETE_EXACT_COMPONENT" if all(x["status"] == "COMPLETE" for x in rows)
              else "CENSORED_COMPONENT", "candidate_id": None,
              "proposal_id": protocol["proposal_id"], "target_count": 0,
              "source_sha256": sha(Path(__file__)), "protocol_sha256": sha(protocol_path),
              "setup_ns": setup_ns, "left_bucket_polynomial_count": len(left_polys),
              "left_bucket_degree_min": min(int(p.degree()) for p in left_polys.values()),
              "left_bucket_degree_max": max(int(p.degree()) for p in left_polys.values()),
              "right_image_rank": 5, "linearized_updates_per_right_seed": 15,
              "rows": rows, "peak_rss_bytes": rss_bytes()}
    with (HERE / "result.json").open("x") as stream:
        json.dump(result, stream, sort_keys=True, indent=2)
        stream.write("\n")
    print(json.dumps({"status": result["status"], "rows": len(rows),
                      "total_bucket_pairs": sum(row["bucket_pairs"] for row in rows)}))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Batch 63 right seed-sum resultants before the left-family GCD."""

import hashlib
import json
import resource
import sys
import time
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing

HERE = Path(__file__).resolve().parent
import run_sage as base  # noqa: E402


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rss_bytes():
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return value if sys.platform == "darwin" else value*1024


def main():
    output = HERE / "batch_result.json"
    if output.exists():
        raise FileExistsError(output)
    protocol_path = HERE / "batch_protocol.json"
    protocol = json.loads(protocol_path.read_text())
    files = {"source": Path(__file__), "base_source": HERE / "run_sage.py",
             "v1_result": HERE / "result.json",
             "geometry": base.GEOMETRY,
             "prior": base.PRIOR,
             "runtime": HERE / "sage_runtime_info_v2.json"}
    for key, path in files.items():
        if sha(path) != protocol["sha256"][key]:
            raise ValueError("frozen digest mismatch: " + key)
    binary = PolynomialRing(GF(2), "t")
    t0 = binary.gen()
    F = GF(2**41, "t", modulus=t0**41+t0**3+1)
    E = EllipticCurve(F, [1, 0, 0, 0, 1])
    ring = PolynomialRing(F, "Z")
    geometry = json.loads(base.GEOMETRY.read_text())["n41"]
    bases = [[base.lift(F, value) for value in row]
             for row in geometry["window_basis_halftrace"]]
    started_setup = time.monotonic_ns()
    left_buckets = [base.seed_bucket(F, bases[2], s) for s in range(1, 64)]
    right_buckets = [base.seed_bucket(F, bases[3], s) for s in range(1, 64)]
    left_global = base.product(base.pair_output_polynomial(ring, u2, values)
                               for u2, values in left_buckets)
    setup_ns = time.monotonic_ns()-started_setup
    if left_global.degree() != 4032 or rss_bytes() > protocol["rss_cap_bytes"]:
        raise AssertionError("frozen left setup gate changed")
    torsion = E(F.one(), F.zero())
    if 4*torsion != E(0):
        raise AssertionError("order-four point changed")
    inverse_four = pow(4, -1, geometry["subgroup_order"])
    cases = []
    for kind in ("positive", "negative"):
        case_started = time.monotonic_ns()
        transport_started = time.monotonic_ns()
        residual = protocol[kind+"_residual"]
        projected = E(base.lift(F, residual[0]), base.lift(F, residual[1]))
        targets = [inverse_four*projected+j*torsion for j in range(4)]
        if len(set(targets)) != 4 or any(4*P != projected for P in targets):
            raise AssertionError("target preimage fiber changed")
        transport_ns = time.monotonic_ns()-transport_started
        norm_ns = batch_ns = gcd_ns = root_ns = classify_ns = 0
        completed = 0
        status = "COMPLETE"
        hits = []
        for option, target in enumerate(targets):
            if target[0] == 1:
                raise AssertionError("exceptional transformed target")
            t = 1/(target[0]+1)
            begin = time.monotonic_ns()
            norms = [base.target_resultant(ring, t, u2, values)
                     for u2, values in right_buckets]
            norm_ns += time.monotonic_ns()-begin
            begin = time.monotonic_ns()
            batched = base.product(norms)
            batch_ns += time.monotonic_ns()-begin
            begin = time.monotonic_ns()
            common = batched.gcd(left_global)
            gcd_ns += time.monotonic_ns()-begin
            if common.degree() > 0:
                begin = time.monotonic_ns()
                roots = common.roots(multiplicities=False)
                root_ns += time.monotonic_ns()-begin
                for root in roots:
                    begin = time.monotonic_ns()
                    matching = [s for s, norm in enumerate(norms, 1) if norm(root) == 0]
                    classify_ns += time.monotonic_ns()-begin
                    hits.append({"target_preimage": option,
                                 "raw_left_x": None if root == 0 else base.encode(1+1/root),
                                 "right_sums": matching})
            completed += 1
            if (time.monotonic_ns()-case_started >
                    protocol["case_wall_cap_seconds"]*10**9):
                status = "CENSORED_TIME"
                break
            if rss_bytes() > protocol["rss_cap_bytes"]:
                status = "CENSORED_MEMORY"
                break
        elapsed_ns = time.monotonic_ns()-case_started
        cases.append({"kind": kind, "status": status,
                      "preimages_checked": completed, "hits": hits,
                      "transport_ns": transport_ns, "norm_build_ns": norm_ns,
                      "batch_product_ns": batch_ns, "gcd_ns": gcd_ns,
                      "root_ns": root_ns, "classify_ns": classify_ns,
                      "other_ns": elapsed_ns-transport_ns-norm_ns-batch_ns-gcd_ns-root_ns-classify_ns,
                      "query_wall_ns": elapsed_ns,
                      "peak_rss_bytes": rss_bytes()})
    result = {"status": "COMPLETE_DIAGNOSTIC" if all(
        row["status"] == "COMPLETE" for row in cases) else "CENSORED_DIAGNOSTIC",
              "candidate_id": None, "proposal_id": protocol["proposal_id"],
              "target_count": 0, "source_sha256": sha(Path(__file__)),
              "protocol_sha256": sha(protocol_path),
              "left_polynomial_degree": int(left_global.degree()),
              "setup_ns": setup_ns, "cases": cases,
              "peak_rss_bytes": rss_bytes()}
    with output.open("x") as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"status": result["status"],
                      "cases": [{"kind": x["kind"], "status": x["status"],
                                 "preimages": x["preimages_checked"],
                                 "hits": len(x["hits"]),
                                 "wall_s": round(x["query_wall_ns"]/1e9, 3)}
                                for x in cases]}))


if __name__ == "__main__":
    main()

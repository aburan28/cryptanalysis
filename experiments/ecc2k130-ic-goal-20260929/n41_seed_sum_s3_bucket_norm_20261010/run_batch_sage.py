#!/usr/bin/env python3
"""Batch S3 norms against one target-independent left-domain polynomial."""

import hashlib
import json
import resource
import signal
import sys
import time
from pathlib import Path

from sage.all import GF, PolynomialRing, EllipticCurve

import run_sage as base

HERE = Path(__file__).resolve().parent
BASE = HERE.parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rss_bytes():
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * (
        1 if sys.platform == "darwin" else 1024)


def alarm_handler(_signum, _frame):
    raise TimeoutError("frozen batched residual wall cap reached")


def main():
    output = HERE / "batch_result.json"
    if output.exists():
        raise FileExistsError(output)
    protocol_path = HERE / "batch_protocol.json"
    protocol = json.loads(protocol_path.read_text())
    for key, path in [("source", Path(__file__)), ("base_source", HERE / "run_sage.py"),
                      ("base_result", HERE / "result.json"),
                      ("geometry", base.GEOMETRY),
                      ("runtime", HERE / "sage_runtime_info.json")]:
        if sha(path) != protocol["sha256"][key]:
            raise ValueError("frozen digest mismatch: " + key)
    binary = PolynomialRing(GF(2), "t")
    t0 = binary.gen()
    F = GF(2**41, "t", modulus=t0**41 + t0**3 + 1)
    E = EllipticCurve(F, [1, 0, 0, 0, 1])
    ring = PolynomialRing(F, "Z")
    Z = ring.gen()
    geometry = json.loads(base.GEOMETRY.read_text())["n41"]
    source = geometry["point_rows_by_unique_rotation"]
    setup_started = time.monotonic_ns()
    left = base.pair_buckets(E, F, source["20"])
    right = base.pair_buckets(E, F, source["30"])
    reverse = {}
    for seed_sum, bucket in left.items():
        for x in bucket:
            reverse.setdefault(x, []).append(seed_sum)
    all_x = sorted(reverse)
    assert len(all_x) == 978
    global_left = base.product(Z + base.lift(F, x) for x in all_x)
    setup_ns = time.monotonic_ns() - setup_started
    assert global_left.degree() == 978
    if rss_bytes() > protocol["rss_cap_bytes"]:
        raise MemoryError("frozen batch setup RSS cap reached")
    signal.signal(signal.SIGALRM, alarm_handler)
    rows = []
    for kind in ("positive", "negative"):
        residual = protocol[kind + "_residual"]
        target_point = E(base.lift(F, residual[0]), base.lift(F, residual[1]))
        target_x = target_point[0]
        signal.alarm(protocol["residual_wall_cap_seconds"])
        started = time.monotonic_ns()
        status = "COMPLETE"
        failure = None
        norm_ns = gcd_ns = extraction_ns = 0
        right_buckets_checked = 0
        gcd_calls = 0
        bucket_pairs_hit = 0
        x_hits = 0
        max_norm_degree = 0
        witness = None
        try:
            for right_sum in range(1, 64):
                begin = time.monotonic_ns()
                norm = base.product(((b+target_x)**2 * Z**2 + b*target_x*Z +
                                     b**2*target_x**2 + 1)
                                    for b in (base.lift(F, x) for x in right[right_sum]))
                norm_ns += time.monotonic_ns() - begin
                max_norm_degree = max(max_norm_degree, int(norm.degree()))
                begin = time.monotonic_ns()
                common = global_left.gcd(norm)
                gcd_ns += time.monotonic_ns() - begin
                gcd_calls += 1
                if common.degree() > 0:
                    begin = time.monotonic_ns()
                    matching_x = [x for x in all_x if norm(base.lift(F, x)) == 0]
                    if len(matching_x) != int(common.degree()):
                        raise AssertionError("batch gcd/root count mismatch")
                    x_hits += len(matching_x)
                    for x in matching_x:
                        for left_sum in reverse[x]:
                            bucket_pairs_hit += 1
                            if witness is None:
                                row = base.witness_for_bucket_pair(
                                    E, F, target_point, left[left_sum], right[right_sum],
                                    norm, [x])
                                if row is None:
                                    raise AssertionError("batch root lacks group lift")
                                row["left_seed_sum"] = left_sum
                                row["right_seed_sum"] = right_sum
                                witness = row
                    extraction_ns += time.monotonic_ns() - begin
                right_buckets_checked += 1
                if rss_bytes() > protocol["rss_cap_bytes"]:
                    raise MemoryError("frozen batch RSS cap reached")
        except Exception as error:
            if isinstance(error, TimeoutError):
                status = "CENSORED_TIME"
            elif isinstance(error, MemoryError):
                status = "CENSORED_MEMORY"
            else:
                status = "PRODUCER_FAILURE"
            failure = str(error)
        finally:
            signal.alarm(0)
        total_ns = time.monotonic_ns() - started
        rows.append({"kind": kind, "residual": residual, "status": status,
                     "failure": failure, "right_buckets_checked": right_buckets_checked,
                     "gcd_calls": gcd_calls, "bucket_pairs_with_gcd": bucket_pairs_hit,
                     "matching_x_count": x_hits, "max_norm_degree": max_norm_degree,
                     "first_group_witness": witness,
                     "norm_build_ns": norm_ns, "gcd_ns": gcd_ns,
                     "root_extraction_ns": extraction_ns,
                     "other_online_ns": total_ns-norm_ns-gcd_ns-extraction_ns,
                     "online_wall_ns": total_ns, "peak_rss_bytes": rss_bytes()})
    result = {"status": "COMPLETE_DIAGNOSTIC", "proposal_id": protocol["proposal_id"],
              "candidate_id": None, "target_count": 0,
              "source_sha256": sha(Path(__file__)),
              "protocol_sha256": sha(protocol_path), "setup_ns": setup_ns,
              "global_left_degree": int(global_left.degree()),
              "cases": rows, "peak_rss_bytes": rss_bytes()}
    with output.open("x") as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"status": result["status"],
                      "cases": [{"kind": row["kind"], "status": row["status"],
                                 "hits": row["bucket_pairs_with_gcd"],
                                 "gcd_calls": row["gcd_calls"],
                                 "online_s": round(row["online_wall_ns"]/1e9, 3)}
                                for row in rows]}))


if __name__ == "__main__":
    main()

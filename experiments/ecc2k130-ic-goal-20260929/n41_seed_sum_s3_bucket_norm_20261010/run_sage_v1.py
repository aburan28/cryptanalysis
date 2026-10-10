#!/usr/bin/env python3
"""Exact target-conditioned S3 norm on N41 seed-sum output buckets."""

import hashlib
import json
import resource
import signal
import sys
import time
from pathlib import Path

from sage.all import GF, PolynomialRing, EllipticCurve

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
GEOMETRY = BASE / "n41_two_free_pair_occupancy_20261009/geometry_snapshot.json"
PRIOR = BASE / "n41_two_free_pair_s3_norm_20261008/native_controls.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def lift(F, value):
    t = F.gen()
    out = F.zero()
    while value:
        bit = value.bit_length() - 1
        out += t**bit
        value ^= 1 << bit
    return out


def encode(value):
    return sum(int(c) << i for i, c in enumerate(value.polynomial()))


def rss_bytes():
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * (
        1 if sys.platform == "darwin" else 1024)


def alarm_handler(_signum, _frame):
    raise TimeoutError("frozen residual wall cap reached")


def pair_buckets(E, F, rows):
    points = [E(lift(F, row[0]), lift(F, row[1])) for row in rows]
    grouped = {s: {} for s in range(1, 64)}
    accepted = 0
    for i, left in enumerate(rows):
        for j in range(i + 1, len(rows)):
            if left[2] == rows[j][2]:
                continue
            total = points[i] + points[j]
            s = left[3] ^ rows[j][3]
            x = encode(total[0])
            grouped[s].setdefault(x, []).append((total, i, j))
            accepted += 1
    if accepted != 1956 or len({x for bucket in grouped.values() for x in bucket}) != 978:
        raise AssertionError("pair-domain census changed")
    return grouped


def product(polynomials):
    values = list(polynomials)
    while len(values) > 1:
        values = [values[i] * values[i+1] if i+1 < len(values) else values[i]
                  for i in range(0, len(values), 2)]
    return values[0]


def witness_for_bucket_pair(E, F, target_point, left, right, norm, a_roots):
    for a_int in a_roots:
        a = lift(F, a_int)
        if norm(a) != 0:
            continue
        for b_int in right:
            b = lift(F, b_int)
            c = a*b + (a+b)*target_point[0]
            if c*c + a*b*target_point[0] + 1 != 0:
                continue
            for lp, li, lj in left[a_int]:
                for rp, ri, rj in right[b_int]:
                    if lp + rp == target_point:
                        return {"a": a_int, "b": b_int,
                                "left_source_indices": [li, lj],
                                "right_source_indices": [ri, rj],
                                "left_pair_point": [encode(lp[0]), encode(lp[1])],
                                "right_pair_point": [encode(rp[0]), encode(rp[1])]}
    return None


def main():
    output = HERE / "result.json"
    if output.exists():
        raise FileExistsError(output)
    protocol = json.loads((HERE / "protocol.json").read_text())
    for key, path in [("sage_source", Path(__file__)), ("geometry", GEOMETRY),
                      ("prior_native_controls", PRIOR),
                      ("runtime", HERE / "sage_runtime_info.json")]:
        if sha(path) != protocol["sha256"][key]:
            raise ValueError("frozen digest mismatch: " + key)
    binary = PolynomialRing(GF(2), "t")
    t0 = binary.gen()
    F = GF(2**41, "t", modulus=t0**41 + t0**3 + 1)
    E = EllipticCurve(F, [1, 0, 0, 0, 1])
    ring = PolynomialRing(F, "Z")
    Z = ring.gen()
    geometry = json.loads(GEOMETRY.read_text())["n41"]
    source = geometry["point_rows_by_unique_rotation"]
    setup_start = time.monotonic_ns()
    left = pair_buckets(E, F, source["20"])
    right = pair_buckets(E, F, source["30"])
    fleft = {s: product(Z + lift(F, x) for x in bucket)
             for s, bucket in left.items()}
    setup_ns = time.monotonic_ns() - setup_start
    if rss_bytes() > protocol["rss_cap_bytes"]:
        raise MemoryError("frozen setup RSS cap reached")
    signal.signal(signal.SIGALRM, alarm_handler)
    cases = []
    for kind in ("positive", "negative"):
        residual = protocol[kind + "_residual"]
        target_point = E(lift(F, residual[0]), lift(F, residual[1]))
        t = target_point[0]
        started = time.monotonic_ns()
        signal.alarm(protocol["residual_wall_cap_seconds"])
        status = "COMPLETE"
        failure = None
        norm_ns = gcd_ns = witness_ns = 0
        gcd_hits = gcd_degree_total = 0
        checked_pairs = 0
        first_witness = None
        completed_buckets = 0
        try:
            for right_sum in range(1, 64):
                begin = time.monotonic_ns()
                norm = product(((b+t)**2 * Z**2 + b*t*Z + b**2*t**2 + 1)
                               for b in (lift(F, x) for x in right[right_sum]))
                norm_ns += time.monotonic_ns() - begin
                for left_sum in range(1, 64):
                    begin = time.monotonic_ns()
                    common = fleft[left_sum].gcd(norm)
                    gcd_ns += time.monotonic_ns() - begin
                    checked_pairs += 1
                    if common.degree() > 0:
                        gcd_hits += 1
                        gcd_degree_total += common.degree()
                        if first_witness is None:
                            begin = time.monotonic_ns()
                            witness = witness_for_bucket_pair(
                                E, F, target_point, left[left_sum], right[right_sum],
                                norm, left[left_sum])
                            witness_ns += time.monotonic_ns() - begin
                            if witness is None:
                                raise AssertionError("positive S3 gcd has no group lift")
                            witness["left_seed_sum"] = left_sum
                            witness["right_seed_sum"] = right_sum
                            first_witness = witness
                completed_buckets += 1
                if rss_bytes() > protocol["rss_cap_bytes"]:
                    raise MemoryError("frozen residual RSS cap reached")
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
        finished = time.monotonic_ns()
        total_ns = finished - started
        cases.append({"kind": kind, "residual": residual, "status": status,
                      "failure": failure, "right_buckets_completed": completed_buckets,
                      "bucket_pairs_checked": checked_pairs,
                      "bucket_pairs_with_gcd": gcd_hits,
                      "gcd_degree_total": gcd_degree_total,
                      "first_group_witness": first_witness,
                      "norm_build_ns": norm_ns, "gcd_ns": gcd_ns,
                      "witness_ns": witness_ns,
                      "other_online_ns": total_ns-norm_ns-gcd_ns-witness_ns,
                      "online_wall_ns": total_ns,
                      "peak_rss_bytes": rss_bytes()})
    result = {"status": "COMPLETE_DIAGNOSTIC", "proposal_id": protocol["proposal_id"],
              "candidate_id": None, "target_count": 0,
              "source_sha256": sha(Path(__file__)),
              "protocol_sha256": sha(HERE / "protocol.json"),
              "setup_ns": setup_ns, "cases": cases,
              "peak_rss_bytes": rss_bytes()}
    with output.open("x") as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"status": result["status"],
                      "cases": [{"kind": x["kind"], "status": x["status"],
                                 "bucket_hits": x["bucket_pairs_with_gcd"],
                                 "online_s": round(x["online_wall_ns"]/1e9, 3)}
                                for x in cases]}))


if __name__ == "__main__":
    main()

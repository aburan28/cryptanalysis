#!/usr/bin/env python3
"""Target-conditioned S3 compatibility of two fixed-seed N41 pair images."""

import hashlib
import json
import resource
import sys
import time
from pathlib import Path

from sage.all import GF, PolynomialRing

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
GEOMETRY = BASE / "n41_two_free_pair_occupancy_20261009/geometry_snapshot.json"
PREDECESSOR = BASE / "n131_w14_s3_prefix_rank_20261010/result.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Field:
    def __init__(self):
        self.n = 41
        self.modulus = (1 << 41) | (1 << 3) | 1

    def mul(self, a, b):
        out = 0
        while b:
            if b & 1:
                out ^= a
            b >>= 1
            a <<= 1
            if a >> 41:
                a ^= self.modulus
        return out

    def inv(self, a):
        if not a:
            raise ZeroDivisionError
        r0, r1, v0, v1 = self.modulus, a, 0, 1
        while r1 != 1:
            delta = r0.bit_length() - r1.bit_length()
            if delta < 0:
                r0, r1, v0, v1 = r1, r0, v1, v0
                continue
            r0 ^= r1 << delta
            v0 ^= v1 << delta
            if r0.bit_length() < r1.bit_length():
                r0, r1, v0, v1 = r1, r0, v1, v0
        return v1 & ((1 << 41) - 1)


def add(f, p, q):
    if p is None:
        return q
    if q is None:
        return p
    x1, y1 = p
    x2, y2 = q
    if x1 == x2:
        if x1 == 0 or y2 == (y1 ^ x1):
            return None
        lam = x1 ^ f.mul(y1, f.inv(x1))
        x3 = f.mul(lam, lam) ^ lam
        y3 = f.mul(x1, x1) ^ f.mul(lam ^ 1, x3)
    else:
        lam = f.mul(y1 ^ y2, f.inv(x1 ^ x2))
        x3 = f.mul(lam, lam) ^ lam ^ x1 ^ x2
        y3 = f.mul(lam, x1 ^ x3) ^ x3 ^ y1
    return x3, y3


def encode(value):
    return sum(int(c) << i for i, c in enumerate(value.polynomial().list()))


def build_bucket(f, rows, seed):
    by_x = {}
    for i, left in enumerate(rows):
        for j in range(i + 1, len(rows)):
            right = rows[j]
            if left[2] == right[2] or left[3] ^ right[3] != seed:
                continue
            point = add(f, tuple(left[:2]), tuple(right[:2]))
            assert point is not None
            by_x.setdefault(point[0], []).append((point, i, j))
    assert by_x
    return by_x


def main():
    protocol_path = HERE / "protocol.json"
    protocol = json.loads(protocol_path.read_text())
    for name, path in (("run", Path(__file__)), ("geometry", GEOMETRY),
                       ("predecessor", PREDECESSOR),
                       ("runtime", HERE / "sage_runtime_info.json")):
        assert sha(path) == protocol["sha256"][name], name
    assert protocol["status"] == "FROZEN"
    assert not (HERE / "result.json").exists()
    started = time.monotonic_ns()
    geometry = json.loads(GEOMETRY.read_text())["n41"]
    predecessor = json.loads(PREDECESSOR.read_text())["n41"]
    assert list(predecessor["positive_residual"]) == protocol["residual"]
    assert geometry["public_target_q"] == protocol["public_target_q"]
    f = Field()
    ring2 = PolynomialRing(GF(2), "t")
    t0 = ring2.gen()
    field = GF(2**41, name="t", modulus=t0**41 + t0**3 + 1)

    def decode(value):
        return field(ring2([(value >> i) & 1 for i in range(41)]))

    xring = PolynomialRing(field, "X")
    x = xring.gen()
    yring = PolynomialRing(xring, "Y")
    y = yring.gen()
    target = decode(protocol["residual"][0])
    # The raw x-coordinate summation polynomial on y^2+xy=x^3+1.
    s3 = (x + target)**2 * y**2 + target * x * y + (target * x)**2 + 1
    cases = []
    for label, seeds in protocol["cases"].items():
        setup_start = time.monotonic_ns()
        left = build_bucket(f, geometry["point_rows_by_unique_rotation"]["20"], seeds[0])
        right = build_bucket(f, geometry["point_rows_by_unique_rotation"]["30"], seeds[1])
        left_poly = xring.prod(x + decode(key) for key in left)
        right_poly = yring.prod(y + decode(key) for key in right)
        setup_ns = time.monotonic_ns() - setup_start
        query_start = time.monotonic_ns()
        resultant = s3.resultant(right_poly)
        resultant_ns = time.monotonic_ns() - query_start
        gcd_start = time.monotonic_ns()
        common = left_poly.gcd(resultant)
        roots = sorted(encode(root) for root, multiplicity in common.roots()
                       if multiplicity >= 1)
        gcd_ns = time.monotonic_ns() - gcd_start
        replay_start = time.monotonic_ns()
        x_hits = []
        group_hits = []
        for a in roots:
            for b in right:
                if (field(decode(a) * decode(b) + target * (decode(a) + decode(b)))**2
                        + target * decode(a) * decode(b) + 1) != 0:
                    continue
                x_hits.append([a, b])
                for pa, ia, ja in left[a]:
                    for pb, ib, jb in right[b]:
                        if add(f, pa, pb) == tuple(protocol["residual"]):
                            group_hits.append({"x": [a, b], "indices": [ia, ja, ib, jb],
                                               "pair_points": [list(pa), list(pb)]})
        replay_ns = time.monotonic_ns() - replay_start
        assert bool(group_hits) == (label == "positive")
        assert len(x_hits) == protocol["expected_x_hits"][label]
        cases.append({"label": label, "seeds": seeds, "left_x_count": len(left),
                      "right_x_count": len(right), "left_polynomial_degree": left_poly.degree(),
                      "right_polynomial_degree": right_poly.degree(),
                      "resultant_degree": resultant.degree(), "gcd_degree": common.degree(),
                      "gcd_roots": roots, "x_hits": x_hits, "group_hits": group_hits,
                      "setup_ns": setup_ns, "target_resultant_ns": resultant_ns,
                      "target_gcd_ns": gcd_ns, "target_replay_ns": replay_ns})
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    peak = peak if sys.platform == "darwin" else peak * 1024
    result = {"status": "COMPLETE_BUCKET_DIAGNOSTIC", "proposal_id": protocol["proposal_id"],
              "candidate_id": None, "target_count": 1,
              "protocol_sha256": sha(protocol_path), "source_sha256": sha(Path(__file__)),
              "curve_id": geometry["curve_id"], "public_target_q": protocol["public_target_q"],
              "residual": protocol["residual"], "cases": cases,
              "elapsed_wall_ns": time.monotonic_ns() - started, "peak_rss_bytes": peak}
    assert result["elapsed_wall_ns"] < protocol["wall_cap_seconds"] * 10**9
    assert peak < protocol["rss_cap_bytes"]
    with (HERE / "result.json").open("x") as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"status": result["status"], "elapsed_wall_ns": result["elapsed_wall_ns"],
                      "peak_rss_bytes": peak, "cases": [{"label": c["label"],
                      "gcd_degree": c["gcd_degree"], "group_hits": len(c["group_hits"])}
                      for c in cases]}), flush=True)


if __name__ == "__main__":
    main()

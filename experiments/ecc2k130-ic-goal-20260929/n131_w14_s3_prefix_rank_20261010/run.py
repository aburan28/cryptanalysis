#!/usr/bin/env python3
"""Exact linear prefix-variation rank for a target-coupled S3 pair link."""

import hashlib
import json
import resource
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
GEOMETRY = BASE / "n41_two_free_pair_occupancy_20261009/geometry_snapshot.json"
W14 = BASE / "n131_w14_polynomial_pair_inverse_20261010/inputs.json"
PUBLIC = BASE / "n131_w14_samepair_target_gate_20261010/query_protocol.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Field:
    def __init__(self, n, terms):
        self.n = n
        self.mask = (1 << n) - 1
        self.modulus = (1 << n) | sum(1 << i for i in terms)

    def mul(self, a, b):
        out = 0
        while b:
            if b & 1:
                out ^= a
            b >>= 1
            a <<= 1
            if a >> self.n:
                a ^= self.modulus
        return out

    def inv(self, a):
        if a == 0:
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
        return v1 & self.mask


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
    return (x3, y3)


def neg(p):
    return None if p is None else (p[0], p[0] ^ p[1])


def s3(f, a, b, t):
    ab = f.mul(a, b)
    c = ab ^ f.mul(t, a ^ b)
    return f.mul(c, c) ^ f.mul(t, ab) ^ 1


def rank(columns):
    pivots = {}
    for original in columns:
        value = original
        while value:
            top = value.bit_length() - 1
            if top not in pivots:
                pivots[top] = value
                break
            value ^= pivots[top]
    return len(pivots)


def variation_columns(f, a, b, t, k):
    """Exact span of S3(A+u,B+v,t)-S3(A,B,t), u,v<2^k."""
    tb, ta = f.mul(t, b), f.mul(t, a)
    cols = []
    for i in range(k):
        e = 1 << i
        w = f.mul(b ^ t, e)
        cols.append(f.mul(w, w) ^ f.mul(tb, e))
    for i in range(k):
        e = 1 << i
        w = f.mul(a ^ t, e)
        cols.append(f.mul(w, w) ^ f.mul(ta, e))
    # uv ranges over the polynomial span 1,t,...,t^(2k-2).
    for h in range(2 * k - 1):
        e = 1 << h
        cols.append(f.mul(e, e) ^ f.mul(t, e))
    return cols


def pair_states(f, rows):
    result = []
    for i, left in enumerate(rows):
        for j in range(i + 1, len(rows)):
            right = rows[j]
            if left[2] == right[2]:
                continue
            point = add(f, tuple(left[:2]), tuple(right[:2]))
            if point is None:
                raise AssertionError("unexpected pair identity")
            result.append((point, i, j))
    assert len(result) == 1956
    return result


def prefix_census(xs, ks):
    out = {}
    for k in ks:
        bins = {}
        for x in xs:
            key = x >> k
            bins[key] = bins.get(key, 0) + 1
        out[str(k)] = {"occupied_prefixes": len(bins),
                       "non_singleton_prefixes": sum(v > 1 for v in bins.values()),
                       "outputs_in_non_singleton_prefixes": sum(v for v in bins.values() if v > 1),
                       "largest_prefix_family": max(bins.values())}
    return out


def main():
    result_path = HERE / "result.json"
    if result_path.exists():
        raise FileExistsError(result_path)
    protocol = json.loads((HERE / "protocol.json").read_text())
    for key, path in [("run", Path(__file__)), ("geometry", GEOMETRY),
                      ("w14_inputs", W14), ("public_protocol", PUBLIC)]:
        if sha(path) != protocol["sha256"][key]:
            raise ValueError("frozen digest mismatch: " + key)
    started = time.monotonic_ns()
    geometry = json.loads(GEOMETRY.read_text())["n41"]
    assert geometry["public_target_q"] == protocol["n41_public_target"]
    f41 = Field(41, [0, 3])
    domains = [pair_states(f41, geometry["point_rows_by_unique_rotation"][str(r)])
               for r in [20, 30]]
    xs = [sorted({state[0][0] for state in domain}) for domain in domains]
    assert [len(x) for x in xs] == [978, 978]
    residual = tuple(protocol["n41_positive_residual"])
    table = {state[0]: state for state in domains[0]}
    witness = None
    for state in domains[1]:
        first = table.get(add(f41, residual, neg(state[0])))
        if first is not None:
            witness = [first, state]
            break
    if witness is None:
        raise AssertionError("positive residual has no pair completion")
    a41, b41 = [state[0][0] for state in witness]
    assert s3(f41, a41, b41, residual[0]) == 0
    n41_cases = [(a41, b41, residual[0])]
    n41_cases += [(xs[0][i], xs[1][i], residual[0]) for i in range(32)]
    ks41 = protocol["n41_low_bits"]
    rank41 = [{"a": a, "b": b, "t": t,
               "s3_value": s3(f41, a, b, t),
               "ranks": {str(k): rank(variation_columns(f41, a, b, t, k))
                         for k in ks41}} for a, b, t in n41_cases]

    f131 = Field(131, [0, 1, 2, 13])
    positives = json.loads(W14.read_text())["positives"]
    t131 = json.loads(PUBLIC.read_text())["public_target_q_polynomial"][0]
    n131_cases = [(positives[i]["raw_sum"][0], positives[i + 1]["raw_sum"][0], t131)
                  for i in range(0, 32, 2)]
    ks131 = protocol["n131_low_bits"]
    rank131 = [{"a": a, "b": b, "t": t,
                "s3_value": s3(f131, a, b, t),
                "ranks": {str(k): rank(variation_columns(f131, a, b, t, k))
                          for k in ks131}} for a, b, t in n131_cases]
    result = {
        "status": "COMPLETE_DIAGNOSTIC", "proposal_id": protocol["proposal_id"],
        "candidate_id": None, "run_id": None, "target_count": 0,
        "protocol_sha256": sha(HERE / "protocol.json"),
        "source_sha256": sha(Path(__file__)),
        "n41": {"curve_id": geometry["curve_id"], "pair_output_x_counts": [len(x) for x in xs],
                "prefix_census": [prefix_census(x, ks41) for x in xs],
                "positive_residual": list(residual),
                "positive_witness": [{"pair_sum": list(state[0]),
                                      "source_indices": [state[1], state[2]]}
                                     for state in witness],
                "cases": rank41},
        "n131": {"curve_id": protocol["n131_curve_id"],
                 "official_target_x": t131, "cases": rank131},
        "elapsed_wall_ns": time.monotonic_ns() - started,
        "peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss *
                          (1 if sys.platform == "darwin" else 1024),
    }
    if result["elapsed_wall_ns"] > protocol["wall_cap_seconds"] * 10**9:
        raise TimeoutError("cap reached")
    if result["peak_rss_bytes"] > protocol["rss_cap_bytes"]:
        raise MemoryError("cap reached")
    with result_path.open("x") as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"status": result["status"], "elapsed_wall_ns": result["elapsed_wall_ns"],
                      "n41_witness": result["n41"]["positive_witness"],
                      "n131_rank_34": [case["ranks"]["34"] for case in rank131]}))


if __name__ == "__main__":
    main()

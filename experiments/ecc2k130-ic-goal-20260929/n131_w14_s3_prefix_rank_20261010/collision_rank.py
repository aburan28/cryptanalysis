#!/usr/bin/env python3
"""Exhaustive first-collision prefix rank on both N41 pair-output domains."""

import hashlib
import json
import resource
import sys
import time
from pathlib import Path

import run

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def field_monomial(f, degree):
    value = 1 << degree
    while value.bit_length() > f.n:
        value ^= f.modulus << (value.bit_length() - f.n - 1)
    return value


def one_side_columns(f, prefix, target, k):
    tp = f.mul(target, prefix)
    values = []
    for i in range(k):
        e = 1 << i
        w = f.mul(prefix ^ target, e)
        values.append(f.mul(w, w) ^ f.mul(tp, e))
    return values


def main():
    out = HERE / "collision_rank_result.json"
    if out.exists():
        raise FileExistsError(out)
    protocol = json.loads((HERE / "collision_rank_protocol.json").read_text())
    for key, path in [("source", Path(__file__)), ("run", HERE / "run.py"),
                      ("geometry", run.GEOMETRY), ("base_result", HERE / "result.json"),
                      ("followup_result", HERE / "followup_result.json")]:
        if protocol["sha256"][key] != sha(path):
            raise ValueError("frozen digest mismatch: " + key)
    started = time.monotonic_ns()
    k = protocol["free_low_bits"]
    f = run.Field(41, [0, 3])
    target = protocol["residual_x"]
    cross = []
    for h in range(2*k - 1):
        e = field_monomial(f, h)
        cross.append(f.mul(e, e) ^ f.mul(target, e))
    cross_rank = run.rank(cross)
    assert cross_rank == 40
    geometry = json.loads(run.GEOMETRY.read_text())["n41"]
    domains = []
    for rotation in [20, 30]:
        states = run.pair_states(f, geometry["point_rows_by_unique_rotation"][str(rotation)])
        xs = {state[0][0] for state in states}
        prefixes = sorted({x & ~((1 << k) - 1) for x in xs})
        counts = {}
        for x in xs:
            p = x & ~((1 << k) - 1)
            counts[p] = counts.get(p, 0) + 1
        assert len(prefixes) == 977 and sorted(counts.values()).count(2) == 1
        rank_counts = {}
        bad = []
        for prefix in prefixes:
            dimension = run.rank(cross + one_side_columns(f, prefix, target, k))
            rank_counts[str(dimension)] = rank_counts.get(str(dimension), 0) + 1
            if dimension < 41:
                bad.append(prefix)
        domains.append({"rotation": rotation, "occupied_prefixes": len(prefixes),
                        "first_collision_prefix": next(p for p, count in counts.items() if count == 2),
                        "one_side_plus_cross_rank_counts": rank_counts,
                        "prefixes_below_full_rank": bad})
    elapsed = time.monotonic_ns() - started
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * (
        1 if sys.platform == "darwin" else 1024)
    if elapsed > protocol["wall_cap_seconds"] * 10**9 or peak > protocol["rss_cap_bytes"]:
        raise RuntimeError("resource cap reached")
    result = {"status": "COMPLETE_EXHAUSTIVE_PREFIX_SCAN", "candidate_id": None,
              "target_count": 0, "source_sha256": sha(Path(__file__)),
              "protocol_sha256": sha(HERE / "collision_rank_protocol.json"),
              "cross_term_rank": cross_rank, "free_low_bits": k,
              "both_domain_prefix_rectangles": domains[0]["occupied_prefixes"] * domains[1]["occupied_prefixes"],
              "domains": domains, "elapsed_wall_ns": elapsed, "peak_rss_bytes": peak}
    with out.open("x") as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"status": result["status"],
                      "rank_counts": [x["one_side_plus_cross_rank_counts"] for x in domains],
                      "elapsed_wall_ns": elapsed}))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Independent checked-Sage rank witness and deficit audit."""

import hashlib
import json
import resource
import sys
import time
from collections import Counter
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing

HERE = Path(__file__).resolve().parent
GOAL = HERE.parent
CENSUS = GOAL / "n41_two_free_pair_occupancy_20261009"
SIGN = GOAL / "n41_two_pair_sign_orbit_x_support_20261009"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def add_pivot(pivots, row):
    while row:
        bit = row.bit_length() - 1
        if bit not in pivots:
            pivots[bit] = row
            return True
        row ^= pivots[bit]
    return False


def main():
    if (HERE / "audit.json").exists():
        raise FileExistsError("preserve first independent Sage audit")
    start = time.monotonic_ns()
    protocol = json.loads((HERE / "protocol.json").read_text())
    result = json.loads((HERE / "result.json").read_text())
    files = {
        "geometry": CENSUS / "geometry_snapshot.json",
        "arithmetic": CENSUS / "arithmetic_snapshot.py",
        "census_result": CENSUS / "result.json",
        "census_sage_audit": CENSUS / "audit.json",
        "sign_source": SIGN / "run.py",
        "sign_protocol": SIGN / "protocol.json",
        "sign_result": SIGN / "result.json",
        "sign_sage_audit": SIGN / "audit.json",
        "producer": HERE / "run.py",
        "auditor": HERE / "audit.py",
    }
    if {key: sha(path) for key, path in files.items()} != protocol["source_sha256"]:
        raise ValueError("frozen source or input hash differs")
    if (result["status"] != "COMPLETE_ALL_SEED_BINS" or
            result["protocol_sha256"] != sha(HERE / "protocol.json") or
            result["peak_rss_bytes"] > protocol["rss_cap_bytes"] or
            result["producer_wall_ns"] > protocol["producer_wall_cap_seconds"] * 10**9):
        raise ValueError("producer identity or resource gate failed")
    sign_result = json.loads(files["sign_result"].read_text())
    sign_audit = json.loads(files["sign_sage_audit"].read_text())
    if (sign_result["status"] != "PASS_EXACT_SIGN_ORBITS_AND_X_FIBERS" or
            sign_audit["status"] != "PASS_INDEPENDENT_SAGE_SIGN_AND_X_FIBER_AUDIT" or
            sign_result["free_sign_orbits"] != protocol["expected_sign_orbits"]):
        raise ValueError("prior sign-orbit evidence differs")
    geometry = json.loads(files["geometry"].read_text())["n41"]
    if geometry["curve_id"] != protocol["curve_id"] or geometry["public_target_q"] != protocol["public_target_q"]:
        raise ValueError("N41 curve or public point differs")
    ring = PolynomialRing(GF(2), "t")
    t = ring.gen()
    field = GF(2**41, "t", modulus=t**41 + t**3 + 1)
    curve = EllipticCurve(field, [1, 0, 0, 0, 1])

    def decode(value):
        return field(ring([(value >> bit) & 1 for bit in range(41)]))

    def x_int(value):
        return sum(int(bit) << index for index, bit in enumerate(value.polynomial().list()))

    domains, signs = [], []
    for rotation in protocol["suffix_pair_rotations"]:
        source = geometry["point_rows_by_unique_rotation"][str(rotation)]
        points = [curve(decode(row[0]), decode(row[1])) for row in source]
        if len(points) != 64 or any(int(geometry["subgroup_order"]) * p != curve(0) for p in points):
            raise ValueError("source points or subgroup changed")
        point_index = {point: i for i, point in enumerate(points)}
        neg_point = []
        for i, point in enumerate(points):
            j = point_index.get(-point)
            if j is None or j == i or source[i][2:4] != source[j][2:4]:
                raise ValueError("point sign map differs")
            neg_point.append(j)
        pairs, pair_index = [], {}
        for i in range(64):
            for j in range(i + 1, 64):
                if source[i][2] == source[j][2]:
                    continue
                pair_index[(i, j)] = len(pairs)
                pairs.append((points[i] + points[j],
                              (1 << source[i][2]) | (1 << source[j][2]),
                              source[i][3] ^ source[j][3]))
        if len(pairs) != 1956:
            raise ValueError("Sage pair-domain size differs")
        neg_pair = []
        for i in range(64):
            for j in range(i + 1, 64):
                if source[i][2] == source[j][2]:
                    continue
                p = pair_index[(i, j)]
                a, b = sorted((neg_point[i], neg_point[j]))
                q = pair_index[(a, b)]
                if pairs[q][0] != -pairs[p][0] or pairs[q][1:] != pairs[p][1:]:
                    raise ValueError("Sage pair sign map differs")
                neg_pair.append(q)
        domains.append(pairs)
        signs.append(neg_pair)
    left, right = domains
    counts = Counter()
    total_orbits = 0
    for i, p in enumerate(left):
        for j, q in enumerate(right):
            if p[1] & q[1] or i * 1956 + j >= signs[0][i] * 1956 + signs[1][j]:
                continue
            counts["%d,%d" % (p[2], q[2])] += 1
            total_orbits += 1
    if (total_orbits != protocol["expected_sign_orbits"] or
            len(counts) != protocol["expected_seed_sum_pair_bins"] or
            set(counts) != set(result["bin_records"])):
        raise ValueError("Sage sign-orbit bin partition differs")
    witness_count = 0
    deficient = 0
    for key, cell in result["bin_records"].items():
        if cell["orbits"] != counts[key]:
            raise ValueError("Sage seed-bin orbit count differs")
        s2, s3 = map(int, key.split(","))
        pivots = {}
        for i, j, claimed_x in cell["witnesses"]:
            p, q = left[i], right[j]
            if (p[1] & q[1] or p[2] != s2 or q[2] != s3 or
                    i * 1956 + j >= signs[0][i] * 1956 + signs[1][j]):
                raise ValueError("rank witness outside exact canonical bin")
            total = p[0] + q[0]
            if total == curve(0):
                raise ValueError("rank witness sums to identity")
            x = x_int(total[0])
            if x != claimed_x or x & 1 or not add_pivot(pivots, 1 | ((x >> 1) << 1)):
                raise ValueError("Sage group output or witness independence differs")
            witness_count += 1
        if len(pivots) != cell["rank"] or len(cell["affine_equations"]) != 41 - cell["rank"]:
            raise ValueError("reported affine rank or equation count differs")
        if cell["rank"] < 41:
            deficient += 1
            exact = {}
            seen = 0
            for i, p in enumerate(left):
                if p[2] != s2:
                    continue
                for j, q in enumerate(right):
                    if (q[2] != s3 or p[1] & q[1] or
                            i * 1956 + j >= signs[0][i] * 1956 + signs[1][j]):
                        continue
                    total = p[0] + q[0]
                    x = x_int(total[0])
                    row = 1 | ((x >> 1) << 1)
                    if x & 1 or any((equation & row).bit_count() & 1
                                    for equation in cell["affine_equations"]):
                        raise ValueError("claimed affine filter rejects a valid completion")
                    add_pivot(exact, row)
                    seen += 1
            if seen != cell["orbits"] or len(exact) != cell["rank"]:
                raise ValueError("deficient bin does not have the reported exact rank")
        if time.monotonic_ns() - start > protocol["audit_wall_cap_seconds"] * 10**9:
            raise TimeoutError("frozen Sage audit wall cap")
    ranks = [cell["rank"] for cell in result["bin_records"].values()]
    if (result["min_affine_rank"] != min(ranks) or
            result["max_affine_rank"] != max(ranks) or
            result["deficient_bins"] != deficient or
            result["seed_sum_pair_bins"] != len(counts) or
            result["sign_orbits_scanned"] != total_orbits):
        raise ValueError("rank aggregate differs")
    elapsed = time.monotonic_ns() - start
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if sys.platform != "darwin":
        peak *= 1024
    if elapsed > protocol["audit_wall_cap_seconds"] * 10**9 or peak > protocol["rss_cap_bytes"]:
        raise ValueError("independent Sage audit resource cap")
    receipt = {
        "status": "PASS_INDEPENDENT_SAGE_AFFINE_BIN_RANK_AUDIT",
        "curve_id": protocol["curve_id"],
        "seed_sum_pair_bins": len(counts),
        "sign_orbits_recounted": total_orbits,
        "independent_group_rank_witnesses": witness_count,
        "deficient_bins": deficient,
        "minimum_rank": min(ranks), "maximum_rank": max(ranks),
        "audit_wall_ns": elapsed, "peak_rss_bytes": peak,
        "protocol_sha256": sha(HERE / "protocol.json"),
        "result_sha256": sha(HERE / "result.json"),
        "runtime_sha256": sha(HERE / "sage_runtime_info.json"),
    }
    with (HERE / "audit.json").open("x") as out:
        json.dump(receipt, out, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps({key: receipt[key] for key in
                      ("status", "seed_sum_pair_bins", "independent_group_rank_witnesses",
                       "deficient_bins", "audit_wall_ns")}, sort_keys=True))


if __name__ == "__main__":
    main()

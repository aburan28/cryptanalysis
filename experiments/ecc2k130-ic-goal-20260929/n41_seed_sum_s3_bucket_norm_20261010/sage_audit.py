#!/usr/bin/env python3
"""Independent Sage replay of seed-sum bucket traces and selected product ranks."""

import hashlib
import json
from pathlib import Path

from sage.all import GF, PolynomialRing, EllipticCurve, matrix

HERE = Path(__file__).resolve().parent
BASE = HERE.parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def lift(F, value):
    out = F.zero()
    t = F.gen()
    while value:
        bit = value.bit_length()-1
        out += t**bit
        value ^= 1 << bit
    return out


def encode(value):
    return sum(int(c) << i for i, c in enumerate(value.polynomial()))


def rank(values):
    rows = []
    for value in values:
        coeffs = list(value.polynomial())
        rows.append([int(coeffs[i]) if i < len(coeffs) else 0 for i in range(41)])
    return matrix(GF(2), rows).rank()


def main():
    output = HERE / "sage_audit.json"
    if output.exists():
        raise FileExistsError(output)
    protocol_path = HERE / "sage_audit_protocol.json"
    protocol = json.loads(protocol_path.read_text())
    geometry_path = BASE / "n41_two_free_pair_occupancy_20261009/geometry_snapshot.json"
    paths = {"source": Path(__file__), "geometry": geometry_path,
             "affine_result": HERE / "affine_rank_result.json",
             "exact_result": HERE / "result.json",
             "batch_result": HERE / "batch_result.json",
             "runtime": HERE / "sage_runtime_info.json"}
    for key, path in paths.items():
        if protocol["sha256"][key] != sha(path):
            raise ValueError("frozen digest mismatch: " + key)
    P = PolynomialRing(GF(2), "t")
    t0 = P.gen()
    F = GF(2**41, "t", modulus=t0**41 + t0**3 + 1)
    E = EllipticCurve(F, [1, 0, 0, 0, 1])
    geometry = json.loads(geometry_path.read_text())["n41"]
    groups = []
    counts = []
    for rotation in [20, 30]:
        rows = geometry["point_rows_by_unique_rotation"][str(rotation)]
        points = [E(lift(F, row[0]), lift(F, row[1])) for row in rows]
        buckets = {s: set() for s in range(1, 64)}
        for i, left in enumerate(rows):
            for j in range(i + 1, len(rows)):
                if left[2] == rows[j][2]:
                    continue
                total = points[i] + points[j]
                buckets[left[3] ^ rows[j][3]].add(encode(total[0]))
        union = set.union(*buckets.values())
        assert len(union) == 978
        assert all(len(buckets[s]) >= 10 for s in buckets)
        assert all(lift(F, x).trace() == 0 for x in union)
        groups.append(buckets)
        counts.append({"rotation": rotation, "seed_sum_buckets": len(buckets),
                       "pair_output_x_count": len(union),
                       "trace_zero_x_count": len(union)})
    target = lift(F, protocol["positive_residual"][0])
    assert target.trace() == 0
    ranks = []
    for s, t in protocol["sampled_bucket_pairs"]:
        A = sorted(groups[0][s])
        B = sorted(groups[1][t])
        U = [lift(F, x ^ A[0]) for x in A[1:]]
        V = [lift(F, x ^ B[0]) for x in B[1:]]
        dimension = rank([u*v for u in U for v in V])
        assert dimension == 41
        ranks.append({"left_seed_sum": s, "right_seed_sum": t,
                      "left_x_count": len(A), "right_x_count": len(B),
                      "cross_product_rank": dimension})
    witness = json.loads((HERE / "batch_result.json").read_text())["cases"][0]["first_group_witness"]
    pair_points = []
    for rotation, key in [(20, "left"), (30, "right")]:
        rows = geometry["point_rows_by_unique_rotation"][str(rotation)]
        i, j = witness[key + "_source_indices"]
        point = E(lift(F, rows[i][0]), lift(F, rows[i][1])) + E(lift(F, rows[j][0]), lift(F, rows[j][1]))
        assert [encode(point[0]), encode(point[1])] == witness[key + "_pair_point"]
        pair_points.append(point)
    summed = pair_points[0] + pair_points[1]
    assert [encode(summed[0]), encode(summed[1])] == protocol["positive_residual"]
    result = {"status": "PASS", "source_sha256": sha(Path(__file__)),
              "protocol_sha256": sha(protocol_path), "domain_checks": counts,
              "sampled_bucket_product_ranks": ranks,
              "independent_group_witness": True}
    with output.open("x") as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"status": result["status"], "domain_checks": counts,
                      "sampled_ranks": [x["cross_product_rank"] for x in ranks]}))


if __name__ == "__main__":
    main()

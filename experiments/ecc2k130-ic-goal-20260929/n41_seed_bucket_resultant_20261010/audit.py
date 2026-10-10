#!/usr/bin/env python3
"""Independent Sage point replay of the fixed-seed S3 bucket decisions."""

import hashlib
import json
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
GEOMETRY = BASE / "n41_two_free_pair_occupancy_20261009/geometry_snapshot.json"
ROW = BASE / "n41_two_free_pair_compact_lookup_20261009/public_search_v2.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    protocol_path = HERE / "audit_protocol.json"
    protocol = json.loads(protocol_path.read_text())
    for name, path in (("source", Path(__file__)), ("geometry", GEOMETRY),
                       ("row", ROW), ("generic", HERE / "result.json"),
                       ("norm", HERE / "norm_result.json"),
                       ("runtime", HERE / "sage_runtime_info.json")):
        assert sha(path) == protocol["sha256"][name], name
    assert not (HERE / "audit.json").exists()
    geometry = json.loads(GEOMETRY.read_text())["n41"]
    generic = json.loads((HERE / "result.json").read_text())
    norm = json.loads((HERE / "norm_result.json").read_text())
    row = json.loads(ROW.read_text())["row"]
    binary = PolynomialRing(GF(2), "t")
    t = binary.gen()
    field = GF(2**41, name="t", modulus=t**41 + t**3 + 1)
    curve = EllipticCurve(field, [1, 0, 0, 0, 1])

    def decode(value):
        return field(binary([(value >> i) & 1 for i in range(41)]))

    def encode(value):
        return int(sum(int(c) << i for i, c in enumerate(value.polynomial().list())))

    def point(coords):
        return curve(decode(coords[0]), decode(coords[1]))

    prefix = sum((point(leaf["point"]) for leaf in row[:4]), curve(0))
    target = point(protocol["public_target_q"])
    residual = point(protocol["residual"])
    assert target - prefix == residual
    cases = []
    for label, seeds in protocol["cases"].items():
        domains = []
        for rotation, seed in zip((20, 30), seeds):
            rows = geometry["point_rows_by_unique_rotation"][str(rotation)]
            by_x = {}
            for i, left in enumerate(rows):
                for j in range(i + 1, len(rows)):
                    right = rows[j]
                    if left[2] == right[2] or left[3] ^ right[3] != seed:
                        continue
                    pair_sum = point(left[:2]) + point(right[:2])
                    assert pair_sum != curve(0)
                    by_x.setdefault(encode(pair_sum[0]), []).append((pair_sum, i, j))
            domains.append(by_x)
        direct_x_hits = []
        direct_group_hits = []
        tx = residual[0]
        for a in domains[0]:
            ax = decode(a)
            for b in domains[1]:
                bx = decode(b)
                s3 = (ax * bx + tx * (ax + bx))**2 + tx * ax * bx + 1
                if s3 != 0:
                    continue
                direct_x_hits.append([a, b])
                for pa, ia, ja in domains[0][a]:
                    for pb, ib, jb in domains[1][b]:
                        if pa + pb == residual:
                            direct_group_hits.append([ia, ja, ib, jb])
        old = next(c for c in generic["cases"] if c["label"] == label)
        new = next(c for c in norm["cases"] if c["label"] == label)
        assert sorted(direct_x_hits) == sorted(old["x_hits"])
        assert sorted(set(pair[0] for pair in direct_x_hits)) == new["gcd_roots"]
        assert sorted(direct_group_hits) == sorted(hit["indices"] for hit in old["group_hits"])
        assert len(domains[0]) == old["left_x_count"] == new["left_degree"]
        assert len(domains[1]) == old["right_x_count"] == new["right_degree"]
        if label == "positive":
            assert len(direct_group_hits) == 1
            indices = direct_group_hits[0]
            leaves = ([geometry["point_rows_by_unique_rotation"]["20"][i]
                       for i in indices[:2]] +
                      [geometry["point_rows_by_unique_rotation"]["30"][i]
                       for i in indices[2:]])
            columns = [leaf["column"] for leaf in row[:4]] + [leaf[2] for leaf in leaves]
            assert len(set(columns)) == 8
            assert prefix + sum((point(leaf[:2]) for leaf in leaves), curve(0)) == target
        cases.append({"label": label, "seed_sums": seeds,
                      "pair_output_x_counts": [len(domain) for domain in domains],
                      "direct_x_hits": direct_x_hits,
                      "direct_group_hit_count": len(direct_group_hits)})
    out = {"status": "PASS", "source_sha256": sha(Path(__file__)),
           "audit_protocol_sha256": sha(protocol_path), "generic_result_sha256": sha(HERE / "result.json"),
           "norm_result_sha256": sha(HERE / "norm_result.json"),
           "public_target_q": protocol["public_target_q"], "residual": protocol["residual"],
           "prefix_replay": "PASS", "eight_column_public_row_replay": "PASS",
           "cases": cases}
    with (HERE / "audit.json").open("x") as stream:
        json.dump(out, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"status": "PASS", "cases": cases}), flush=True)


if __name__ == "__main__":
    main()

#!/usr/bin/env sage -python
"""Independent group replay and folded-column relation row for the MITM hit."""

import hashlib
import json
import sys
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing, Zmod

HERE = Path(__file__).resolve().parent
BASE = HERE.parent / "n41_w7_entropy_cubic_20261011/w8"
R = 549756390943
ROTATIONS = (0, 7, 14, 21, 28, 35)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    protocol = json.loads((HERE / "protocol.json").read_text())
    query = json.loads((HERE / "query_result.json").read_text())
    geometry = json.loads((BASE / "geometry.json").read_text())
    fixture = json.loads((BASE / "fixture.json").read_text())
    assert protocol["source_sha256"]["geometry"] == sha(BASE / "geometry.json")
    assert protocol["source_sha256"]["fixture"] == sha(BASE / "fixture.json")
    assert protocol["source_sha256"]["input"] == sha(HERE / "join_input.tsv")
    assert query["protocol_sha256"] == sha(HERE / "protocol.json")
    assert query["stdout_sha256"] == sha(HERE / "join.stdout.txt")
    assert query["stderr_sha256"] == sha(HERE / "join.stderr.txt")
    assert query["status"] == "HIT_PENDING_SAGE_REPLAY"
    assert json.loads((HERE / "sage_runtime_info.json").read_text())["status"] == "verified"
    lines = (HERE / "join.stdout.txt").read_text().splitlines()
    assert lines[0].startswith("CHECK_PASS 128 ")
    hits = [line for line in lines if line.startswith("HIT ")]
    assert len(hits) == 1 and hits == query["hit_lines"]
    tokens = hits[0].split()
    target_index = int(tokens[1])
    state_ids = list(map(int, tokens[2:8]))
    assert target_index == 0 and len(state_ids) == 6
    rows = {int(row["mask"]): row for row in geometry["rows"]}
    edges = [(a, a ^ 184) for a in sorted(rows)
             if a < (a ^ 184) and a ^ 184 in rows
             and rows[a]["column"] != rows[a ^ 184]["column"]]
    assert len(edges) == 35
    ring = PolynomialRing(GF(2), "t")
    t = ring.gen()
    field = GF(2**41, name="t", modulus=t**41+t**3+1)
    curve = EllipticCurve(field, [1, 0, 0, 0, 1])

    def dec(value):
        return field(ring([(int(value) >> i) & 1 for i in range(41)]))

    def enc(value):
        return sum(int(bit) << i for i, bit in enumerate(value.polynomial().list()))

    def xy(point):
        return [enc(point[0]), enc(point[1])]

    def frobenius(point, exponent):
        return curve(point[0]**(1 << exponent), point[1]**(1 << exponent))

    raw = {mask: curve(*map(dec, row["raw_point"])) for mask, row in rows.items()}
    projected = {mask: 4 * point for mask, point in raw.items()}
    assert all(point != curve(0) and R * point == curve(0)
               for point in projected.values())
    representatives = {}
    for mask, row in sorted(rows.items()):
        representatives.setdefault(int(row["column"]), mask)
    quotient = {}
    for mask in {m for sid in state_ids for m in edges[sid // 4]}:
        col = rows[mask]["column"]
        rep = projected[representatives[col]]
        images = [(frobenius(rep, exponent), exponent, 1) for exponent in range(41)]
        images += [(-point, exponent, -1) for point, exponent, _ in images]
        matches = [(exponent, sign) for point, exponent, sign in images
                   if point == projected[mask]]
        assert len(matches) == 1
        quotient[mask] = matches[0]

    # For the a=0 Koblitz model, tau^2 + tau + 2 acts as zero on this subgroup.
    ring_r = PolynomialRing(Zmod(R), "L")
    L = ring_r.gen()
    roots = [int(root) for root, _ in (L**2 + L + 2).roots()]
    assert len(roots) == 2
    sample = projected[representatives[min(representatives)]]
    eigenvalues = [value for value in roots if value * sample == frobenius(sample, 1)]
    assert len(eigenvalues) == 1
    eigenvalue = eigenvalues[0]

    occupied_edges, occupied_columns = set(), set()
    running = curve(0)
    terms = []
    source_points = []
    for slot, sid in enumerate(state_ids):
        edge_id, choice = divmod(sid, 4)
        a, b = edges[edge_id]
        assert edge_id not in occupied_edges
        occupied_edges.add(edge_id)
        sign_a, sign_b = divmod(choice, 2)
        first = -raw[a] if sign_a else raw[a]
        second = -raw[b] if sign_b else raw[b]
        pair = first + second
        rotated = frobenius(pair, ROTATIONS[slot])
        running += rotated
        source_points.append({"slot": slot, "edge_id": edge_id,
                              "masks": [a, b], "source_sign_bits": [sign_a, sign_b],
                              "rotation": ROTATIONS[slot], "pair_rotated": xy(rotated)})
        for mask, sign_bit in ((a, sign_a), (b, sign_b)):
            column = int(rows[mask]["column"])
            assert column not in occupied_columns
            occupied_columns.add(column)
            exponent, orbit_sign = quotient[mask]
            coefficient = ((-1 if sign_bit else 1) * orbit_sign *
                           pow(eigenvalue, ROTATIONS[slot] + exponent, R)) % R
            terms.append({"slot": slot, "mask": mask,
                          "column": column, "representative_mask": representatives[column],
                          "orbit_exponent": exponent, "orbit_sign": orbit_sign,
                          "source_sign_bit": sign_bit,
                          "coefficient_mod_r": str(coefficient)})
    expected_raw = fixture["raw_target_preimages"][target_index]
    assert xy(running) == expected_raw
    assert xy(4 * running) == fixture["public_target_transported"]
    row_sum = curve(0)
    for term in terms:
        row_sum += int(term["coefficient_mod_r"]) * projected[term["representative_mask"]]
    assert row_sum == 4 * running
    assert len(terms) == len(occupied_columns) == 12
    assert all(int(term["coefficient_mod_r"]) != 0 for term in terms)
    result = {"status": "PASS_INDEPENDENT_N41_PUBLIC_SIX_PAIR_RELATION",
              "candidate_id": None, "target_count": 1,
              "curve_id": protocol["curve_id"], "public_target_transported":
                  fixture["public_target_transported"],
              "raw_target_preimage_index": target_index,
              "raw_target_replayed": expected_raw,
              "frobenius_eigenvalue_mod_r": str(eigenvalue),
              "source_edges_distinct": len(occupied_edges),
              "folded_columns_distinct": len(occupied_columns),
              "relation_row": terms, "source_pairs": source_points,
              "row_rank_from_empty_matrix": 1,
              "source_sha256": {"script": sha(Path(__file__)),
                                "protocol": sha(HERE / "protocol.json"),
                                "query": sha(HERE / "query_result.json"),
                                "geometry": sha(BASE / "geometry.json"),
                                "fixture": sha(BASE / "fixture.json"),
                                "join_stdout": sha(HERE / "join.stdout.txt"),
                                "sage_runtime": sha(HERE / "sage_runtime_info.json")}}
    with (HERE / "audit_result.json").open("x") as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(result["status"], len(terms), eigenvalue)


if __name__ == "__main__":
    main()

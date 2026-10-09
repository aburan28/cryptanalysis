#!/usr/bin/env python3
"""Independent Sage group replay and transposed-rank audit of the corrected gate."""

from __future__ import annotations

import hashlib
import itertools
import json
import resource
import sys
import time
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing

HERE = Path(__file__).resolve().parent
PROTOCOL = HERE / "audit_protocol_v2.json"
OUTPUT = HERE / "sage_audit_v2.json"


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def insert_low(basis: dict[int, int], value: int) -> bool:
    while value:
        bit = value & -value
        pivot = bit.bit_length() - 1
        prior = basis.get(pivot)
        if prior is None:
            basis[pivot] = value
            return True
        value ^= prior
    return False


def main() -> None:
    if OUTPUT.exists():
        raise FileExistsError("preserve first independent corrected audit")
    freeze = json.loads(PROTOCOL.read_text())
    inputs = {name: Path(path) for name, path in freeze["inputs"].items()}
    if sha(Path(__file__)) != freeze["audit_source_sha256"]:
        raise ValueError("independent audit source changed after freeze")
    for name, path in inputs.items():
        if sha(path) != freeze["input_sha256"][name]:
            raise ValueError(f"frozen audit input changed: {name}")
    protocol = json.loads(inputs["protocol_v2"].read_text())
    result = json.loads(inputs["result_v2"].read_text())
    runtime = json.loads(inputs["runtime"].read_text())
    if (runtime.get("status") != "verified" or
            result["status"] != "FULL_DISTINCT_COLUMN_MIXED_CUBIC_RANK" or
            result["rank"] != 13599 or result["coordinate_rank"] != 821 or
            result["counts"]["source_rows_accepted"] != 13646 or
            result["counts"]["extra_rows_accepted"] != 0 or
            protocol["curve_id"] != result["curve_id"] or
            result["source_sha256"]["protocol"] != sha(inputs["protocol_v2"])):
        raise ValueError("corrected producer result or checked Sage runtime changed")
    decoded = json.loads(inputs["decoded_rows"].read_text())
    holdout = json.loads(inputs["holdout_rows"].read_text())
    geometry = json.loads(inputs["geometry"].read_text())["n41"]
    if not (decoded["curve_id"] == holdout["curve_id"] ==
            geometry["curve_id"] == protocol["curve_id"]):
        raise ValueError("curve ID changed")

    start = time.monotonic_ns()
    poly = PolynomialRing(GF(2), "t")
    t = poly.gen()
    field = GF(2**41, "t", modulus=t**41 + t**3 + 1)
    curve = EllipticCurve(field, [1, 0, 0, 0, 1])
    zero = curve(0)

    def decode(value: int):
        return field(poly([(int(value) >> bit) & 1 for bit in range(41)]))

    def point(raw):
        return curve(decode(raw[0]), decode(raw[1]))

    def encode(value):
        return [sum(int(bit) << i for i, bit in enumerate(value[0].polynomial().list())),
                sum(int(bit) << i for i, bit in enumerate(value[1].polynomial().list()))]

    domain_rows = [geometry["point_rows_by_unique_rotation"][str(r)]
                   for r in protocol["pair_rotations"]]
    source_points = [[point(raw) for raw in rows] for rows in domain_rows]
    r = 549756390943
    if any(r * p != zero for rows in source_points for p in rows):
        raise ValueError("source point outside declared prime subgroup")
    target = point(protocol["public_target_q"])
    if r * target != zero:
        raise ValueError("public target outside declared prime subgroup")
    domains = []
    for rows, points in zip(domain_rows, source_points):
        states = []
        for i in range(64):
            for j in range(i + 1, 64):
                if rows[i][2] == rows[j][2]:
                    continue
                states.append((rows[i][3] ^ rows[j][3], points[i] + points[j],
                               (1 << rows[i][2]) | (1 << rows[j][2])))
        if len(states) != 1956:
            raise ValueError("independent Sage pair domain changed")
        domains.append(states)

    terms = [()]
    terms.extend((i,) for i in range(52))
    terms.extend(itertools.combinations(range(52), 2))
    terms.extend(triple for triple in itertools.combinations(range(52), 3)
                 if triple[0] < 12)
    if len(terms) != 13599:
        raise ValueError("frozen cubic feature count changed")
    index = {term: pos for pos, term in enumerate(terms)}
    row_capacity = result["counts"]["source_rows_accepted"]
    columns = [bytearray((row_capacity + 7) // 8) for _ in terms]
    valid_indices = []
    counts = {"source_rows_seen": 0, "source_column_rejects": 0,
              "source_rows_accepted": 0}

    for name, records in (("decoded", decoded["rows"]),
                          ("holdout", holdout["rows"])):
        for record in records:
            if counts["source_rows_seen"] >= result["counts"]["source_rows_seen"]:
                break
            counts["source_rows_seen"] += 1
            i, j = record["pair_state_indices"][-2:]
            a, b = domains[0][i], domains[1][j]
            if name == "decoded" and record["pair_seed_sums"] != [a[0], b[0]]:
                raise ValueError("independent seed-sum reconstruction changed")
            if a[2] & b[2]:
                counts["source_column_rejects"] += 1
                continue
            combined = a[1] + b[1]
            if combined == zero or encode(combined) != record["sum_point"]:
                raise ValueError("independent Sage group sum differs")
            x = record["sum_point"][0]
            if x & 1:
                raise ValueError("subgroup x trace differs")
            packed = a[0] | (b[0] << 6) | ((x >> 1) << 12)
            active = [bit for bit in range(52) if packed >> bit & 1]
            position = counts["source_rows_accepted"]
            bit = 1 << (position & 7)
            byte = position >> 3
            columns[0][byte] |= bit
            for degree in (1, 2, 3):
                for term in itertools.combinations(active, degree):
                    if degree == 3 and term[0] >= 12:
                        continue
                    columns[index[term]][byte] |= bit
            valid_indices.append((i, j))
            counts["source_rows_accepted"] += 1
        if counts["source_rows_seen"] >= result["counts"]["source_rows_seen"]:
            break
    if counts != {key: result["counts"][key] for key in counts}:
        raise ValueError("source distinct-column counts differ")
    index_hash = hashlib.sha256(
        ",".join(f"{i}:{j}" for i, j in valid_indices).encode()).hexdigest()
    if index_hash != result["valid_index_pairs_sha256"]:
        raise ValueError("Sage accepted-row ordering differs")
    rank_basis: dict[int, int] = {}
    for column in columns:
        insert_low(rank_basis, int.from_bytes(column, "little"))
    if len(rank_basis) != result["rank"]:
        raise ValueError("independent transposed GF(2) rank differs")

    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if sys.platform != "darwin":
        rss *= 1024
    audit = {
        "kind": "n41_two_pair_distinct_column_mixed_cubic_independent_sage_audit_v2",
        "status": "PASS_FULL_EXACT_RANK_WITNESS",
        "curve_id": protocol["curve_id"], "public_target_q": protocol["public_target_q"],
        "source_subgroup_points_checked": 128, "pair_domain_sizes": [1956, 1956],
        "exact_group_sums_replayed": counts["source_rows_accepted"],
        "source_column_rejects": counts["source_column_rejects"],
        "transposed_low_pivot_rank": len(rank_basis),
        "feature_count": len(terms), "accepted_row_index_sha256": index_hash,
        "audit_wall_ns": time.monotonic_ns() - start,
        "peak_rss_bytes": rss,
        "input_sha256": {"audit_protocol": sha(PROTOCOL),
                         "audit_source": sha(Path(__file__)),
                         **{name: sha(path) for name, path in inputs.items()}},
    }
    with OUTPUT.open("x") as stream:
        json.dump(audit, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"status": audit["status"],
                      "rank": len(rank_basis),
                      "group_sums": counts["source_rows_accepted"],
                      "wall_s": audit["audit_wall_ns"] / 1e9}, sort_keys=True))


if __name__ == "__main__":
    main()

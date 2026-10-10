#!/usr/bin/env sage -python
"""Independent Sage audit of the exact N41 two-pair backward table."""

import hashlib
import json
import random
from collections import Counter
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing

HERE = Path(__file__).resolve().parent
GOAL = HERE.parent
GEOMETRY = GOAL / "n41_w8_fixed_sum_backward_20261009/geometry.json"
RECORD_BYTES = 15
R = 549756390943


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def sage_curve():
    ring = PolynomialRing(GF(2), "t")
    t = ring.gen()
    field = GF(2**41, name="t", modulus=t**41+t**3+1)
    curve = EllipticCurve(field, [1, 0, 0, 0, 1])
    def elem(value):
        return field(ring([(int(value) >> bit) & 1 for bit in range(41)]))
    def integer(value):
        return sum(int(bit) << i for i, bit in enumerate(value.polynomial().list()))
    def point(row):
        return curve(elem(row[0]), elem(row[1]))
    return curve, point, integer


def decode(record):
    return ((int.from_bytes(record[:6], "little"),
             int.from_bytes(record[6:12], "little")),
            record[12], record[13], record[14])


def main():
    output = HERE / "audit.json"
    if output.exists():
        raise FileExistsError("preserve first independent audit")
    protocol = json.loads((HERE / "protocol.json").read_text())
    result = json.loads((HERE / "result.json").read_text())
    if protocol["source_sha256"] != {
            path: sha(path) for path in protocol["source_sha256"]}:
        raise ValueError("frozen source changed")
    if (result["source_sha256"] != protocol["source_sha256"] or
            result["protocol_sha256"] != sha(HERE / "protocol.json") or
            result["table_sha256"] != sha(HERE / "table.bin") or
            result["status"] != "EXACT_TWO_PAIR_DOMAIN" or
            result["charged_target_dependent_wall_ns"] > protocol["time_cap_ns"] or
            result["peak_rss_bytes"] > protocol["rss_cap_bytes"]):
        raise ValueError("frozen terminal receipt failed")
    data = (HERE / "table.bin").read_bytes()
    if len(data) % RECORD_BYTES:
        raise ValueError("truncated packed table")
    geometry = json.loads(GEOMETRY.read_text())
    states4 = geometry["blocks"][4]["states"]
    states5 = geometry["blocks"][5]["states"]
    raw = result["raw_target_preimages"]
    group_count = Counter()
    x_values = set()
    labels = set()
    branch_counts = Counter()
    records = []
    for offset in range(0, len(data), RECORD_BYTES):
        record = decode(data[offset:offset+RECORD_BYTES])
        residual, branch, i, j = record
        if (branch >= len(raw) or i >= len(states4) or j >= len(states5) or
                len(set(states4[i]["columns"]+states5[j]["columns"])) != 4 or
                (branch, i, j) in labels):
            raise ValueError("invalid or duplicate table descriptor")
        labels.add((branch, i, j))
        group_count[residual] += 1
        x_values.add(residual[0])
        branch_counts[branch] += 1
        records.append(record)
    if (len(records) != result["stored_labeled_residuals"] or
            len(group_count) != result["distinct_residual_group_points"] or
            len(x_values) != result["distinct_residual_x_coordinates"] or
            len(records)-len(group_count) != result["group_collision_excess"] or
            max(group_count.values()) != result["maximum_group_multiplicity"]):
        raise ValueError("independent table cardinality audit failed")
    curve, point, integer = sage_curve()
    q = point(result["public_target_q"])
    targets = [point(row) for row in raw]
    if len(targets) != 4 or R*q != curve(0) or any(4*t != q for t in targets):
        raise ValueError("independent raw target preimage audit failed")
    rng = random.Random(20261009181500)
    sampled_offsets = sorted(set(rng.sample(range(len(records)), 40)) |
                             {result["witness_table_offset"]})
    for index in sampled_offsets:
        residual, branch, i, j = records[index]
        actual = targets[branch]-point(states4[i]["raw_sum"])-point(states5[j]["raw_sum"])
        if actual == curve(0) or (integer(actual[0]), integer(actual[1])) != residual:
            raise ValueError(f"independent Sage residual mismatch at {index}")
    witness_indices = result["witness_state_indices"]
    first4 = curve(0)
    for block, index in enumerate(witness_indices[:4]):
        first4 += point(geometry["blocks"][block]["states"][index]["raw_sum"])
    offset = result["witness_table_offset"]
    residual, branch, i, j = records[offset]
    if (branch != result["witness_branch"] or
            (i, j) != tuple(witness_indices[4:]) or
            (integer(first4[0]), integer(first4[1])) != residual or
            4*(first4+point(states4[i]["raw_sum"])+point(states5[j]["raw_sum"])) != q):
        raise ValueError("saved public witness not in exact backward table")
    audited = {"status": "PASS_INDEPENDENT_SAGE_TABLE_AUDIT",
               "proposal_id": result["proposal_id"], "candidate_id": None,
               "curve_id": geometry["curve_id"],
               "table_sha256": result["table_sha256"],
               "protocol_sha256": sha(HERE / "protocol.json"),
               "stored_labeled_residuals": len(records),
               "distinct_residual_group_points": len(group_count),
               "distinct_residual_x_coordinates": len(x_values),
               "branch_counts": dict(branch_counts),
               "sampled_sage_group_replays": len(sampled_offsets),
               "witness_table_offset": offset,
               "witness_scalar_replay": True}
    output.write_text(json.dumps(audited, indent=2, sort_keys=True)+"\n")
    print(json.dumps(audited, sort_keys=True))


if __name__ == "__main__":
    main()

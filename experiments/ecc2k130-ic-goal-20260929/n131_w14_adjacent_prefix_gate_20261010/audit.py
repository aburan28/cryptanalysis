#!/usr/bin/env python3
"""Independent span and positive-identity audit of projected pair gates."""
import hashlib
import json
import random
from pathlib import Path

import run

HERE = Path(__file__).resolve().parent
ADJACENT = run.ADJACENT


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rank_and_membership(columns, value):
    basis = {}
    for column in columns:
        while column:
            lead = column.bit_length() - 1
            if lead not in basis:
                basis[lead] = column
                break
            column ^= basis[lead]
    while value:
        lead = value.bit_length() - 1
        if lead not in basis:
            return len(basis), False
        value ^= basis[lead]
    return len(basis), True


def expected(field, joint, z, width, mask):
    prefix = z & (run.FULL ^ ((1 << width) - 1))
    squared = field.mul(prefix, prefix)
    az = squared ^ prefix
    columns = [field.mul(u, u) & mask for u in joint["sum_u_basis"]]
    columns += [field.mul(az, p) & mask for p in joint["product_basis"]]
    rank, consistent = rank_and_membership(columns, squared & mask)
    return prefix, rank, "CONSISTENT" if consistent else "SPAN_REJECT"


def main():
    protocol = json.loads((HERE / "audit_protocol.json").read_text())
    dependencies = {"audit": HERE / "audit.py", "run": HERE / "run.py",
                    "controls": HERE / "controls.py",
                    "protocol": HERE / "protocol.json", "result": HERE / "result.json",
                    "controls_protocol": HERE / "controls_protocol.json",
                    "controls_result": HERE / "controls_result.json",
                    "adjacent_run": ADJACENT / "run.py",
                    "oracle": run.SOURCE / "oracle.py", "support": run.SUPPORT,
                    "adjacent_result": ADJACENT / "result.json",
                    "adjacent_sage_audit": ADJACENT / "sage_audit.json"}
    assert protocol["status"] == "FROZEN_BEFORE_AUDIT"
    assert protocol["sha256"] == {name: sha(path) for name, path in dependencies.items()}
    adjacent = run.load_adjacent()
    candidate = adjacent.oracle.PairOracle(adjacent.oracle.load_support(run.SUPPORT))
    joint = adjacent.build_joint(candidate)
    field = candidate.field
    first = json.loads((HERE / "result.json").read_text())
    second = json.loads((HERE / "controls_result.json").read_text())
    first_protocol = json.loads((HERE / "protocol.json").read_text())
    second_protocol = json.loads((HERE / "controls_protocol.json").read_text())
    assert first_protocol["sha256"] == {
        "run": sha(HERE / "run.py"), "adjacent_run": sha(ADJACENT / "run.py"),
        "adjacent_result": sha(ADJACENT / "result.json"),
        "oracle": sha(run.SOURCE / "oracle.py"), "support": sha(run.SUPPORT)}
    assert second_protocol["sha256"] == {
        "controls": sha(HERE / "controls.py"), "run": sha(HERE / "run.py"),
        "first_protocol": sha(HERE / "protocol.json"),
        "first_result": sha(HERE / "result.json")}
    source = json.loads((ADJACENT / "result.json").read_text())
    sage = json.loads((ADJACENT / "sage_audit.json").read_text())
    assert sage["status"] == "PASS_INDEPENDENT_SAGE_ADJACENT_W14_RANK_AND_GROUP"
    assert sage["raw_group_replayed"] == 16
    assert first["status"] == "COMPLETE_PROJECTED_GATE"
    assert second["status"] == "COMPLETE_UNIFORM_PREFIX_PANEL"
    assert first["source_sha256"] == first_protocol["sha256"]
    assert second["source_sha256"] == second_protocol["sha256"]
    assert first["wall_ns"] <= first_protocol["wall_cap_seconds"] * 10**9
    assert second["wall_ns"] <= second_protocol["wall_cap_seconds"] * 10**9
    assert first["peak_rss_bytes"] <= first_protocol["rss_cap_bytes"]
    assert second["peak_rss_bytes"] <= second_protocol["rss_cap_bytes"]
    for result in (first, second):
        for width in result["free_low_bits"]:
            mask = run.invariant_mask(field, width, joint["product_basis"])
            assert mask == result["invariant_masks"][str(width)]
            for bit in range(width):
                e = 1 << bit
                sq = field.mul(e, e)
                assert not (sq & mask)
                for p in joint["product_basis"]:
                    assert not (field.mul(sq ^ e, p) & mask)
    query_map = {(r["kind"], r["index"]): r for r in source["records"]}
    assert len(query_map) == 32
    for row in first["rows"]:
        query = query_map[row["kind"], row["input_index"]]
        mask = first["invariant_masks"][str(row["width"])]
        prefix, rank, status = expected(field, joint, query["z"], row["width"], mask)
        assert (row["prefix"], row["rank"], row["nullity"], row["status"]) == (
            prefix, rank, 61-rank, status)
        if row["kind"] == "positive":
            a, b = query["masks"]
            w1 = adjacent.oracle.coordinate(joint["left_w"], a)
            w2 = adjacent.oracle.coordinate(joint["right_w"], b)
            s = w1 ^ w2
            p = field.mul(w1, w2)
            u = adjacent.oracle.half_trace(field, s)
            z2 = field.mul(query["z"], query["z"])
            assert z2 == field.mul(u, u) ^ field.mul(z2 ^ query["z"], p)
            p2 = field.mul(prefix, prefix)
            assert not ((p2 ^ field.mul(u, u) ^ field.mul(p2 ^ prefix, p)) & mask)
            assert status == "CONSISTENT"
    rng = random.Random(second_protocol["seed"])
    values = [rng.getrandbits(131) for _ in range(second_protocol["control_count"])]
    digest = hashlib.sha256(b"".join(v.to_bytes(17, "little") for v in values)).hexdigest()
    assert digest == second["control_digest"]
    assert len(second["rows"]) == len(values) * len(second["free_low_bits"])
    for row in second["rows"]:
        mask = second["invariant_masks"][str(row["width"])]
        _, rank, status = expected(field, joint, values[row["index"]], row["width"], mask)
        assert (row["rank"], row["nullity"], row["status"]) == (rank, 61-rank, status)
    print(json.dumps({"status": "PASS_ADJACENT_PREFIX_AUDIT", "positive_outputs": 16,
                      "uniform_controls": len(values), "rows_checked": len(first["rows"])
                        + len(second["rows"]), "sage_group_replays": 16}))


if __name__ == "__main__":
    main()

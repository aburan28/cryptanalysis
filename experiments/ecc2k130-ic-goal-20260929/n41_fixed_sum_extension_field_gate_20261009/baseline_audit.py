#!/usr/bin/env python3
"""Replay exact fixed-sum lookup output against the frozen public group."""

import hashlib
import json
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing

HERE = Path(__file__).resolve().parent
GOAL = HERE.parent
INPUT = GOAL / "n131_w18_four_pairs/native_join/native_input.txt"
ROW = GOAL / "n41_two_free_pair_compact_lookup_20261009/public_search_v2.json"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    frozen = json.loads((HERE / "baseline_protocol.json").read_text())
    assert frozen["status"] == "FROZEN"
    assert frozen["sha256"]["source"] == sha(HERE / "exact_baseline.py")
    assert frozen["sha256"]["audit"] == sha(__file__)
    assert frozen["sha256"]["core_protocol"] == sha(HERE / "protocol.json")
    assert frozen["sha256"]["input"] == sha(INPUT)
    assert frozen["sha256"]["row"] == sha(ROW)
    assert frozen["sha256"]["runtime"] == sha(HERE / "sage_runtime_info.json")
    core = json.loads((HERE / "protocol.json").read_text())
    core_audit = json.loads((HERE / "audit.json").read_text())
    assert core_audit["status"] == "PASS_INDEPENDENT_SAGE_REPLAY"
    binary = PolynomialRing(GF(2), "x")
    x = binary.gen()
    field = GF(2**41, name="x", modulus=x**41 + x**3 + 1)
    curve = EllipticCurve(field, [1, 0, 0, 0, 1])

    def decode(value):
        return field(binary([(int(value) >> i) & 1 for i in range(41)]))

    def point(coords):
        return curve(decode(coords[0]), decode(coords[1]))

    lines = INPUT.read_text().splitlines()
    slots = []
    pos = 1
    for slot in range(8):
        count = int(lines[pos]); pos += 1
        entries = [tuple(map(int, lines[pos + j].split())) for j in range(count)]
        pos += count
        slots.append(entries)
    assert pos == len(lines)
    q = point(core["target_q"])
    prefix = json.loads(ROW.read_text())["row"][:4]
    prefix_points = [point(leaf["point"]) for leaf in prefix]
    prefix_columns = [leaf["column"] for leaf in prefix]
    statuses = {}
    for case in ("positive", "negative"):
        result = json.loads((HERE / case / "exact_result.json").read_text())
        assert result["baseline_protocol_sha256"] == sha(HERE / "baseline_protocol.json")
        assert result["target"] == core["target_q"]
        assert result["residual"] == core["residual"]
        assert result["sum_masks"] == core[f"{case}_sum_masks"]
        assert result["online_ns"] == (result["leaf_build_ns"] +
                result["pair_build_ns"] + result["target_lookup_ns"] +
                result["interval_overhead_ns"])
        assert result["online_ns"] < frozen["limits"]["per_case_seconds"] * 10**9
        assert result["peak_self_rss_bytes"] < frozen["limits"]["combined_rss_bytes"]
        if case == "negative":
            assert result["status"] == "EXACT_DOMAIN_EMPTY" and result["witness"] is None
            assert core_audit["negative_exact_domain_empty"]
        else:
            assert result["status"] == "VERIFIED_RAW_ROW"
            witness = result["witness"]
            assert witness is not None
            columns = prefix_columns + sum(witness["pair_columns"], [])
            assert len(set(columns)) == 8
            masks = sum(witness["pair_masks"], [])
            assert [masks[0] ^ masks[1], masks[2] ^ masks[3]] == \
                core["positive_sum_masks"]
            suffix_points = [point(coords) for coords in witness["subgroup_points"]]
            assert sum(prefix_points + suffix_points, curve(0)) == q
            assert all(core["subgroup_order"] * p == curve(0)
                       for p in prefix_points + suffix_points)
            for i, p in enumerate(suffix_points):
                slot = i + 4
                candidates = [entry for entry in slots[slot]
                              if entry[2] == columns[slot] and entry[3] == masks[i]]
                assert len(candidates) == 2
                assert any(p == point(entry[:2]) for entry in candidates)
        statuses[case] = result["status"]
    receipt = {"status": "PASS_INDEPENDENT_SAGE_BASELINE_REPLAY",
               "case_statuses": statuses,
               "public_target": core["target_q"],
               "baseline_protocol_sha256": sha(HERE / "baseline_protocol.json")}
    (HERE / "baseline_audit.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()

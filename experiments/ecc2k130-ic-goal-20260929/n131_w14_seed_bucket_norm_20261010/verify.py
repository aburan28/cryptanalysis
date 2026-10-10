#!/usr/bin/env python3
"""Verify frozen N131 source roots and proposed-output query receipts."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
SUPPORT = BASE / "n131_w14_ten_source_gate_20261009/support_w14.tsv"
CONTROL = BASE / "n131_w14_mixed_rotation_fouratom_join_20261010/inputs.json"
NATIVE = BASE / "n131_w14_mixed_rotation_fouratom_join_20261010/result.json"
AUDIT = BASE / "n131_w14_mixed_rotation_fouratom_join_20261010/sage_audit.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(name):
    return json.loads((HERE / name).read_text())


def main():
    prepare = load("prepare_protocol.json")
    query = load("query_protocol.json")
    roots = load("roots.json")
    result = load("query_result.json")
    assert prepare["status"] == query["status"] == "FROZEN"
    for protocol, paths in ((prepare, {"source": HERE / "prepare.py",
                                      "support": SUPPORT, "control": CONTROL,
                                      "runtime": HERE / "sage_runtime_info.json"}),
                            (query, {"source": HERE / "query.py",
                                     "roots": HERE / "roots.json", "control": CONTROL,
                                     "native": NATIVE,
                                     "runtime": HERE / "sage_runtime_info.json"})):
        assert all(protocol["sha256"][key] == sha(path) for key, path in paths.items())
    assert roots["status"] == "COMPLETE_EXACT_ROOTS"
    assert roots["source_sha256"] == sha(HERE / "prepare.py")
    assert roots["protocol_sha256"] == sha(HERE / "prepare_protocol.json")
    assert roots["allowed_source_pairs"] == 2062
    assert roots["distinct_raw_pair_x_per_rotation"] == 4124
    assert roots["setup_ns"] < prepare["wall_cap_seconds"]*10**9
    assert roots["peak_self_rss_bytes"] < prepare["rss_cap_bytes"]
    for rotation in ("26", "39"):
        values = roots["rotations"][rotation]
        assert len(values) == len(set(values)) == 4124
        assert values == sorted(values)
        assert all(0 < value < 2**131 for value in values)
    assert result["status"] == "COMPLETE_N131_PROPOSED_OUTPUT_PANEL"
    assert result["source_sha256"] == sha(HERE / "query.py")
    assert result["protocol_sha256"] == sha(HERE / "query_protocol.json")
    assert result["roots_sha256"] == sha(HERE / "roots.json")
    assert result["pair_outputs_per_rotation"] == 4124
    assert result["elapsed_wall_ns"] < query["wall_cap_seconds"]*10**9
    assert result["peak_self_rss_bytes"] < query["rss_cap_bytes"]
    assert [case["label"] for case in result["cases"]] == query["case_order"]
    expected = {"trace_zero_control": (0, []),
                "positive": (1, [1252034191094050147895298468406210809797])}
    for case in result["cases"]:
        degree, values = expected[case["label"]]
        assert case["gcd_degree"] == degree and case["gcd_roots"] == values
        parts = (case["factor_construction_ns"] +
                 case["balanced_product_and_remainder_ns"] + case["gcd_ns"] +
                 case["root_extraction_ns"])
        assert 0 < parts <= case["target_query_ns"]
        assert case["peak_self_rss_bytes"] < query["rss_cap_bytes"]
    independent = json.loads(AUDIT.read_text())
    assert independent["status"] == "PASS_INDEPENDENT_MIXED_ROTATION_REPLAY"
    assert independent["checks"]["131"]["group_sum_replay"] is True
    assert independent["checks"]["131"]["projected_subgroup_replay"] is True
    assert independent["checks"]["131"]["positive_algebraic_hits"] == 1
    assert independent["checks"]["131"]["control_algebraic_hits"] == 0
    print("PASS: frozen roots, N131 norm decisions, resource caps, and prior group replay")


if __name__ == "__main__":
    main()

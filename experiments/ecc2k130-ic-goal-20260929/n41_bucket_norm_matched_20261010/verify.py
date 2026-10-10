#!/usr/bin/env python3
"""Verify matched-input and retained exact decisions for the norm panel."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
PREVIOUS = BASE / "n41_seed_bucket_resultant_20261010"
GEOMETRY = BASE / "n41_two_free_pair_occupancy_20261009/geometry_snapshot.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    protocol = json.loads((HERE / "protocol.json").read_text())
    result = json.loads((HERE / "result.json").read_text())
    paths = {"source": HERE / "compare.py", "helper": PREVIOUS / "run.py",
             "bsgs": PREVIOUS / "norm_bsgs.py", "geometry": GEOMETRY,
             "prior_audit": PREVIOUS / "audit.json",
             "prior_result": PREVIOUS / "result.json",
             "runtime": HERE / "sage_runtime_info.json"}
    assert protocol["status"] == "FROZEN"
    assert all(protocol["sha256"][key] == sha(path) for key, path in paths.items())
    assert result["status"] == "COMPLETE_MATCHED_BUCKET_PANEL"
    assert result["source_sha256"] == sha(HERE / "compare.py")
    assert result["protocol_sha256"] == sha(HERE / "protocol.json")
    assert result["elapsed_wall_ns"] < protocol["wall_cap_seconds"] * 10**9
    assert result["peak_rss_bytes"] < protocol["rss_cap_bytes"]
    assert result["public_target_q"] == protocol["public_target_q"]
    assert result["residual"] == protocol["residual"]
    audit = json.loads((PREVIOUS / "audit.json").read_text())
    old = json.loads((PREVIOUS / "result.json").read_text())
    assert audit["status"] == "PASS" and audit["eight_column_public_row_replay"] == "PASS"
    assert [case["label"] for case in result["cases"]] == protocol["case_order"]
    for case in result["cases"]:
        label = case["label"]
        expected = next(row for row in old["cases"] if row["label"] == label)
        assert case["seeds"] == protocol["cases"][label]
        assert case["resultant_norm_identity_mod_left"] is True
        assert [row["method"] for row in case["observations"]] == protocol["method_order"]
        for row in case["observations"]:
            assert row["gcd_roots"] == expected["gcd_roots"]
            assert row["gcd_degree"] == expected["gcd_degree"]
            assert 0 < row["target_query_ns"] < protocol["wall_cap_seconds"] * 10**9
        assert case["left_degree"] == expected["left_x_count"]
        assert case["right_degree"] == expected["right_x_count"]
    print("PASS: frozen identities, paired order, norm congruence, and audited roots")


if __name__ == "__main__":
    main()

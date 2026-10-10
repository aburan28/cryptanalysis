#!/usr/bin/env python3
"""Bind exact N131 root-evaluation receipts to prior GCD and group checks."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
PREVIOUS = BASE / "n131_w14_seed_bucket_norm_20261010"
CONTROL = BASE / "n131_w14_mixed_rotation_fouratom_join_20261010/inputs.json"
AUDIT = BASE / "n131_w14_mixed_rotation_fouratom_join_20261010/sage_audit.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    protocol = json.loads((HERE / "protocol.json").read_text())
    result = json.loads((HERE / "result.json").read_text())
    previous = json.loads((PREVIOUS / "query_result.json").read_text())
    sources = {"source": HERE / "run.py", "prior_source": PREVIOUS / "query.py",
               "roots": PREVIOUS / "roots.json",
               "prior_result": PREVIOUS / "query_result.json",
               "control": CONTROL, "runtime": HERE / "sage_runtime_info.json"}
    assert protocol["status"] == "FROZEN"
    assert all(protocol["sha256"][key] == sha(path) for key, path in sources.items())
    assert result["status"] == "COMPLETE_N131_ROOT_EVALUATION_PANEL"
    assert result["source_sha256"] == sha(HERE / "run.py")
    assert result["protocol_sha256"] == sha(HERE / "protocol.json")
    assert result["prior_result_sha256"] == sha(PREVIOUS / "query_result.json")
    assert result["elapsed_wall_ns"] < protocol["wall_cap_seconds"] * 10**9
    assert result["peak_self_rss_bytes"] < protocol["rss_cap_bytes"]
    assert result["tree_levels"] == 14
    assert result["pair_outputs_per_rotation"] == 4124
    assert [row["label"] for row in result["cases"]] == protocol["case_order"]
    assert previous["status"] == "COMPLETE_N131_PROPOSED_OUTPUT_PANEL"
    for row in result["cases"]:
        prior = next(x for x in previous["cases"] if x["label"] == row["label"])
        assert row["zero_roots"] == prior["gcd_roots"]
        assert row["query_x"] == prior["query_x"]
        assert row["norm_remainder_degree"] == prior["norm_remainder_degree"]
        assert row["remainder_levels_checked"] == 13
        parts = (row["factor_construction_ns"] +
                 row["balanced_product_and_remainder_ns"] +
                 row["remainder_tree_root_scan_ns"])
        assert 0 < parts <= row["target_query_ns"]
        assert row["peak_self_rss_bytes"] < protocol["rss_cap_bytes"]
    old_audit = json.loads(AUDIT.read_text())
    assert old_audit["status"] == "PASS_INDEPENDENT_MIXED_ROTATION_REPLAY"
    assert old_audit["checks"]["131"]["group_sum_replay"] is True
    assert old_audit["checks"]["131"]["projected_subgroup_replay"] is True
    lines = (HERE / "run.stdout.txt").read_text().splitlines()
    assert lines[0] == "START_N131_ROOT_EVALUATION"
    assert len([line for line in lines if '"stage": "QUERY_DONE"' in line]) == 4
    assert '"status": "COMPLETE_N131_ROOT_EVALUATION_PANEL"' in lines[-1]
    assert (HERE / "run.stderr.txt").read_text() == ""
    print("PASS: frozen sources, four exact roots scans, resource caps, and group replay")


if __name__ == "__main__":
    main()

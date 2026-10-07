#!/usr/bin/env python3
"""Read-only raw receipt audit for the sparse native old-data control."""

import hashlib
import json
from pathlib import Path
import subprocess

from check_tau3_atlas_panel import fields, int_field


ROOT = Path(__file__).resolve().parent
SPARSE_PANEL_COMMIT = "d952227e91e67a50516eb63fbe56a09ff6aeb7f2"


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sparse_source_sha256(path):
    repository = ROOT.parents[1]
    subprocess.run(["git", "merge-base", "--is-ancestor", SPARSE_PANEL_COMMIT, "HEAD"],
                   cwd=repository, check=True, capture_output=True)
    content = subprocess.check_output(["git", "show", f"{SPARSE_PANEL_COMMIT}:{path}"],
                                      cwd=repository)
    return hashlib.sha256(content).hexdigest()


def main():
    receipt = json.loads((ROOT / "tau3-sparse-native-design.json").read_text())
    fixture = json.loads((ROOT / "compact-pos-inputs.json").read_text())
    screen = json.loads((ROOT / "tau3-sparse-screen.json").read_text())
    design = {record["curve"]: record for record in screen["records"]}
    assert receipt["status"] == "retrospective_sparse_native_control"
    assert receipt["cpu_timing_claim"] is None
    assert receipt["runner_sha256"] == sha256(ROOT / "check_tau3_sparse_native_design.py")
    assert receipt["fixture_sha256"] == sha256(ROOT / "compact-pos-inputs.json")
    assert receipt["screen_sha256"] == sha256(ROOT / "tau3-sparse-screen.json")
    assert receipt["ec_tau_source_sha256"] == sparse_source_sha256("src/ec_tau.c")
    assert receipt["header_sha256"] == sha256(ROOT.parents[1] / "src/generated/tau3_sparse.h")
    assert len(receipt["rows"]) == 16 and len(receipt["pairs"]) == 8
    rows = {(row["case_id"], row["mode"]): row for row in receipt["rows"]}
    assert len(rows) == 16
    for case, pair in zip(fixture["cases"], receipt["pairs"]):
        assert pair["case_id"] == case["id"] and pair["verified"] and pair["gate_pass"]
        old = rows[(case["id"], "tau3-atlas-pos")]
        new = rows[(case["id"], "tau3-sparse-pos")]
        for row in (old, new):
            assert row["exit_code"] == 0 and not row["timed_out"] and not row["stderr"]
            assert row["verified"] and row["fields"] == fields(row["stdout"])
            f = row["fields"]
            assert f["verified"] == "1" and f["count"] == "4096"
            assert f["input_digest"] == case["input_digest"]
            assert f["output_digest"] == case["expected_output_digest"]
            assert f["base_x"] == case["base_x"] and f["base_y"] == case["base_y"]
        target = design[case["curve"]["name"]]
        assert int_field(new, "point_entries") == target["point_entries"]
        assert int_field(new, "point_table_bytes") == target["point_bytes"]
        assert int_field(new, "prep_adds") == target["hot_entries"]
        assert int_field(new, "sparse_preparation_checks") == target["point_entries"]
        assert int_field(new, "sparse_checks") == 4096
        assert int_field(new, "sparse_action_fallbacks") == int_field(new, "fallbacks") == 0
        assert new["fields"]["sparse_action_digest"] == old["fields"]["tau3_action_digest"]
        assert pair["full_adds"] == int_field(old, "adds")
        assert pair["sparse_adds"] == int_field(new, "adds")
        assert pair["cold_pairs"] == int_field(new, "sparse_cold_pairs")
        assert pair["sparse_adds"] - pair["full_adds"] == pair["cold_pairs"]
    for curve, target in design.items():
        aggregate = receipt["aggregate"][curve]
        assert aggregate["matched"]
        assert aggregate["full_adds"] == aggregate["screen_full_adds"] == target["full_fused_adds"]
        assert aggregate["sparse_adds"] == aggregate["screen_sparse_adds"] == target["predicted_sparse_adds"]
    print("tau3 sparse native design audit: PASS (32,768 outputs; exact old-data operation screen)")


if __name__ == "__main__":
    main()

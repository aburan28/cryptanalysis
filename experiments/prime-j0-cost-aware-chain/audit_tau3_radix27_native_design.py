#!/usr/bin/env python3
"""Read-only audit of raw old-data native radix-27 control arms."""

import hashlib
import json
from pathlib import Path

from check_tau3_atlas_panel import fields, int_field


ROOT = Path(__file__).resolve().parent


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    receipt = json.loads((ROOT / "tau3-radix27-native-design.json").read_text())
    fixture = json.loads((ROOT / "compact-pos-inputs.json").read_text())
    screen = json.loads((ROOT / "tau3-radix27-screen.json").read_text())
    expected = {row["case_id"]: row for row in screen["rows"]}
    assert receipt["status"] == "retrospective_radix27_native_control"
    assert receipt["cpu_timing_claim"] is None and receipt["isolated_receipt"] is None
    assert receipt["runner_sha256"] == sha256(ROOT / "check_tau3_radix27_native_design.py")
    assert receipt["arm_runner_sha256"] == sha256(ROOT / "check_tau3_atlas_panel.py")
    assert receipt["fixture_sha256"] == sha256(ROOT / "compact-pos-inputs.json")
    assert receipt["screen_sha256"] == sha256(ROOT / "tau3-radix27-screen.json")
    assert receipt["bench_source_sha256"] == sha256(ROOT / "bench.c")
    assert receipt["ec_tau_source_sha256"] == sha256(ROOT.parents[1] / "src/ec_tau.c")
    assert receipt["map_header_sha256"] == sha256(ROOT.parents[1] / "src/generated/tau3_radix27.h")
    assert len(receipt["rows"]) == 16 and len(receipt["pairs"]) == 8
    for index, (case, pair) in enumerate(zip(fixture["cases"], receipt["pairs"])):
        baseline, candidate = receipt["rows"][2 * index:2 * index + 2]
        assert (baseline["case_id"], baseline["mode"]) == (case["id"], "tau3-sparse-pos")
        assert (candidate["case_id"], candidate["mode"]) == (case["id"], "tau3-radix27-pos")
        for row in (baseline, candidate):
            assert row["exit_code"] == 0 and not row["timed_out"] and not row["stderr"]
            assert row["verified"] and row["fields"] == fields(row["stdout"])
            f = row["fields"]
            assert f["verified"] == "1" and f["count"] == "4096"
            assert f["input_digest"] == case["input_digest"]
            assert f["output_digest"] == case["expected_output_digest"]
            assert f["base_x"] == case["base_x"] and f["base_y"] == case["base_y"]
        design = expected[case["id"]]
        assert int_field(baseline, "adds") == pair["sparse_adds"] == design["native_sparse_additions"]
        assert int_field(candidate, "adds") == pair["optimal_adds"] == design["optimal_additions"]
        assert pair["optimal_adds"] <= pair["sparse_adds"]
        assert pair["dp_states"] == int_field(candidate, "radix27_dp_states") > 0
        assert pair["dp_options"] == int_field(candidate, "radix27_dp_options") > 0
        assert int_field(candidate, "radix27_checks") == 4096
        assert int_field(candidate, "radix27_action_fallbacks") == 0
        assert int_field(candidate, "fallbacks") == 0
        assert int_field(candidate, "static_map_bytes") == 55222
        entries = 396 if case["curve"]["name"] == "glv-j0-32" else 756
        assert int_field(candidate, "point_entries") == entries
        assert int_field(candidate, "point_table_bytes") == entries * 32
        assert int_field(candidate, "sparse_preparation_checks") == entries
        assert pair["verified"] and pair["gate_pass"]
    print("tau3 radix-27 native design audit: PASS (16 arms, 32,768 exact outputs)")


if __name__ == "__main__":
    main()

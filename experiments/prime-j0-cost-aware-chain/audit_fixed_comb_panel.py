#!/usr/bin/env python3
"""Read-only replay of frozen fixed-comb and positional-control evidence."""

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fields(stdout):
    return dict(item.split("=", 1) for item in stdout.strip().split())


def main():
    fixture_path = HERE / "mixed-full-inputs.json"
    prior_path = HERE / "mixed-full-native-panel.json"
    panel = json.loads((HERE / "fixed-comb9-panel.json").read_text())
    fixture = json.loads(fixture_path.read_text())
    prior = json.loads(prior_path.read_text())
    assert panel["source_sha256"] == sha256(HERE / "check_fixed_comb_panel.py")
    assert panel["fixture_sha256"] == sha256(fixture_path)
    assert panel["prior_panel_sha256"] == sha256(prior_path)
    assert panel["isolated_receipt"] is None and panel["cpu_timing_claim"] is None
    assert panel["status"] == "exploratory_correctness_and_operation_control"
    cases = {case["id"]: case for case in fixture["cases"]}
    prior_pairs = {pair["case_id"]: pair for pair in prior["pairs"]}
    assert len(cases) == len(prior_pairs) == len(panel["rows"]) == 8
    assert {row["case_id"] for row in panel["rows"]} == set(cases)
    for row in panel["rows"]:
        case = cases[row["case_id"]]
        assert row["exit_code"] == 0 and not row["timed_out"] and not row["stderr"]
        assert row["fields"] == fields(row["stdout"])
        assert row["verified"] and row["fields"]["verified"] == "1"
        assert row["fields"]["input_digest"] == case["input_digest"]
        assert row["fields"]["output_digest"] == case["expected_output_digest"]
        assert row["fields"]["base_x"] == case["base_x"]
        assert row["fields"]["base_y"] == case["base_y"]
        assert int(row["fields"]["point_entries"]) == 512
        assert int(row["fields"]["point_table_bytes"]) == 16384
        assert int(row["fields"]["prep_layer_inversions"]) == 1
        assert row["comb_score"] == (8 * int(row["fields"]["doubles"]) +
                                     16 * int(row["fields"]["adds"]))
        assert row["full_digit_score"] == prior_pairs[row["case_id"]]["full_score"]
        assert row["operation_gate_pass"] == (row["comb_score"] < row["full_digit_score"])
        pos = row["pos_global"]
        assert pos["exit_code"] == 0 and not pos["timed_out"] and not pos["stderr"]
        assert pos["fields"] == fields(pos["stdout"])
        assert pos["verified"] and pos["fields"]["verified"] == "1"
        assert pos["fields"]["input_digest"] == case["input_digest"]
        assert pos["fields"]["output_digest"] == case["expected_output_digest"]
        assert pos["score"] == (16 * int(pos["fields"]["adds"]) +
                                int(pos["fields"]["rotations"]))
    print("fixed-comb9 control audit: PASS (8 paired frozen cases, 16 verified arms)")


if __name__ == "__main__":
    main()

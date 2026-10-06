#!/usr/bin/env python3
"""Read-only integrity and operation-gate audit of the prospective tau3 atlas panel."""

import hashlib
import json
from pathlib import Path

from check_tau3_atlas_panel import fields, int_field


ROOT = Path(__file__).resolve().parent


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    panel = json.loads((ROOT / "tau3-atlas-panel.json").read_text())
    fixture_path = ROOT / "tau3-atlas-inputs.json"
    fixture = json.loads(fixture_path.read_text())
    assert panel["status"] == "exploratory_correctness_and_operation_gate"
    assert panel["runner_sha256"] == sha256(ROOT / "check_tau3_atlas_panel.py")
    assert panel["fixture_sha256"] == sha256(fixture_path)
    assert panel["ec_tau_source_sha256"] == sha256(ROOT.parents[1] / "src/ec_tau.c")
    assert panel["header_sha256"] == sha256(ROOT.parents[1] / "src/generated/tau3_atlas.h")
    assert panel["isolated_receipt"] is None and panel["cpu_timing_claim"] is None
    assert len(panel["rows"]) == 16 and len(panel["pairs"]) == 8
    assert len(fixture["cases"]) == 8
    rows = {(row["case_id"], row["mode"]): row for row in panel["rows"]}
    assert len(rows) == 16
    assert [pair["case_id"] for pair in panel["pairs"]] == [case["id"] for case in fixture["cases"]]
    for index, (case, pair) in enumerate(zip(fixture["cases"], panel["pairs"])):
        modes = [row["mode"] for row in panel["rows"][2 * index:2 * index + 2]]
        expected_order = (["tau3-fused-pos", "tau3-atlas-pos"] if index % 2 == 0 else
                          ["tau3-atlas-pos", "tau3-fused-pos"])
        assert modes == expected_order
        assert all(row["case_id"] == case["id"] for row in panel["rows"][2 * index:2 * index + 2])
        for mode in expected_order:
            row = rows[(case["id"], mode)]
            assert row["mode"] == mode
            if row["exit_code"] == 0 and "parse_error" not in row:
                assert row["fields"] == fields(row["stdout"])
                f = row["fields"]
                verified = (f.get("verified") == "1"
                            and f.get("curve") == case["curve"]["name"]
                            and f.get("point_index") == str(case["point_index"])
                            and f.get("count") == "4096"
                            and f.get("input_digest") == case["input_digest"]
                            and f.get("output_digest") == case["expected_output_digest"]
                            and f.get("base_x") == case["base_x"]
                            and f.get("base_y") == case["base_y"])
            else:
                verified = False
            assert row["verified"] == verified
        control = rows[(case["id"], "tau3-fused-pos")]
        candidate = rows[(case["id"], "tau3-atlas-pos")]
        verified = control["verified"] and candidate["verified"]
        entries = 1372 if case["curve"]["name"] == "glv-j0-32" else 2401
        control_adds = int_field(control, "adds")
        candidate_adds = int_field(candidate, "adds")
        passed = (verified and control_adds is not None and candidate_adds == control_adds
                  and int_field(candidate, "rotations") == int_field(control, "rotations")
                  and int_field(candidate, "fallbacks") == 0
                  and int_field(candidate, "tau3_action_fallbacks") == 0
                  and int_field(candidate, "tau3_checks") == 4096
                  and int_field(candidate, "tau3_atlas_checks") == 4096
                  and int_field(candidate, "tau3_preparation_checks") == entries
                  and int_field(candidate, "point_entries") == entries
                  and int_field(candidate, "point_table_bytes") == entries * 32
                  and int_field(candidate, "output_inversions") is not None
                  and int_field(candidate, "output_inversions") == int_field(control, "output_inversions")
                  and candidate.get("fields", {}).get("tau3_action_digest") is not None
                  and candidate.get("fields", {}).get("tau3_action_digest") ==
                  control.get("fields", {}).get("tau3_action_digest")
                  and int_field(candidate, "static_map_bytes") is not None
                  and int_field(control, "static_map_bytes") is not None
                  and int_field(candidate, "static_map_bytes") -
                  int_field(control, "static_map_bytes") == 26244)
        assert pair == {"case_id": case["id"], "verified": verified,
                        "gate_pass": passed, "control_adds": control_adds,
                        "candidate_adds": candidate_adds,
                        "control_rotations": int_field(control, "rotations"),
                        "candidate_rotations": int_field(candidate, "rotations"),
                        "candidate_fallbacks": int_field(candidate, "fallbacks")}
    wins = sum(pair["gate_pass"] for pair in panel["pairs"])
    print(f"tau3 atlas panel audit: PASS (16 raw arms, {wins}/8 operation gates)")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Read-only integrity and operation-gate audit of the prospective tau3 panel."""

import hashlib
import json
from pathlib import Path

from check_tau3_fused_panel import fields, int_field
from audit_tau3_fused_format import verify_format_equivalence


ROOT = Path(__file__).resolve().parent


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    panel = json.loads((ROOT / "tau3-fused-panel.json").read_text())
    fixture_path = ROOT / "tau3-fused-inputs.json"
    fixture = json.loads(fixture_path.read_text())
    assert panel["status"] == "exploratory_correctness_and_operation_gate"
    assert panel["runner_sha256"] == sha256(ROOT / "check_tau3_fused_panel.py")
    assert panel["fixture_sha256"] == sha256(fixture_path)
    verify_format_equivalence(panel["ec_tau_source_sha256"], panel["bench_sha256"])
    assert panel["header_sha256"] == sha256(ROOT.parents[1] / "src/generated/tau3_fused.h")
    assert panel["isolated_receipt"] is None and panel["cpu_timing_claim"] is None
    assert len(panel["rows"]) == 16 and len(panel["pairs"]) == 8
    assert len(fixture["cases"]) == 8
    rows = {(row["case_id"], row["mode"]): row for row in panel["rows"]}
    assert len(rows) == 16
    assert [pair["case_id"] for pair in panel["pairs"]] == [case["id"] for case in fixture["cases"]]
    for index, (case, pair) in enumerate(zip(fixture["cases"], panel["pairs"])):
        modes = [row["mode"] for row in panel["rows"][2 * index:2 * index + 2]]
        expected_order = (["pos-compact", "tau3-fused-pos"] if index % 2 == 0 else
                          ["tau3-fused-pos", "pos-compact"])
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
        control = rows[(case["id"], "pos-compact")]
        candidate = rows[(case["id"], "tau3-fused-pos")]
        verified = control["verified"] and candidate["verified"]
        entries = 1372 if case["curve"]["name"] == "glv-j0-32" else 2401
        control_adds = int_field(control, "adds")
        candidate_adds = int_field(candidate, "adds")
        passed = (verified and control_adds is not None and candidate_adds is not None
                  and candidate_adds < control_adds
                  and int_field(candidate, "fallbacks") == 0
                  and int_field(candidate, "tau3_action_fallbacks") == 0
                  and int_field(candidate, "tau3_checks") == 4096
                  and int_field(candidate, "tau3_preparation_checks") == entries
                  and int_field(candidate, "point_entries") == entries
                  and int_field(candidate, "point_table_bytes") == entries * 32
                  and int_field(candidate, "output_inversions") is not None
                  and int_field(candidate, "output_inversions") == int_field(control, "output_inversions"))
        assert pair == {"case_id": case["id"], "verified": verified,
                        "gate_pass": passed, "control_adds": control_adds,
                        "candidate_adds": candidate_adds,
                        "candidate_rotations": int_field(candidate, "rotations"),
                        "candidate_fallbacks": int_field(candidate, "fallbacks")}
    wins = sum(pair["gate_pass"] for pair in panel["pairs"])
    print(f"tau3 panel audit: PASS (16 raw arms, {wins}/8 operation gates)")


if __name__ == "__main__":
    main()

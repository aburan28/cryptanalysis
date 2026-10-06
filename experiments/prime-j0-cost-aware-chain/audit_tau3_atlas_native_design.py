#!/usr/bin/env python3
"""Read-only audit of the old-fixture native atlas differential."""

import hashlib
import json
from pathlib import Path

from check_tau3_fused_panel import fields
from audit_tau3_atlas_format import verify_format_equivalence


ROOT = Path(__file__).resolve().parent


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    receipt = json.loads((ROOT / "tau3-atlas-native-design.json").read_text())
    fixture_path = ROOT / "compact-pos-inputs.json"
    fixture = json.loads(fixture_path.read_text())
    assert receipt["status"] == "retrospective_native_design_control"
    assert receipt["fixture_sha256"] == sha256(fixture_path)
    assert receipt["runner_sha256"] == sha256(ROOT / "check_tau3_atlas_native_design.py")
    verify_format_equivalence(receipt["ec_tau_source_sha256"], receipt["bench_sha256"])
    assert receipt["atlas_header_sha256"] == sha256(ROOT.parents[1] / "src/generated/tau3_atlas.h")
    assert receipt["cpu_timing_claim"] is None
    assert len(receipt["rows"]) == 16 and len(receipt["pairs"]) == 8
    rows = {(row["case_id"], row["mode"]): row for row in receipt["rows"]}
    assert len(rows) == 16
    for case, pair in zip(fixture["cases"], receipt["pairs"]):
        assert pair == {"case_id": case["id"], "matched": True}
        old = rows[(case["id"], "tau3-fused-pos")]
        new = rows[(case["id"], "tau3-atlas-pos")]
        for row in (old, new):
            assert row["exit_code"] == 0 and not row["timed_out"] and not row["stderr"]
            assert row["verified"] and row["fields"] == fields(row["stdout"])
            f = row["fields"]
            assert f["verified"] == "1" and f["count"] == "4096"
            assert f["input_digest"] == case["input_digest"]
            assert f["output_digest"] == case["expected_output_digest"]
            assert f["base_x"] == case["base_x"] and f["base_y"] == case["base_y"]
        a, b = old["fields"], new["fields"]
        assert all(a[k] == b[k] for k in
                   ("adds", "rotations", "output_inversions", "point_entries",
                    "point_table_bytes", "tau3_action_digest"))
        assert b["tau3_atlas_checks"] == "4096"
        assert b["tau3_action_fallbacks"] == b["fallbacks"] == "0"
        assert int(b["static_map_bytes"]) - int(a["static_map_bytes"]) == 26244
    print("tau3 atlas native design audit: PASS (32,768 exact action digests; 16 generic outputs)")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Read-only audit of the compact positional held-out comparison."""

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fields(stdout):
    return dict(token.split("=", 1) for token in stdout.strip().split())


def main():
    panel = json.loads((ROOT / "compact-pos-panel.json").read_text())
    fixture_path = ROOT / "compact-pos-inputs.json"
    fixture = json.loads(fixture_path.read_text())
    assert panel["runner_sha256"] == sha256(ROOT / "check_compact_pos_panel.py")
    assert panel["fixture_sha256"] == sha256(fixture_path)
    assert panel["isolated_receipt"] is None and panel["cpu_timing_claim"] is None
    assert len(panel["rows"]) == 16 and len(panel["pairs"]) == 8
    cases = {case["id"]: case for case in fixture["cases"]}
    rows = {(row["case_id"], row["mode"]): row for row in panel["rows"]}
    assert len(rows) == 16
    for case_id, case in cases.items():
        for mode in ("pos-global", "pos-compact"):
            row = rows[(case_id, mode)]
            assert row["exit_code"] == 0 and not row["timed_out"] and not row["stderr"]
            assert row["fields"] == fields(row["stdout"])
            f = row["fields"]
            assert row["verified"] and f["verified"] == "1"
            assert f["curve"] == case["curve"]["name"]
            assert f["point_index"] == str(case["point_index"])
            assert f["input_digest"] == case["input_digest"]
            assert f["output_digest"] == case["expected_output_digest"]
            assert f["base_x"] == case["base_x"] and f["base_y"] == case["base_y"]
        full = rows[(case_id, "pos-global")]["fields"]
        compact = rows[(case_id, "pos-compact")]["fields"]
        pair = next(pair for pair in panel["pairs"] if pair["case_id"] == case_id)
        assert pair["verified"] and pair["gate_pass"]
        assert all(full[key] == compact[key] for key in
                   ("adds", "rotations", "output_inversions"))
        assert int(compact["fallbacks"]) == pair["compact_fallbacks"] == 0
        assert int(compact["point_table_bytes"]) == pair["compact_point_table_bytes"]
        assert int(compact["point_table_bytes"]) * 3 <= panel["full_point_table_bytes"]
        assert int(compact["prep_triples"]) * 3 <= int(full["prep_triples"])
        assert int(compact["prep_layer_inversions"]) == int(full["prep_layer_inversions"]) == 1
        assert int(compact["adds"]) == pair["compact_adds"] == pair["full_adds"]
    print("compact-pos panel audit: PASS (8 paired cases, 16 verified arms)")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Read-only replay of all saved native width-three action traces."""

import gzip
import hashlib
import json
from pathlib import Path
import struct

from check_tau3_fused_native_design import expected_actions
from make_tau3_fused import build


ROOT = Path(__file__).resolve().parent


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def main():
    report = json.loads((ROOT / "tau3-fused-native-design.json").read_text())
    fixture_path = ROOT / "compact-pos-inputs.json"
    screen_path = ROOT / "tau3-fused-screen.json"
    fixture = json.loads(fixture_path.read_text())
    screen = json.loads(screen_path.read_text())
    assert report["status"] == "old_data_exact_native_action_match"
    assert report["source_sha256"] == sha256(
        (ROOT / "check_tau3_fused_native_design.py").read_bytes())
    assert report["fixture_sha256"] == sha256(fixture_path.read_bytes())
    assert report["screen_sha256"] == sha256(screen_path.read_bytes())
    assert report["cpu_timing_claim"] is None and len(report["rows"]) == 8
    cases = {case["id"]: case for case in fixture["cases"]}
    designs = {row["case_id"]: row for row in screen["rows"]}
    digit, residue, _, orbit_id, orbit_unit, _ = build()
    checked = 0
    for row in report["rows"]:
        case = cases[row["case_id"]]
        design = designs[row["case_id"]]
        assert row["status"] == 0 and row["verified"] and row["scalars"] == 4096
        assert row["input_digest"] == case["input_digest"]
        assert row["output_digest"] == case["expected_output_digest"]
        assert row["adds"] == design["predicted_tau3_fused_adds"]
        assert row["rotations"] == design["predicted_rotations"]
        assert row["point_table_bytes"] == design["prepared_blocks"] * 343 * 32
        assert row["prep_verify_points"] == design["prepared_blocks"] * 343
        assert row["prep_layer_inversions"] == 2
        compressed = (ROOT / row["trace_file"]).read_bytes()
        assert sha256(compressed) == row["trace_gzip_sha256"]
        raw_trace = gzip.decompress(compressed)
        assert sha256(raw_trace) == row["trace_sha256"]
        trace_lines = raw_trace.decode().splitlines()
        scalar_path = ROOT / case["scalar_file"]
        scalar_bytes = scalar_path.read_bytes()
        assert sha256(scalar_bytes) == case["scalar_file_sha256"]
        scalars = [word for (word,) in struct.iter_unpack("<Q", scalar_bytes)]
        assert len(trace_lines) == len(scalars) == 4096
        # The lattice eigenvalue is the negative of the reported endomorphism
        # eigenvalue. These two subgroup orders and eigenvalues are pinned by
        # the older bench receipt used by the design screen.
        prior = json.loads((ROOT / "compact-pos-panel.json").read_text())
        old = next(r["fields"] for r in prior["rows"] if r["case_id"] == case["id"]
                   and r["mode"] == "pos-compact")
        order = case["curve"]["order"]
        lattice_lambda = (order - int(old["endo_lambda"])) % order
        for index, (line, scalar) in enumerate(zip(trace_lines, scalars)):
            pieces = line.split(":")
            assert pieces[0] == f"tau3_actions={index}"
            actual = [int(value) for value in pieces[2:]]
            assert int(pieces[1]) == len(actual)
            expected = expected_actions(scalar, order, lattice_lambda,
                                        digit, residue, orbit_id, orbit_unit)
            assert actual == expected, (case["id"], index)
            checked += 1
    assert checked == 32768
    print("tau3 native action audit: PASS (32,768 exact action streams)")


if __name__ == "__main__":
    main()

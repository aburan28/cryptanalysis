#!/usr/bin/env python3
"""Read-only audit of the frozen full-digit mixed-tail held-out panel."""

import argparse
import hashlib
import json
from pathlib import Path

from make_inputs import read_fields


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
UNIT = "tail-pair-mixed-radix"
FULL = "tail-pair-mixed-full-digits"
FIXTURE_SHA256 = "fb7661410d765073239759d4e87c660d6e17c4baad345f9fd5804b41a56a6991"


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(bench):
    receipt = json.loads((ROOT / "mixed-full-native-panel.json").read_text())
    fixture_path = ROOT / "mixed-full-inputs.json"
    fixture = json.loads(fixture_path.read_text())
    assert sha256(fixture_path) == receipt["fixture_sha256"] == FIXTURE_SHA256
    assert receipt["schema"] == 1 and receipt["status"] == "native_operation_gate_pass"
    assert receipt["cpu_timing_claim"] is None and receipt["isolated_receipt"] is None
    assert receipt["protocol_freeze_commit"] == "ef9aef0e"
    assert receipt["implementation_commit"] == "27943663"
    assert receipt["fixture_runner_commit"].startswith("9fb9ec3a")
    assert len(fixture["cases"]) == 8 and len(receipt["rows"]) == 16
    assert len(receipt["pairs"]) == 8
    if bench is not None:
        assert sha256(bench) == receipt["bench_sha256"]
    assert sha256(REPO / "build-cost-aware/CMakeCache.txt") == receipt["build_cache_sha256"]
    for name, digest in receipt["source_sha256"].items():
        assert sha256(REPO / name) == digest, name
    for case_index, case in enumerate(fixture["cases"]):
        scalar_path = ROOT / case["scalar_file"]
        assert sha256(scalar_path) == case["scalar_file_sha256"]
        group = receipt["rows"][2 * case_index:2 * case_index + 2]
        order = (UNIT, FULL) if case_index % 2 == 0 else (FULL, UNIT)
        assert tuple(row["arm"] for row in group) == order
        arms = {}
        for position, row in enumerate(group):
            arm = row["arm"]
            arms[arm] = row
            assert row["case_id"] == case["id"]
            assert row["case_run_position"] == position
            assert row["curve"] == case["curve"]["name"]
            assert row["point_index"] == case["point_index"]
            assert row["command"][1:] == [arm, case["curve"]["name"],
                                            str(case["point_index"]), str(scalar_path)]
            assert row["status"] == "exited" and row["returncode"] == 0
            assert row["verified"] and not row["failures"] and not row["stderr"]
            fields = read_fields(row["stdout"])
            for key, expected in (("curve", case["curve"]["name"]),
                                  ("point_index", str(case["point_index"])),
                                  ("count", "4096"),
                                  ("input_digest", case["input_digest"]),
                                  ("output_digest", case["expected_output_digest"]),
                                  ("point_entries", "726"),
                                  ("tail_complete_preparation_checks", "726"),
                                  ("mixed_checks", "4096"),
                                  ("mixed_fallbacks", "0"),
                                  ("prep_bytes", "24336"),
                                  ("point_table_bytes", "23232"),
                                  ("static_map_bytes", "99853"),
                                  ("rotations", "0"), ("verified", "1")):
                assert fields.get(key) == expected, (case["id"], arm, key)
            counts = {name: int(fields[name]) for name in
                      ("triples", "tau_steps", "doubles", "adds")}
            assert counts == row["counts"]
            score = (10 * counts["triples"] + 6 * counts["tau_steps"] +
                     8 * counts["doubles"] + 16 * counts["adds"])
            assert score == row["weighted_group_score"]
            assert fields["online_ms"] == row["online_ms_exploratory"]
        pair = receipt["pairs"][case_index]
        assert pair["case_id"] == case["id"] and pair["verified"]
        assert pair["operation_gate_pass"]
        assert pair["unit_score"] == arms[UNIT]["weighted_group_score"]
        assert pair["full_score"] == arms[FULL]["weighted_group_score"]
        assert pair["saved_score"] == pair["unit_score"] - pair["full_score"] > 0
    print("PASS: eight frozen pairs, 16 verified raw arms, all eight strict operation gains")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bench", type=Path, help="optional exact panel executable")
    args = parser.parse_args()
    audit(args.bench)

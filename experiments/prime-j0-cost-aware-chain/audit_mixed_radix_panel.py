#!/usr/bin/env python3
"""Read-only audit of the frozen mixed-radix held-out operation panel."""

import argparse
import hashlib
import json
from pathlib import Path

from make_inputs import read_fields


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
CANONICAL = "tail-pair-periodic-canonical"
FIRSTWORD = "tail-pair-periodic-firstword27"
MIXED = "tail-pair-mixed-radix"
ARMS = (CANONICAL, FIRSTWORD, MIXED)
STATIC_BYTES = {CANONICAL: "68029", FIRSTWORD: "68157", MIXED: "99853"}
FIXTURE_SHA256 = "adf881607a1cb3cc8b50a92b6b54265aabe8a4bc6ff9614281f2b8f8decb593f"


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(bench):
    receipt = json.loads((ROOT / "mixed-radix-native-panel.json").read_text())
    fixture_path = ROOT / "mixed-radix-inputs.json"
    fixture = json.loads(fixture_path.read_text())
    assert sha256(fixture_path) == receipt["fixture_sha256"] == FIXTURE_SHA256
    assert receipt["schema"] == 1 and receipt["status"] == "native_operation_gate_pass"
    assert receipt["cpu_timing_claim"] is None and receipt["isolated_receipt"] is None
    assert len(fixture["cases"]) == 8 and len(receipt["rows"]) == 24
    assert len(receipt["pairs"]) == 8
    if bench is not None:
        assert sha256(bench) == receipt["bench_sha256"]
    assert sha256(REPO / "build-cost-aware/CMakeCache.txt") == receipt["build_cache_sha256"]
    for name, digest in receipt["source_sha256"].items():
        assert sha256(REPO / name) == digest, name
    for case_index, case in enumerate(fixture["cases"]):
        scalar_path = ROOT / case["scalar_file"]
        assert sha256(scalar_path) == case["scalar_file_sha256"]
        group = receipt["rows"][3 * case_index:3 * case_index + 3]
        order = ARMS[case_index % 3:] + ARMS[:case_index % 3]
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
                                  ("prep_bytes", "24336"),
                                  ("point_table_bytes", "23232"),
                                  ("static_map_bytes", STATIC_BYTES[arm]),
                                  ("rotations", "0"), ("verified", "1")):
                assert fields.get(key) == expected, (case["id"], arm, key)
            check_name = "mixed_checks" if arm == MIXED else "periodic_checks"
            assert fields.get(check_name) == "4096"
            if arm == MIXED:
                assert fields["mixed_fallbacks"] == "0"
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
        assert pair["canonical_score"] == arms[CANONICAL]["weighted_group_score"]
        assert pair["firstword_score"] == arms[FIRSTWORD]["weighted_group_score"]
        assert pair["mixed_score"] == arms[MIXED]["weighted_group_score"]
        assert pair["saved_vs_canonical"] == pair["canonical_score"] - pair["mixed_score"] > 0
        assert pair["saved_vs_firstword"] == pair["firstword_score"] - pair["mixed_score"] > 0
    print("PASS: eight frozen cases, 24 verified raw arms, all eight strict gains over both comparators")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bench", type=Path, help="optional exact panel executable")
    args = parser.parse_args()
    audit(args.bench)

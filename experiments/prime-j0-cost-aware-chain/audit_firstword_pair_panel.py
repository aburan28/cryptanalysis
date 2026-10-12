#!/usr/bin/env python3
"""Read-only audit of the frozen first-word held-out paired operation panel."""

import argparse
import hashlib
import json
from pathlib import Path

from make_inputs import read_fields


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
REFERENCE = "tail-pair-periodic-canonical"
CANDIDATE = "tail-pair-periodic-firstword27"
FIXTURE_SHA256 = "d144189c6b53317c9380515baecb3ea3aec41fc00d8b82b367dba808eb0eaaf5"


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(bench):
    receipt = json.loads((ROOT / "firstword-pair-native-panel.json").read_text())
    fixture_path = ROOT / "firstword-pair-inputs.json"
    fixture = json.loads(fixture_path.read_text())
    assert sha256(fixture_path) == receipt["fixture_sha256"] == FIXTURE_SHA256
    assert receipt["schema"] == 1 and receipt["status"] == "native_operation_gate_pass"
    assert receipt["cpu_timing_claim"] is None and receipt["isolated_receipt"] is None
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
        order = (REFERENCE, CANDIDATE) if case_index % 2 == 0 else (CANDIDATE, REFERENCE)
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
                                  ("periodic_checks", "4096"),
                                  ("prep_bytes", "24336"),
                                  ("point_table_bytes", "23232"),
                                  ("static_map_bytes", "68157" if arm == CANDIDATE else "68029"),
                                  ("rotations", "0"), ("verified", "1")):
                assert fields.get(key) == expected, (case["id"], arm, key)
            for key in ("triples", "adds", "periodic_lookups", "periodic_accepted",
                        "periodic_fallbacks"):
                assert int(fields[key]) == row[key], (case["id"], arm, key)
            assert fields["online_ms"] == row["online_ms_exploratory"]
            assert 10 * row["triples"] + 16 * row["adds"] == row["weighted_group_score"]
            if arm == REFERENCE:
                assert row["periodic_lookups"] == row["periodic_accepted"] == 0
            else:
                assert row["periodic_fallbacks"] == 0
        pair = receipt["pairs"][case_index]
        reference, candidate = arms[REFERENCE], arms[CANDIDATE]
        assert pair["case_id"] == case["id"] and pair["verified"]
        assert pair["operation_gate_pass"]
        assert pair["reference_score"] == reference["weighted_group_score"]
        assert pair["candidate_score"] == candidate["weighted_group_score"]
        assert pair["saved_score"] == pair["reference_score"] - pair["candidate_score"] > 0
    print("PASS: eight frozen pairs, 16 verified raw arms, all eight strict operation gains")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bench", type=Path, help="optional exact panel executable")
    args = parser.parse_args()
    audit(args.bench)

#!/usr/bin/env python3
"""Read-only audit of the frozen periodic-pair native operation panel."""

import argparse
import hashlib
import json
from pathlib import Path

from make_inputs import read_fields


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
REFERENCE = "tail-pair-periodic-canonical"
CANDIDATE = "tail-pair-periodic-gated27"


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(bench=None, build_cache=None):
    fixture_path = ROOT / "periodic-pair-native-inputs.json"
    panel_path = ROOT / "periodic-pair-native-panel.json"
    fixture = json.loads(fixture_path.read_text())
    panel = json.loads(panel_path.read_text())
    assert fixture["status"] == "frozen_periodic_pair_native_disjoint_fixture"
    assert len(fixture["cases"]) == 8
    assert panel["fixture_sha256"] == sha256(fixture_path)
    assert panel["cpu_timing_claim"] is None and panel["isolated_receipt"] is None
    assert panel["protocol_freeze_commit"] == "e4178e1e02393ae33bd01b98af2243cb011c17cb"
    assert panel["schema"] == 1 and panel["timeout_seconds_per_arm"] == 120
    if bench is not None:
        assert sha256(bench) == panel["bench_sha256"]
    if build_cache is not None:
        assert sha256(build_cache) == panel["build_cache_sha256"]
    for name, digest in panel["source_sha256"].items():
        assert sha256(REPO / name) == digest, name
    assert len(panel["rows"]) == 16 and len(panel["pairs"]) == 8
    assert len({(row["case_id"], row["arm"]) for row in panel["rows"]}) == 16
    assert {pair["case_id"] for pair in panel["pairs"]} == \
        {case["id"] for case in fixture["cases"]}
    for case_index, case in enumerate(fixture["cases"]):
        assert sha256(ROOT / case["scalar_file"]) == case["scalar_file_sha256"]
        expected_order = (REFERENCE, CANDIDATE) if case_index % 2 == 0 else \
            (CANDIDATE, REFERENCE)
        rows = sorted((row for row in panel["rows"] if row["case_id"] == case["id"]),
                      key=lambda row: row["case_run_position"])
        assert [row["arm"] for row in rows] == list(expected_order)
        scores = {}
        for row in rows:
            assert row["curve"] == case["curve"]["name"]
            assert row["point_index"] == case["point_index"]
            recorded_bench = Path(row["command"][0])
            assert recorded_bench.is_absolute()
            assert recorded_bench.parts[-2:] == ("build-cost-aware", "ca_tau_chain_bench")
            recorded_root = recorded_bench.parent.parent / \
                "experiments/prime-j0-cost-aware-chain"
            assert row["command"] == [str(recorded_bench),
                                      row["arm"], case["curve"]["name"],
                                      str(case["point_index"]),
                                      str(recorded_root / case["scalar_file"])]
            assert row["status"] == "exited" and row["returncode"] == 0
            assert row["verified"] and not row["failures"] and not row["stderr"]
            fields = read_fields(row["stdout"])
            for key, value in (("curve", case["curve"]["name"]),
                               ("point_index", str(case["point_index"])),
                               ("count", "4096"),
                               ("input_digest", case["input_digest"]),
                               ("output_digest", case["expected_output_digest"]),
                               ("point_entries", "726"),
                               ("tail_complete_preparation_checks", "726"),
                               ("periodic_checks", "4096"),
                               ("prep_adds", "103"),
                               ("prep_rotations", "390"),
                               ("prep_layer_inversions", "2"),
                               ("rotations", "0"), ("verified", "1")):
                assert fields[key] == value, (case["id"], row["arm"], key)
            assert fields["prep_bytes"] == "24336"
            assert fields["point_table_bytes"] == "23232"
            assert fields["static_map_bytes"] == "68029"
            assert fields["online_scratch_bytes"] == "1024"
            assert fields["online_ms"] == row["online_ms_exploratory"]
            score = 10 * int(fields["triples"]) + 16 * int(fields["adds"])
            assert score == row["weighted_group_score"]
            assert int(fields["triples"]) == row["triples"]
            assert int(fields["adds"]) == row["adds"]
            assert int(fields["periodic_lookups"]) == row["periodic_lookups"]
            assert int(fields["periodic_accepted"]) == row["periodic_accepted"]
            assert int(fields["periodic_fallbacks"]) == row["periodic_fallbacks"]
            scores[row["arm"]] = score
        pair = next(pair for pair in panel["pairs"] if pair["case_id"] == case["id"])
        assert pair["verified"] and pair["operation_gate_pass"]
        assert pair["reference_score"] == scores[REFERENCE]
        assert pair["candidate_score"] == scores[CANDIDATE]
        assert pair["saved_score"] == scores[REFERENCE] - scores[CANDIDATE]
        assert pair["saved_score"] > 0
    assert panel["status"] == "native_operation_gate_pass"
    print("PASS: eight frozen pairs, all raw outputs and setup checks, strict operation gain")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bench", type=Path, help="optional exact panel executable")
    parser.add_argument("--build-cache", type=Path, help="optional exact CMake cache")
    args = parser.parse_args()
    audit(args.bench, args.build_cache)

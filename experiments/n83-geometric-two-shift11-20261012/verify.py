#!/usr/bin/env python3
"""Audit the frozen N83 width-11 two-coordinate shift screen."""

import hashlib
import itertools
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    protocol_path = HERE / "protocol.json"
    result_path = HERE / "screen.json"
    protocol = json.loads(protocol_path.read_text())
    result = json.loads(result_path.read_text())
    assert result["status"] == "complete_geometry_screen"
    assert result["candidate_id"] is None
    assert result["protocol_sha256"] == sha(protocol_path)
    assert result["runtime_info_sha256"] == sha(HERE / "sage_runtime_info.json")
    assert json.loads((HERE / "sage_runtime_info.json").read_text())["status"] == "verified"
    for relative, digest in protocol["source_sha256"].items():
        assert sha(ROOT / relative) == digest, relative
    assert sha(ROOT / protocol["prior_census_file"]) == protocol[
        "prior_census_sha256"]
    assert sha(ROOT / protocol["prior_key_file"]) == protocol[
        "prior_key_sha256"]
    prior = json.loads((ROOT / protocol["prior_census_file"]).read_text())
    assert prior["best_K"] == protocol["baseline_K"] == result["baseline_K"] == 1096
    pairs = list(itertools.combinations(range(11, 83), 2))
    rows = result["rows"]
    assert len(rows) == len(pairs) == 2556
    progress = (HERE / "screen.progress.jsonl").read_text().splitlines()
    assert len(progress) == 2556
    for pair, row, line in zip(pairs, rows, progress):
        assert row["shift_coordinates"] == list(pair)
        assert 0 <= row["valid_lifts"] <= 2048
        assert json.loads(line) == row
    top = sorted(rows, key=lambda row: row["valid_lifts"], reverse=True)
    assert (top[0]["shift_coordinates"], top[0]["valid_lifts"]) == ([26, 38], 1109)
    assert top[1]["valid_lifts"] == 1094
    competitive = result["competitive_full_scans"]
    assert len(competitive) == 1
    winner = competitive[0]
    assert winner["shift_coordinates"] == [26, 38]
    assert (winner["valid_lifts"], winner["identity_projections"],
            winner["duplicate_orbit_seeds"], winner["K"], winner["B"]) == (
                1109, 0, 0, 1109, 184094)
    assert (result["best_shift_coordinates"], result["best_K"],
            result["best_B"]) == ([26, 38], 1109, 184094)
    key_path = HERE / result["best_key_file"]
    assert key_path.stat().st_size == 21 * 1109
    assert sha(key_path) == result["best_key_sha256"]
    assert not (HERE / "screen.stderr.txt").read_text().strip()
    assert result["ordinary_query_relation_yield"] is None
    assert result["novel_rank_per_query"] is None
    assert result["one_target_online_ms"] is None
    sage = json.loads((HERE / "independent_sage_replay.json").read_text())
    assert sage["status"] == "PASS"
    assert sage["protocol_sha256"] == sha(protocol_path)
    assert sage["screen_sha256"] == sha(result_path)
    assert sage["verifier_source_sha256"] == sha(HERE / "verify_sage.py")
    assert sage["all_2556_lift_counts"] == "PASS"
    assert sage["winner_full_subgroup_orbit_and_key_replay"] == "PASS"
    assert (sage["winner_shift_coordinates"], sage["winner_K"],
            sage["winner_B"]) == ([26, 38], 1109, 184094)
    assert (HERE / "lean-toolchain").read_text().strip() == "leanprover/lean4:v4.34.1"
    lean = (HERE / "lean-build.txt").read_text()
    assert "error:" not in lean
    assert "N83TwoShift.losing_shift_below_winner" in lean
    assert "does not depend on any axioms" in lean
    print(json.dumps({"status": "PASS", "best_shift_coordinates": [26, 38],
                      "best_K": 1109, "best_B": 184094,
                      "baseline_K": 1096}, sort_keys=True))


if __name__ == "__main__":
    main()

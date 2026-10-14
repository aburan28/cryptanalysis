#!/usr/bin/env python3
"""Audit the frozen N83 width-12 two-coordinate shift screen."""

import hashlib
import itertools
import json
from math import comb
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
    assert sha(ROOT / protocol["prior_protocol_file"]) == protocol[
        "prior_protocol_sha256"]
    assert sha(ROOT / protocol["prior_key_file"]) == protocol[
        "prior_key_sha256"]
    prior = json.loads((ROOT / protocol["prior_protocol_file"]).read_text())
    prior_row = next(row for row in prior["base_rows"] if row["dimension"] == 12)
    assert prior_row["K"] == protocol["baseline_K"] == result["baseline_K"] == 2130
    assert prior_row["B"] == protocol["baseline_B"] == 353580
    pairs = list(itertools.combinations(range(12, 83), 2))
    rows = result["rows"]
    assert len(rows) == len(pairs) == 2485
    progress = (HERE / "screen.progress.jsonl").read_text().splitlines()
    assert len(progress) == 2485
    for pair, row, line in zip(pairs, rows, progress):
        assert row["shift_coordinates"] == list(pair)
        assert 0 <= row["valid_lifts"] <= 4096
        assert json.loads(line) == row
    top = sorted(rows, key=lambda row: row["valid_lifts"], reverse=True)
    assert (top[0]["shift_coordinates"], top[0]["valid_lifts"]) == ([37, 73], 2196)
    assert top[1]["valid_lifts"] == 2156
    competitive = result["competitive_full_scans"]
    assert len(competitive) == 1
    winner = competitive[0]
    assert winner["shift_coordinates"] == [37, 73]
    assert (winner["valid_lifts"], winner["identity_projections"],
            winner["duplicate_orbit_seeds"], winner["K"], winner["B"]) == (
                2196, 0, 0, 2196, 364536)
    assert (result["best_shift_coordinates"], result["best_K"],
            result["best_B"]) == ([37, 73], 2196, 364536)
    assert result["best_full_scan"] == {
        key: winner[key] for key in ("valid_lifts", "identity_projections",
                                     "duplicate_orbit_seeds", "K", "B")}
    key_path = HERE / result["best_key_file"]
    assert key_path.stat().st_size == 21 * 2196
    assert sha(key_path) == result["best_key_sha256"]
    assert result["ordinary_query_relation_yield"] is None
    assert result["novel_rank_per_query"] is None
    assert result["one_target_online_ms"] is None
    sage = json.loads((HERE / "independent_sage_replay.json").read_text())
    assert sage["status"] == "PASS"
    assert sage["protocol_sha256"] == sha(protocol_path)
    assert sage["screen_sha256"] == sha(result_path)
    assert sage["verifier_source_sha256"] == sha(HERE / "verify_sage.py")
    assert sage["all_2485_lift_counts"] == "PASS"
    assert sage["winner_full_subgroup_orbit_and_key_replay"] == "PASS"
    assert (sage["winner_shift_coordinates"], sage["winner_K"],
            sage["winner_B"]) == ([37, 73], 2196, 364536)
    assert (HERE / "lean-toolchain").read_text().strip() == "leanprover/lean4:v4.34.1"
    lean = (HERE / "lean-build.txt").read_text()
    assert "error:" not in lean
    assert "N83Width12TwoShift.losing_shift_below_winner" in lean
    assert "N83Width12TwoShift.other_coset_pair_below_winner" in lean
    assert lean.count("does not depend on any axioms") == 2
    union_protocol_path = HERE / "union_protocol.json"
    union_path = HERE / "union.json"
    union_protocol = json.loads(union_protocol_path.read_text())
    union = json.loads(union_path.read_text())
    assert union_protocol["screen_sha256"] == sha(result_path)
    assert union_protocol["screen_source_sha256"] == sha(HERE / "screen.py")
    assert union_protocol["source_sha256"] == sha(HERE / "union.py")
    assert union["status"] == "complete_geometry"
    assert union["protocol_sha256"] == sha(union_protocol_path)
    assert union["source_sha256"] == sha(HERE / "union.py")
    assert union["screen_sha256"] == sha(result_path)
    assert union["best_K"] == 4349 and union["best_B"] == 721934
    assert union["best_B"] == 166 * union["best_K"]
    assert union["intersection_K"] == 2
    assert [row["shift_coordinates"] for row in union["components"]] == [[37, 73], [12, 51]]
    assert [(row["valid_lifts"], row["K"], row["duplicate_orbit_seeds"])
            for row in union["components"]] == [(2196, 2196, 0), (2156, 2155, 1)]
    assert union["best_K"] == sum(row["K"] for row in union["components"]) - 2
    assert union["upper_bound_K_all_pairs"] == 4352
    assert top[0]["valid_lifts"] + top[2]["valid_lifts"] == 4346 < union["best_K"]
    assert union["evaluated_pairs"] == 1 and union["full_scanned_offsets"] == 2
    assert union["all_pair_optimum_certified"]
    assert sha(HERE / union["key_file"]) == union["key_sha256"]
    assert (HERE / union["key_file"]).stat().st_size == 21 * union["best_K"]
    assert sha(HERE / "union_attempt1.py") == json.loads(
        (HERE / "union_attempt1_protocol.json").read_text())["source_sha256"]
    assert "AssertionError" in (HERE / "union_attempt1.stderr.txt").read_text()
    interrupted = json.loads((HERE / "interrupted_verification.json").read_text())
    assert interrupted["status"] == "interrupted_for_exact_lift_optimization"
    for role in ("screen_verifier", "union_verifier"):
        item = interrupted[role]
        assert sha(HERE / item["source_file"]) == item["source_sha256"]
    union_sage = json.loads((HERE / "independent_union_sage_replay.json").read_text())
    assert union_sage["status"] == "PASS"
    assert union_sage["protocol_sha256"] == sha(union_protocol_path)
    assert union_sage["union_sha256"] == sha(union_path)
    assert union_sage["verifier_source_sha256"] == sha(HERE / "verify_union_sage.py")
    assert union_sage["best_K"] == union["best_K"]
    assert union_sage["best_B"] == union["best_B"]
    assert union_sage["intersection_K"] == union["intersection_K"]
    basis = json.loads((HERE / "basis_manifest.json").read_text())
    a, b = basis["coset_offsets_onb_coordinates"]
    vectors = basis["basis_onb_coordinates"]
    assert basis["affine_offset_onb_coordinates"] == a
    assert vectors == [1 << i for i in range(12)] + [a ^ b]
    assert basis["dimension"] == len(vectors) == 13
    assert len({a ^ seed ^ (choice * (a ^ b)) for seed in range(4096)
                for choice in (0, 1)}) == 8192
    assert basis["effective_columns_K"] == union["best_K"]
    assert basis["actual_subgroup_points_B"] == union["best_B"]
    assert basis["factor_base_key_sha256"] == union["key_sha256"]
    assert basis["union_receipt_sha256"] == sha(union_path)
    frontier = json.loads((ROOT / "experiments/koblitz-n83-index-design-20260929/"
                            "Q20261012_N83_WIDTH_FRONTIER/frontier.json").read_text())
    prior13 = max((row for row in frontier["rows"] if row["dimension"] == 13),
                  key=lambda row: row["folded_columns_K"])
    assert prior13["folded_columns_K"] == 4125
    assert prior13["actual_usable_points_B_before_folding"] == 684750
    assert comb(union["best_B"], 5) > comb(prior13["actual_usable_points_B_before_folding"], 5)
    print(json.dumps({"status": "PASS", "best_single_K": 2196,
                      "best_union_K": 4349, "best_union_B": 721934,
                      "prior_width13_K": 4125}, sort_keys=True))


if __name__ == "__main__":
    main()

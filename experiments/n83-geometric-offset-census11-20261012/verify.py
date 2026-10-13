#!/usr/bin/env python3
"""Audit the frozen N83 width-11 one-coordinate shift census."""

import hashlib
import json
import math
from decimal import Decimal, localcontext
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    protocol_path = HERE / "protocol.json"
    census_path = HERE / "census.json"
    protocol = json.loads(protocol_path.read_text())
    census = json.loads(census_path.read_text())
    assert census["status"] == "complete_geometry_stage"
    assert census["candidate_id"] is None
    assert census["protocol_sha256"] == sha(protocol_path)
    assert census["runtime_info_sha256"] == sha(HERE / "sage_runtime_info.json")
    assert json.loads((HERE / "sage_runtime_info.json").read_text())["status"] == "verified"
    for relative, digest in protocol["source_sha256"].items():
        assert sha(ROOT / relative) == digest, relative
    prior_path = ROOT / protocol["frontier_file"]
    assert sha(prior_path) == protocol["frontier_sha256"]
    assert len(census["rows"]) == len(protocol["offset_coordinates"]) == 73
    assert [row["shift_coordinate"] for row in census["rows"]] == protocol["offset_coordinates"]
    for row in census["rows"]:
        assert row["offset_onb_coordinates"] == (
            0 if row["shift_coordinate"] is None else 1 << row["shift_coordinate"])
        assert row["valid_lifts"] + row["invalid_or_zero_lifts"] == 2048
        assert row["valid_lifts"] - row["identity_projections"] - row[
            "duplicate_orbit_seeds"] == row["folded_columns_K"]
        assert row["actual_usable_points_B_before_folding"] == 166 * row[
            "folded_columns_K"]
    rows = census["rows"]
    winner = max(rows, key=lambda row: row["folded_columns_K"])
    baseline = next(row for row in rows if row["shift_coordinate"] == 81)
    previous = next(row for row in json.loads(prior_path.read_text())["rows"]
                    if row["dimension"] == 11 and row[
                        "offset_onb_coordinates"] == 1 << 81)
    assert (baseline["folded_columns_K"], baseline["valid_lifts"],
            baseline["duplicate_orbit_seeds"]) == (
                previous["folded_columns_K"], previous["valid_lifts"],
                previous["duplicate_orbit_seeds"])
    assert census["best_shift_coordinate"] == winner["shift_coordinate"]
    assert census["best_K"] == winner["folded_columns_K"]
    assert census["best_B"] == winner["actual_usable_points_B_before_folding"]
    assert max(row["valid_lifts"] for row in rows if row is not winner) == 1066
    assert winner["folded_columns_K"] > 1066
    assert census["baseline_shift_coordinate"] == 81
    assert census["baseline_K"] == baseline["folded_columns_K"]
    assert census["baseline_B"] == baseline[
        "actual_usable_points_B_before_folding"]
    with localcontext() as ctx:
        ctx.prec = 50
        moment = str(Decimal(math.comb(census["best_B"], 6)) /
                     Decimal(protocol["subgroup_order"]))
    assert census["best_six_subset_uniform_target_first_moment"] == moment
    key_path = HERE / census["best_key_file"]
    assert key_path.stat().st_size == 21 * census["best_K"]
    assert sha(key_path) == census["best_key_sha256"]
    stdout = (HERE / "run.stdout.txt").read_text().splitlines()
    assert len(stdout) == len(rows)
    for line, row in zip(stdout, rows):
        progress = json.loads(line)
        assert progress == {"shift_coordinate": row["shift_coordinate"],
                            "K": row["folded_columns_K"],
                            "valid": row["valid_lifts"]}
    assert not (HERE / "run.stderr.txt").read_text().strip()
    replay = json.loads((HERE / "independent_sage_replay.json").read_text())
    assert replay["status"] == "PASS"
    assert replay["protocol_sha256"] == sha(protocol_path)
    assert replay["census_sha256"] == sha(census_path)
    assert replay["verifier_source_sha256"] == sha(HERE / "verify_sage.py")
    assert replay["all_shift_lift_counts"] == "PASS"
    assert replay["winner_full_subgroup_orbit_and_key_replay"] == "PASS"
    assert replay["winner_shift_coordinate"] == winner["shift_coordinate"]
    assert replay["winner_K"] == census["best_K"]
    assert replay["winner_B"] == census["best_B"]
    assert (HERE / "lean-toolchain").read_text().strip() == "leanprover/lean4:v4.34.1"
    lean = (HERE / "lean-build.txt").read_text()
    assert "error:" not in lean
    assert "N83Width11Coset.xor_translate_surjective" in lean
    assert "[propext, Quot.sound]" in lean
    assert (HERE / "preflight_failed.stderr.txt").is_file()
    assert (HERE / "cancelled_bad_baseline.stdout.txt").is_file()
    print(json.dumps({"status": "PASS", "best_shift_coordinate": census[
        "best_shift_coordinate"], "best_K": census["best_K"], "best_B":
        census["best_B"], "baseline_K": census["baseline_K"]}, sort_keys=True))


if __name__ == "__main__":
    main()

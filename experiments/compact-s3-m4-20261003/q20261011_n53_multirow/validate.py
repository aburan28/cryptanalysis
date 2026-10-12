#!/usr/bin/env python3
"""Validate Q1448's frozen inputs, measured charge, and independent replay."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    from run import frozen_inputs

    protocol = json.loads((HERE / "protocol.json").read_text())
    freeze = json.loads((HERE / "freeze.json").read_text())
    measured = json.loads((HERE / "measurement.json").read_text())
    replay = json.loads((HERE / "independent_replay.json").read_text())
    analysis = json.loads((HERE / "analysis.json").read_text())
    reference = json.loads((PARENT / "runs/n53_ordinary_matched_pair_table.json").read_text())
    assert freeze == frozen_inputs()
    assert measured["freeze_sha256"] == sha(HERE / "freeze.json")
    assert measured["source_sha256"] == sha(HERE / "run.py")
    assert replay["source_sha256"] == sha(HERE / "verify.py")
    assert replay["measurement_sha256"] == analysis["measurement_sha256"] == sha(
        HERE / "measurement.json")
    assert analysis["independent_replay_sha256"] == sha(HERE / "independent_replay.json")
    assert analysis["source_sha256"] == sha(HERE / "summarize.py")
    assert measured["curve_id"] == replay["curve_id"] == protocol["curve_id"]
    assert measured["workload_id"] == replay["workload_id"] == protocol["workload_id"]
    assert measured["factor_base_enumerated_set_sha256"] == replay[
        "base_key_packed_sha256"] == protocol["factor_base_enumerated_set_sha256"]
    assert measured["candidate_id"] is measured["run_id"] is None
    assert measured["status"] == "completed_query_cap"
    assert measured["query_samples_processed"] == protocol[
        "point_decomposition"]["query_sample_cap"]
    assert measured["first_only_reference_query"] == reference[
        "ordinary_query"]["query_samples"] == 171218
    assert measured["relations"][0]["relation"] == reference[
        "ordinary_query"]["relation"]
    assert [row["query_number"] for row in measured["relations"]] == [
        171218, 555285, 1042474]
    assert measured["verified_relation_occurrences"] == replay[
        "verified_relation_occurrences"] == 3
    assert measured["augmented_rank"] == replay["independent_augmented_rank"] == 3
    assert measured["same_target_homogeneous_difference_rank"] == replay[
        "same_target_homogeneous_difference_rank"] == 2
    assert all(row["novel_augmented_rank"] for row in measured["relations"])
    assert measured["query_matched_key_positions"] == 3
    assert measured["candidate_table_descriptors_checked"] == 3
    assert measured["proper_rejections"] == 0
    phases = measured["phase_wall_ns"]
    assert sum(phases.values()) == analysis["cold_stage_wall_ns"]
    assert phases["target_query_and_lookup"] + phases[
        "relation_verification_and_rank"] == analysis[
            "target_dependent_query_and_replay_wall_ns"]
    assert analysis["charged_target_pair_add_attempts"] == 1500000
    assert analysis["charged_target_complement_add_attempts"] == 1499940
    assert analysis["cumulative_same_point_pair_lane_table_samples"] == 1000000
    assert analysis["cumulative_same_point_pair_lane_query_samples"] == 1671218
    assert analysis["complete_solve_work_log2"] is None
    assert analysis["degree131_challenge_gap_bits"] is None
    print("PASS Q1448 frozen N53 multirow relation and rank accounting")


if __name__ == "__main__":
    main()

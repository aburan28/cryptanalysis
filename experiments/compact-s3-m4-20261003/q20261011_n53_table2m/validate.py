#!/usr/bin/env python3
"""Validate frozen Q1451 work and independent full-point rank replay."""

import json
from pathlib import Path

from run import (FREEZE, HERE, OUT, PREVIOUS, PROTOCOL, REFERENCE,
                 frozen_inputs, sha)


def main():
    freeze = json.loads(FREEZE.read_text())
    protocol = json.loads(PROTOCOL.read_text())
    result = json.loads(OUT.read_text())
    replay = json.loads((HERE / "independent_replay.json").read_text())
    analysis = json.loads((HERE / "analysis.json").read_text())
    previous = json.loads(PREVIOUS.read_text())
    reference = json.loads(REFERENCE.read_text())
    assert freeze == frozen_inputs()
    assert result["freeze_sha256"] == sha(FREEZE)
    assert result["source_sha256"] == sha(HERE / "run.py")
    assert result["proposal_id"] == replay["proposal_id"] == "Q1451"
    assert result["candidate_id"] is result["run_id"] is None
    assert result["isogeny"] == replay["isogeny"] == "none"
    assert result["curve_id"] == protocol["curve_id"] == replay["curve_id"]
    assert result["workload_id"] == protocol["workload_id"] == replay["workload_id"]
    for key in ("factor_base_actual_B", "factor_base_folded_columns_K",
                "factor_base_enumerated_set_sha256"):
        assert result[key] == protocol[key] == replay[key]
    assert result["table_samples"] == protocol["point_decomposition"][
        "table_samples"]
    assert result["table_distinct_keys"] + result["table_same_key_repeats"] + (
        result["table_skipped_identity_pairs"]) == result["table_samples"]
    assert 0 < result["query_samples_processed"] <= protocol[
        "point_decomposition"]["query_sample_cap"]
    assert result["query_matched_key_positions"] <= result[
        "query_samples_processed"]
    assert result["verified_relation_occurrences"] == len(result["relations"])
    assert result["verified_relation_occurrences"] == replay[
        "verified_relation_occurrences"]
    assert result["augmented_rank"] == replay["independent_augmented_rank"]
    assert result["same_target_homogeneous_difference_rank"] == replay[
        "same_target_homogeneous_difference_rank"]
    assert result["queries_with_multiple_verified_relations"] == replay[
        "queries_with_multiple_verified_relations"]
    assert result["maximum_verified_relations_per_query"] == replay[
        "maximum_verified_relations_per_query"]
    assert replay["measurement_sha256"] == sha(OUT)
    assert replay["status"] == "PASS"
    assert analysis["measurement_sha256"] == sha(OUT)
    assert analysis["independent_replay_sha256"] == sha(
        HERE / "independent_replay.json")
    assert analysis["source_sha256"] == sha(HERE / "summarize.py")
    assert analysis["novel_augmented_rows"] == result["augmented_rank"]
    assert analysis["distinct_point_multisets"] == result[
        "distinct_point_multisets"]
    assert analysis["queries_with_multiple_distinct_rows"] == 0
    assert analysis["max_distinct_rows_per_query"] == 1
    assert analysis["max_novel_rows_per_query"] == 1
    assert sum(row["verified_occurrences"] for row in analysis[
        "per_matching_query"]) == result["verified_relation_occurrences"]
    assert result["prior_same_point_q1448_table_samples"] == previous[
        "table_samples"]
    assert result["prior_same_point_q1448_query_samples"] == previous[
        "query_samples_processed"]
    assert result["cumulative_same_point_pair_lane_table_samples"] == (
        reference["table_samples"] + previous["table_samples"] +
        result["table_samples"])
    assert result["cumulative_same_point_pair_lane_query_samples"] == (
        reference["ordinary_query"]["query_samples"] +
        previous["query_samples_processed"] + result["query_samples_processed"])
    phases = result["phase_wall_ns"]
    assert all(value >= 0 for value in phases.values())
    assert set(phases) == {"base_and_column_setup", "table_build",
                           "target_query_and_lookup",
                           "relation_verification_and_rank"}
    assert result["complete_solve_work_log2"] is None
    assert result["degree131_challenge_gap_bits"] is None
    print("Q1451 VALIDATED: frozen same-point work and independent rank replay")


if __name__ == "__main__":
    main()

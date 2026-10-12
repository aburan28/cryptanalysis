#!/usr/bin/env python3
"""Derive Q1451 unique-per-query, cost, and same-point comparison metrics."""

import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
MEASUREMENT = HERE / "measurement.json"
REPLAY = HERE / "independent_replay.json"
PREVIOUS = PARENT / "q20261011_n53_multirow/measurement.json"
OUT = HERE / "analysis.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def wilson(successes, trials):
    z = 1.959963984540054
    p = successes / trials
    denominator = 1 + z * z / trials
    center = (p + z * z / (2 * trials)) / denominator
    radius = z * math.sqrt(p * (1 - p) / trials +
                           z * z / (4 * trials * trials)) / denominator
    return [center - radius, center + radius]


def signature(record):
    return tuple(sorted(tuple(point) for point in record["relation"]["points"]))


def main():
    assert not OUT.exists()
    measured = json.loads(MEASUREMENT.read_text())
    replay = json.loads(REPLAY.read_text())
    previous = json.loads(PREVIOUS.read_text())
    assert replay["status"] == "PASS"
    assert replay["measurement_sha256"] == sha(MEASUREMENT)
    assert measured["augmented_rank"] == replay["independent_augmented_rank"]
    grouped = defaultdict(list)
    for record in measured["relations"]:
        grouped[record["query_number"]].append(record)
    per_query = []
    for query, records in sorted(grouped.items()):
        unique_points = {signature(record) for record in records}
        unique_rows = {tuple(tuple(entry) for entry in record["row"])
                       for record in records}
        novel = sum(bool(record["novel_augmented_rank"]) for record in records)
        per_query.append({"query_number": query,
                          "verified_occurrences": len(records),
                          "distinct_point_multisets": len(unique_points),
                          "distinct_quotient_rows": len(unique_rows),
                          "novel_augmented_rows": novel})
    assert len(per_query) == measured["query_matched_key_positions"]
    assert sum(row["verified_occurrences"] for row in per_query) == measured[
        "verified_relation_occurrences"]
    assert sum(row["novel_augmented_rows"] for row in per_query) == measured[
        "augmented_rank"]
    previous_relations = {signature(record) for record in previous["relations"]}
    new_relations = {signature(record) for record in measured["relations"]}
    assert previous_relations <= new_relations
    assert len(previous_relations) == previous["augmented_rank"]
    assert len(new_relations) == measured["augmented_rank"]
    phases = measured["phase_wall_ns"]
    total_ns = sum(phases.values())
    target_online_ns = (phases["target_query_and_lookup"] +
                        phases["relation_verification_and_rank"])
    novel = measured["augmented_rank"]
    pair_attempts = (measured["table_samples"] +
                     measured["query_samples_processed"] +
                     measured["query_samples_processed"] -
                     measured["query_skipped_identity_pairs"])
    previous_pair_attempts = (previous["table_samples"] +
                              previous["query_samples_processed"] +
                              previous["query_samples_processed"] -
                              previous["query_skipped_identity_pairs"])
    analysis = {
        "proposal_id": "Q1451", "candidate_id": None, "run_id": None,
        "curve_id": measured["curve_id"],
        "workload_id": measured["workload_id"], "isogeny": "none",
        "measurement_sha256": sha(MEASUREMENT),
        "independent_replay_sha256": sha(REPLAY),
        "previous_measurement_sha256": sha(PREVIOUS),
        "source_sha256": sha(Path(__file__)),
        "query_samples": measured["query_samples_processed"],
        "matched_query_positions": len(per_query),
        "verified_occurrences": measured["verified_relation_occurrences"],
        "distinct_point_multisets": len(new_relations),
        "novel_augmented_rows": novel,
        "new_distinct_rows_beyond_q1448": len(new_relations - previous_relations),
        "queries_with_multiple_occurrences": sum(
            row["verified_occurrences"] > 1 for row in per_query),
        "queries_with_multiple_distinct_rows": sum(
            row["distinct_quotient_rows"] > 1 for row in per_query),
        "max_distinct_rows_per_query": max(
            row["distinct_quotient_rows"] for row in per_query),
        "max_novel_rows_per_query": max(
            row["novel_augmented_rows"] for row in per_query),
        "per_matching_query": per_query,
        "conditional_matched_query_yield": len(per_query) /
            measured["query_samples_processed"],
        "conditional_matched_query_yield_wilson95": wilson(
            len(per_query), measured["query_samples_processed"]),
        "conditional_novel_rank_yield_per_query": novel /
            measured["query_samples_processed"],
        "rate_scope": "one frozen N53 public point, fixed table seed and size, uniform-with-replacement query pair schedule; not a cross-target or N131 rate",
        "charged_pair_add_attempts": pair_attempts,
        "charged_pair_add_attempts_per_novel_row": pair_attempts / novel,
        "previous_q1448_pair_add_attempts": previous_pair_attempts,
        "previous_q1448_pair_add_attempts_per_novel_row": (
            previous_pair_attempts / previous["augmented_rank"]),
        "pair_attempts_per_row_ratio_previous_over_new": (
            (previous_pair_attempts / previous["augmented_rank"]) /
            (pair_attempts / novel)),
        "target_dependent_query_and_inrun_check_ns": target_online_ns,
        "target_dependent_ns_per_novel_row": target_online_ns / novel,
        "cold_stage_ns": total_ns,
        "cold_stage_ns_per_novel_row": total_ns / novel,
        "phase_wall_ns": phases,
        "peak_rss_bytes": measured["peak_rss_bytes"],
        "cumulative_same_point_pair_lane_table_samples": measured[
            "cumulative_same_point_pair_lane_table_samples"],
        "cumulative_same_point_pair_lane_query_samples": measured[
            "cumulative_same_point_pair_lane_query_samples"],
        "complete_solve_work_log2": None,
        "degree131_challenge_gap_bits": None,
    }
    OUT.write_text(json.dumps(analysis, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"matched_queries": len(per_query),
                      "unique_rows": len(new_relations),
                      "multi_distinct_queries": analysis[
                          "queries_with_multiple_distinct_rows"],
                      "pair_attempts_per_novel_row": analysis[
                          "charged_pair_add_attempts_per_novel_row"]},
                     sort_keys=True))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Charge Q1448's one-point N53 relation and rank yield in named units."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
MEASUREMENT = HERE / "measurement.json"
REPLAY = HERE / "independent_replay.json"
OUT = HERE / "analysis.json"
Z = 1.959963984540054


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def wilson(hits: int, trials: int) -> list[float]:
    p = hits / trials
    z2 = Z * Z
    denominator = 1 + z2 / trials
    center = (p + z2 / (2 * trials)) / denominator
    radius = Z * math.sqrt(p * (1 - p) / trials + z2 / (4 * trials * trials)) / denominator
    return [max(0.0, center - radius), min(1.0, center + radius)]


def main() -> None:
    assert not OUT.exists()
    record = json.loads(MEASUREMENT.read_text())
    replay = json.loads(REPLAY.read_text())
    protocol = json.loads((HERE / "protocol.json").read_text())
    assert record["status"] == "completed_query_cap"
    assert replay["status"] == "PASS"
    assert record["curve_id"] == replay["curve_id"] == protocol["curve_id"]
    assert record["workload_id"] == replay["workload_id"] == protocol["workload_id"]
    assert record["verified_relation_occurrences"] == replay[
        "verified_relation_occurrences"] == 3
    assert record["augmented_rank"] == replay["independent_augmented_rank"] == 3
    phases = record["phase_wall_ns"]
    online = phases["target_query_and_lookup"] + phases[
        "relation_verification_and_rank"]
    cold = sum(phases.values())
    q = record["query_samples_processed"]
    novel = record["augmented_rank"]
    output = {
        "kind": "q1448_n53_one_target_pair_stage_cost_and_rank_analysis",
        "proposal_id": "Q1448", "candidate_id": None, "run_id": None,
        "curve_id": record["curve_id"], "workload_id": record["workload_id"],
        "isogeny": "none",
        "factor_base_actual_B": record["factor_base_actual_B"],
        "factor_base_folded_columns_K": record["factor_base_folded_columns_K"],
        "factor_base_enumerated_set_sha256": record[
            "factor_base_enumerated_set_sha256"],
        "measured_same_target_query_attempts": q,
        "verified_distinct_relations": record["distinct_point_multisets"],
        "novel_augmented_rows": novel,
        "same_target_homogeneous_difference_rank": record[
            "same_target_homogeneous_difference_rank"],
        "query_attempts_per_novel_augmented_row": q / novel,
        "conditional_verified_relation_yield_per_query": record[
            "verified_relation_occurrences"] / q,
        "conditional_relation_yield_wilson95": wilson(
            record["verified_relation_occurrences"], q),
        "conditional_novel_row_fraction_of_verified_relations": novel / record[
            "verified_relation_occurrences"],
        "conditional_novel_row_fraction_wilson95": wilson(
            novel, record["verified_relation_occurrences"]),
        "charged_table_pair_add_attempts": record["table_samples"],
        "charged_target_pair_add_attempts": q,
        "charged_target_complement_add_attempts": q - record[
            "query_skipped_identity_pairs"],
        "charged_table_pair_add_attempts_per_novel_row": record["table_samples"] / novel,
        "charged_target_pair_add_attempts_per_novel_row": q / novel,
        "charged_target_complement_add_attempts_per_novel_row": (
            q - record["query_skipped_identity_pairs"]) / novel,
        "target_dependent_query_and_replay_wall_ns": online,
        "target_dependent_wall_seconds_per_novel_row_exploratory": online / novel / 1e9,
        "cold_stage_wall_ns": cold,
        "cold_stage_wall_seconds_per_novel_row_exploratory": cold / novel / 1e9,
        "host_isolation": protocol["limits"]["host_isolation"],
        "cumulative_same_point_pair_lane_table_samples": record[
            "cumulative_same_point_pair_lane_table_samples"],
        "cumulative_same_point_pair_lane_query_samples": record[
            "cumulative_same_point_pair_lane_query_samples"],
        "distinct_same_point_rows_across_parent_and_current": novel,
        "additional_rows_beyond_q1301": novel - 1,
        "rate_scope": "conditional on this N53 public point, fixed 500000-sample table, and uniform-with-replacement target pair draws; Wilson interval is a sampling model, not a cross-target guarantee",
        "complete_solve_work_log2": None,
        "degree131_challenge_gap_bits": None,
        "measurement_sha256": sha(MEASUREMENT),
        "independent_replay_sha256": sha(REPLAY),
        "protocol_sha256": sha(HERE / "protocol.json"),
        "source_sha256": sha(Path(__file__)),
    }
    OUT.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
    print(f"PASS Q1448 {novel} novel rows / {q} query attempts")


if __name__ == "__main__":
    main()

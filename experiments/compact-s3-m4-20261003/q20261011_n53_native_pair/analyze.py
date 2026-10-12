#!/usr/bin/env python3
"""Derive named-unit Q1454 cap costs and conditional N131 distance."""
from __future__ import annotations
import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
OUT = HERE / "analysis.json"
PRIOR = PARENT / "q20261011_n53_table2m/measurement.json"
MODEL = PARENT / "q20261011_weight7_screen/measurement.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def wilson(k: int, n: int) -> list[float]:
    z = 1.959963984540054
    p = k / n
    denominator = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denominator
    half = z * math.sqrt((p * (1 - p) + z * z / (4 * n)) / n) / denominator
    return [center - half, center + half]


def main() -> None:
    assert not OUT.exists()
    measured = json.loads((HERE / "native_measurement.json").read_text())
    replay = json.loads((HERE / "independent_replay.json").read_text())
    previous = json.loads(PRIOR.read_text())
    model = json.loads(MODEL.read_text())
    assert measured["status"] == "completed_query_cap" and replay["status"] == "PASS"
    assert previous["curve_id"] == measured["curve_id"]
    assert previous["workload_id"] == measured["workload_id"]
    assert previous["factor_base_enumerated_set_sha256"] == measured[
        "factor_base_enumerated_set_sha256"]
    assert previous["query_samples_processed"] == measured["query_samples_processed"]
    assert previous["table_samples"] == measured["table_states_generated"]
    per_cap = {}
    query_count = measured["query_samples_processed"]
    for cap, verified in sorted(replay["cap_results"].items(), key=lambda item: int(item[0])):
        index = measured["prefix_table"][cap]
        counts = measured["cap_query"][cap]
        rank = verified["augmented_rank"]
        additions = (int(cap) + 2 * query_count -
                     measured["query_skipped_identity_pairs"])
        assert counts["candidate_descriptors"] == verified["candidate_matches"]
        assert rank == verified["distinct_quotient_rows"]
        per_cap[cap] = {
            "table_pair_add_attempts": int(cap),
            "table_distinct_keys": index["distinct_keys"],
            "table_key_fraction_per_attempt": index["distinct_keys"] / int(cap),
            "query_samples": query_count,
            "matched_query_positions": counts["matched_positions"],
            "verified_occurrences": verified["verified_relation_occurrences"],
            "distinct_rows": verified["distinct_quotient_rows"],
            "novel_augmented_rows": rank,
            "maximum_occurrences_per_query": verified["maximum_occurrences_per_query"],
            "charged_pair_add_attempts": additions,
            "pair_add_attempts_per_novel_row": additions / rank if rank else None,
            "log2_pair_add_attempts_per_novel_row": math.log2(additions / rank) if rank else None,
            "conditional_matched_query_yield": counts["matched_positions"] / query_count,
            "conditional_matched_query_yield_wilson95": wilson(
                counts["matched_positions"], query_count),
        }
    w7 = next(row for row in model["rows"] if row["weight_bound"] == 7)
    conditional_pair = w7["model"]["pure_pair_index_plus_K_rows_actions_model_log2"]
    previous_additions = (previous["table_samples"] + 2 * previous[
        "query_samples_processed"] - previous["query_skipped_identity_pairs"])
    previous_rank = previous["augmented_rank"]
    assert previous_additions == 4999940 and previous_rank == 11
    comparison = {
        "q1451_distinct_table_keys": previous["table_distinct_keys"],
        "q1451_novel_augmented_rows": previous_rank,
        "q1451_pair_add_attempts_per_novel_row": previous_additions / previous_rank,
        "q1454_distinct_table_keys": per_cap["2000000"]["table_distinct_keys"],
        "q1454_novel_augmented_rows": per_cap["2000000"]["novel_augmented_rows"],
        "q1454_pair_add_attempts_per_novel_row": per_cap["2000000"][
            "pair_add_attempts_per_novel_row"],
        "key_count_ratio": per_cap["2000000"]["table_distinct_keys"] /
                           previous["table_distinct_keys"],
        "rank_yield_ratio": per_cap["2000000"]["novel_augmented_rows"] /
                            previous_rank,
        "pair_add_efficiency_ratio": (previous_additions / previous_rank) /
                                      per_cap["2000000"]["pair_add_attempts_per_novel_row"],
        "measured_stage_rank_yield_gain_bits": math.log2(
            per_cap["2000000"]["novel_augmented_rows"] / previous_rank),
        "comparison_scope": "same frozen N53 point, base, query draws, two-million pair-add table budget; changed table schedule; native wall times exploratory on unisolated host",
    }
    output = {
        "proposal_id": "Q1454", "candidate_id": None, "run_id": None,
        "curve_id": measured["curve_id"], "workload_id": measured["workload_id"],
        "isogeny": "none", "factor_base_actual_B": measured["factor_base_actual_B"],
        "factor_base_folded_columns_K": measured["factor_base_folded_columns_K"],
        "factor_base_enumerated_set_sha256": measured[
            "factor_base_enumerated_set_sha256"],
        "measurement_sha256": sha(HERE / "native_measurement.json"),
        "independent_replay_sha256": sha(HERE / "independent_replay.json"),
        "previous_q1451_measurement_sha256": sha(PRIOR),
        "n131_conditional_model_sha256": sha(MODEL),
        "per_cap": per_cap, "same_input_comparison": comparison,
        "native_launcher_wall_seconds": measured["launcher_wall_ns"] / 1e9,
        "native_phase_wall_seconds": {name: value / 1e9 for name, value
                                      in measured["phase_wall_ns"].items()},
        "native_peak_rss_bytes": measured["peak_rss_bytes"],
        "n131_conditional_pure_pair_index_log2_logical_actions": conditional_pair,
        "n131_conditional_pure_pair_index_gap_above_2pow61_bits": conditional_pair - 61,
        "n131_index_build_states_log2": w7["model"]["pure_pair_index_states_log2"],
        "n131_model_note": "Q1447 already assumes efficient quotient-pair state enumeration; the N53 removal of repeated random table draws is not a justified reduction of its N131 exponent",
        "complete_solve_work_log2": None,
        "degree131_full_solve_challenge_gap_bits": None,
    }
    OUT.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
    print("ANALYZED", comparison["pair_add_efficiency_ratio"], "stage efficiency ratio")


if __name__ == "__main__":
    main()

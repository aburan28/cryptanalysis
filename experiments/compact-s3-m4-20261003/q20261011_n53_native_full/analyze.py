#!/usr/bin/env python3
"""Derive Q1455 complete-index work and comparisons in named units."""
from __future__ import annotations
import hashlib
import json
import math
from pathlib import Path
from freeze import Q1452, Q1454

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
OUT = HERE / "analysis.json"
Q1451 = PARENT / "q20261011_n53_table2m/measurement.json"
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
    previous = json.loads((Q1454 / "native_measurement.json").read_text())
    previous_replay = json.loads((Q1454 / "independent_replay.json").read_text())
    random_table = json.loads(Q1451.read_text())
    complete_python = json.loads((Q1452 / "measurement.json").read_text())
    model = json.loads(MODEL.read_text())
    assert measured["status"] == "completed_query_cap" and replay["status"] == "PASS"
    assert measured["table_distinct_keys"] == complete_python["table_distinct_keys"]
    assert measured["table_same_key_repeats"] == complete_python["table_same_key_repeats"]
    assert measured["table_skipped_identity_pairs"] == complete_python[
        "table_skipped_identity_pairs"]
    assert measured["cap_query"]["2000000"] == previous["cap_query"]["2000000"]
    assert measured["query_samples_processed"] == previous[
        "query_samples_processed"] == random_table["query_samples_processed"]
    per_cap = {}
    query_count = measured["query_samples_processed"]
    for cap, verified in sorted(replay["cap_results"].items(), key=lambda item: int(item[0])):
        index = measured["prefix_table"][cap]
        counts = measured["cap_query"][cap]
        rank = verified["augmented_rank"]
        additions = int(cap) + 2 * query_count - measured[
            "query_skipped_identity_pairs"]
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
    full = per_cap["2743068"]
    prior = previous_replay["cap_results"]["2000000"]
    prior_additions = previous["charged_pair_add_attempts"]
    q1451_additions = (random_table["table_samples"] + 2 * query_count -
                       random_table["query_skipped_identity_pairs"])
    assert q1451_additions == prior_additions == 4999940
    w7 = next(row for row in model["rows"] if row["weight_bound"] == 7)
    conditional_pair = w7["model"]["pure_pair_index_plus_K_rows_actions_model_log2"]
    output = {
        "proposal_id": "Q1455", "candidate_id": None, "run_id": None,
        "curve_id": measured["curve_id"], "workload_id": measured["workload_id"],
        "isogeny": "none", "factor_base_actual_B": measured["factor_base_actual_B"],
        "factor_base_folded_columns_K": measured["factor_base_folded_columns_K"],
        "factor_base_enumerated_set_sha256": measured[
            "factor_base_enumerated_set_sha256"],
        "measurement_sha256": sha(HERE / "native_measurement.json"),
        "independent_replay_sha256": sha(HERE / "independent_replay.json"),
        "q1454_measurement_sha256": sha(Q1454 / "native_measurement.json"),
        "q1451_measurement_sha256": sha(Q1451),
        "q1452_measurement_sha256": sha(Q1452 / "measurement.json"),
        "n131_conditional_model_sha256": sha(MODEL),
        "per_cap": per_cap,
        "same_input_comparison": {
            "q1451_random_2m_rows": random_table["augmented_rank"],
            "q1451_random_2m_pair_additions_per_row": q1451_additions /
                random_table["augmented_rank"],
            "q1454_unique_2m_rows": prior["augmented_rank"],
            "q1454_unique_2m_pair_additions_per_row": prior_additions /
                prior["augmented_rank"],
            "q1455_complete_rows": full["novel_augmented_rows"],
            "q1455_complete_pair_additions_per_row": full[
                "pair_add_attempts_per_novel_row"],
            "stage_efficiency_ratio_vs_q1454": (prior_additions /
                prior["augmented_rank"]) / full["pair_add_attempts_per_novel_row"],
            "stage_efficiency_ratio_vs_q1451": (q1451_additions /
                random_table["augmented_rank"]) / full[
                    "pair_add_attempts_per_novel_row"],
            "stage_gain_bits_vs_q1451": math.log2((q1451_additions /
                random_table["augmented_rank"]) / full[
                    "pair_add_attempts_per_novel_row"]),
            "comparison_scope": "same frozen N53 public target, exact base, and query draws; table state count and schedule vary; stage pair-addition events only",
        },
        "native_launcher_wall_seconds": measured["launcher_wall_ns"] / 1e9,
        "native_phase_wall_seconds": {name: value / 1e9 for name, value
                                      in measured["phase_wall_ns"].items()},
        "native_peak_rss_bytes": measured["peak_rss_bytes"],
        "n131_conditional_pure_pair_index_log2_logical_actions": conditional_pair,
        "n131_conditional_pure_pair_index_gap_above_2pow61_bits": conditional_pair - 61,
        "n131_index_build_states_log2": w7["model"]["pure_pair_index_states_log2"],
        "n131_model_note": "Q1447 already assumes efficient quotient-pair state enumeration; N53 cap gains do not lower its N131 exponent without a validated transfer law",
        "complete_solve_work_log2": None,
        "degree131_full_solve_challenge_gap_bits": None,
    }
    OUT.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
    print("ANALYZED", output["same_input_comparison"]["stage_efficiency_ratio_vs_q1451"])


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Account for N53 full-index query horizons in named pair-add units."""
from __future__ import annotations
import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
PRIOR = HERE.parent / "q20261011_n53_native_full"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def wilson(successes: int, trials: int, z: float = 1.959963984540054) -> list[float]:
    p = successes / trials
    denominator = 1 + z*z/trials
    middle = (p + z*z/(2*trials)) / denominator
    half = z*math.sqrt(p*(1-p)/trials + z*z/(4*trials*trials)) / denominator
    return [middle-half, middle+half]


def main() -> None:
    measured = json.loads((HERE / "native_measurement.json").read_text())
    replay = json.loads((HERE / "independent_replay.json").read_text())
    query_audit = json.loads((HERE / "query_prefix_audit.json").read_text())
    protocol = json.loads((HERE / "protocol.json").read_text())
    prior = json.loads((PRIOR / "native_measurement.json").read_text())
    assert measured["status"] == "completed_query_cap" and replay["status"] == "PASS"
    assert measured["query_samples_processed"] == 5000000
    table = measured["table_states_generated"]
    assert table == protocol["point_decomposition"]["table_states"]
    match_positions = [match[0] for match in measured["matches"]]
    rows = []
    previous_queries = previous_rank = 0
    for cap in protocol["point_decomposition"]["query_caps"]:
        checked = replay["cap_results"][str(cap)]
        hits = sum(position <= cap for position in match_positions)
        assert hits == checked["candidate_matches"]
        # An identity query pair skips the target-complement addition.
        skipped = query_audit["identity_pair_prefix_counts"][str(cap)]
        charge_upper = table + 2*cap
        charge_exact = charge_upper - skipped
        rank = checked["augmented_rank"]
        rows.append({"query_cap": cap, "candidate_matches": hits,
                     "verified_relations": checked["verified_relation_occurrences"],
                     "augmented_rank": rank,
                     "new_rank_since_previous_cap": rank - previous_rank,
                     "additional_queries_since_previous_cap": cap - previous_queries,
                     "pair_add_attempt_upper_bound": charge_upper,
                     "exact_charged_pair_add_attempts": charge_exact,
                     "pair_add_upper_bound_per_rank_row": charge_upper/rank if rank else None,
                     "exact_pair_adds_per_rank_row": charge_exact/rank if rank else None,
                     "conditional_match_rate": hits/cap,
                     "conditional_match_rate_wilson_95": wilson(hits, cap)})
        previous_queries, previous_rank = cap, rank
    first = rows[0]
    last = rows[-1]
    best = min(rows, key=lambda row: row["exact_pair_adds_per_rank_row"])
    prior_replay = json.loads((PRIOR / "independent_replay.json").read_text())
    assert first["augmented_rank"] == prior_replay["cap_results"]["2743068"]["augmented_rank"]
    prior_adds = prior["charged_pair_add_attempts"]
    assert first["exact_charged_pair_add_attempts"] == prior_adds
    assert abs(prior_adds / first["augmented_rank"] - 273476.5714285714) < 1
    output = {"proposal_id": "Q1456", "candidate_id": None, "run_id": None,
              "curve_id": protocol["curve_id"], "workload_id": protocol["workload_id"],
              "isogeny": "none", "factor_base_actual_B": protocol["factor_base_actual_B"],
              "factor_base_folded_columns_K": protocol["factor_base_folded_columns_K"],
              "factor_base_enumerated_set_sha256": protocol["factor_base_enumerated_set_sha256"],
              "measurement_sha256": sha(HERE / "native_measurement.json"),
              "independent_replay_sha256": sha(HERE / "independent_replay.json"),
              "query_prefix_audit_sha256": sha(HERE / "query_prefix_audit.json"),
              "q1455_analysis_sha256": sha(PRIOR / "analysis.json"),
              "query_horizons": rows,
              "best_measured_query_cap_for_pair_adds_per_rank_row": best["query_cap"],
              "best_measured_pair_adds_per_rank_row": best["exact_pair_adds_per_rank_row"],
              "best_measured_pair_adds_per_rank_row_log2": math.log2(best["exact_pair_adds_per_rank_row"]),
              "best_vs_q1455_pair_adds_per_novel_row_ratio":
                  (prior_adds / first["augmented_rank"]) / best["exact_pair_adds_per_rank_row"],
              "best_vs_q1455_pair_adds_per_novel_row_bits":
                  math.log2((prior_adds / first["augmented_rank"]) / best["exact_pair_adds_per_rank_row"]),
              "full_horizon_pair_adds_per_novel_row_log2": math.log2(last["exact_pair_adds_per_rank_row"]),
              "full_vs_q1455_pair_adds_per_novel_row_ratio":
                  (prior_adds / first["augmented_rank"]) / last["exact_pair_adds_per_rank_row"],
              "full_vs_q1455_pair_adds_per_novel_row_bits":
                  math.log2((prior_adds / first["augmented_rank"]) / last["exact_pair_adds_per_rank_row"]),
              "q1447_conditional_n131_logical_action_log2": 85.18,
              "q1447_conditional_gap_above_2_61_bits": 24.18,
              "complete_solve_work_log2": None,
              "degree131_challenge_gap_bits": None,
              "units_note": "Pair-add attempts are a stage count; Q1447 logical actions and full-solve operations are different boundaries."}
    (HERE / "analysis.json").write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
    print("Q1456", [(item["query_cap"], item["augmented_rank"]) for item in rows],
          output["full_horizon_pair_adds_per_novel_row_log2"])


if __name__ == "__main__":
    main()

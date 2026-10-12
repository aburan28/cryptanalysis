#!/usr/bin/env python3
"""Reprice Q1447's conditional N131 pair index using measured query additions."""
from __future__ import annotations
import hashlib
import json
import math
from fractions import Fraction
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
Q1447 = PARENT / "q20261011_weight7_screen/measurement.json"
Q1457 = PARENT / "q20261011_n53_full_pipeline/independent_replay.json"
Q1461 = PARENT / "q20261011_n53_fresh_target/native_first.cpp"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def log2(value: Fraction) -> float:
    return math.log2(value.numerator) - math.log2(value.denominator)


def main() -> None:
    assert not (HERE / "analysis.json").exists()
    protocol = json.loads((HERE / "protocol.json").read_text())
    prior = json.loads(Q1447.read_text())
    n53 = json.loads(Q1457.read_text())
    native = Q1461.read_text()
    assert prior["curve_id"] == protocol["curve_id"]
    assert prior["complete_solve_work_log2"] is None
    assert n53["matrix_rank"] == 227 and n53["verified_relation_occurrences"] == 400
    assert "P sum=add(base[query[0]],base[query[1]]);" in native
    assert "P complement=add(target,neg(sum));" in native
    row = next(item for item in prior["rows"] if item["weight_bound"] == 7)
    n = prior["field_degree_n"]
    k = row["conditional_folded_K"]
    b = row["conditional_B"]
    r = int(prior["subgroup_order_r"])
    assert b == 2 * n * k
    table_max = n * k * k
    queries_full = Fraction(k * 2 * r, b * b)
    prior_actions = Fraction(table_max) + queries_full
    assert abs(log2(prior_actions) -
               row["model"]["pure_pair_index_plus_K_rows_actions_model_log2"]) < 1e-10
    fractions = [Fraction(value) for value in protocol["table_size_fractions_of_full"]]
    rows = []
    for fraction in fractions:
        states = Fraction(table_max) * fraction
        queries = queries_full / fraction
        actions = states + 2 * queries
        rows.append({"table_fraction": str(fraction),
                     "table_states_log2": log2(states),
                     "optimistic_successful_queries_log2": log2(queries),
                     "counted_pair_add_attempts_log2": log2(actions),
                     "gap_above_2pow61_pair_add_bits": log2(actions) - 61})
    # For A(T)=T+K*r/(n*T), the unrestricted stationary point is
    # sqrt(K*r/n).  The frozen index family only supports T<=n*K^2.
    optimum_log2 = (math.log2(k) + math.log2(r) - math.log2(n)) / 2
    table_max_log2 = math.log2(table_max)
    assert optimum_log2 > table_max_log2
    rank_ratio = Fraction(n53["verified_relation_occurrences"], n53["matrix_rank"])
    sensitivity = Fraction(table_max) + 2 * queries_full * rank_ratio
    result = {"proposal_id": "Q1462", "candidate_id": None, "run_id": None,
              "curve_id": protocol["curve_id"], "isogeny": "none",
              "status": "CONDITIONAL_MODEL_REPRICED",
              "protocol_sha256": sha(HERE / "protocol.json"),
              "source_sha256": sha(Path(__file__)),
              "q1447_measurement_sha256": sha(Q1447),
              "q1457_replay_sha256": sha(Q1457),
              "q1461_native_source_sha256": sha(Q1461),
              "conditional_B": b, "conditional_K": k,
              "subgroup_order_r": str(r),
              "full_table_states": table_max,
              "full_table_states_log2": table_max_log2,
              "unrestricted_optimal_table_states_log2": optimum_log2,
              "unrestricted_optimum_exceeds_full_table_by_bits": optimum_log2 - table_max_log2,
              "table_size_search": rows,
              "measured_n53_relation_occurrences_per_final_rank": {
                  "numerator": rank_ratio.numerator, "denominator": rank_ratio.denominator},
              "cross_degree_rank_novelty_sensitivity_log2_pair_add_attempts": log2(sensitivity),
              "cross_degree_sensitivity_is_projection": True,
              "conditional_full_table_counted_pair_add_attempts_log2": rows[0]["counted_pair_add_attempts_log2"],
              "conditional_gap_above_2pow61_pair_add_bits": rows[0]["gap_above_2pow61_pair_add_bits"],
              "complete_solve_work_log2": None,
              "degree131_complete_solve_challenge_gap_bits": None,
              "model_caveat": "W<=7 base size is sampled and conditional; successful-query count assumes uniform support and every useful relation raises rank; factor-base construction, sparse LA and target descent are excluded"}
    (HERE / "analysis.json").write_text(json.dumps(result, indent=2,
                                                sort_keys=True) + "\n")
    print("Q1462", rows[0]["counted_pair_add_attempts_log2"],
          rows[0]["gap_above_2pow61_pair_add_bits"])


if __name__ == "__main__":
    main()

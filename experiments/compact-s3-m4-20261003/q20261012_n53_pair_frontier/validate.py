#!/usr/bin/env python3
"""Check Q1511 frozen inputs and prefix-frontier arithmetic."""
import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
SOURCE = PARENT / "q20261011_n53_full_pipeline"
PAIR = PARENT / "q20261011_n53_native_pair"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    result = json.loads((HERE / "result.json").read_text())
    measured = json.loads((SOURCE / "native_measurement.json").read_text())
    freeze = json.loads((SOURCE / "freeze.json").read_text())
    replay = json.loads((SOURCE / "independent_replay.json").read_text())
    assert result["proposal_id"] == "Q1511"
    assert result["candidate_id"] is result["run_id"] is None
    assert result["source_sha256"] == sha(HERE / "analyze.py")
    for name, digest in result["input_sha256"].items():
        assert sha(SOURCE / name) == digest
    assert sha(PARENT / "bases/n53_weight3_orbits.json.gz") == result["base_archive_sha256"]
    assert sha(PAIR / "inputs/base.bin") == result["base_points_sha256"] == freeze["base_input_sha256"]
    assert result["query_file_sha256"] == freeze["query_file_sha256"]
    assert result["curve_id"] == measured["curve_id"] == replay["curve_id"]
    assert result["factor_base_actual_B"] == measured["factor_base_actual_B"] == 24062
    assert result["factor_base_folded_columns_K"] == replay["matrix_rank"] == 227
    assert result["factor_base_enumerated_set_sha256"] == measured["factor_base_enumerated_set_sha256"]
    assert len(measured["matches"]) == len(replay["relations"]) == 400
    full = result["full_run"]
    assert full["table_states"] == measured["table_states_generated"]
    assert full["query_representatives"] == measured["query_samples_processed"]
    assert full["charged_pair_add_attempts"] == measured["charged_pair_add_attempts"]
    assert math.isclose(full["operation_log2"], math.log2(full["charged_pair_add_attempts"]))
    frontier = result["prefix_frontier"]
    assert len(frontier) == result["feasible_prefix_count"] > 0
    assert frontier[0]["table_states"] == result["smallest_full_rank_table_states"]
    assert all(a["table_states"] < b["table_states"] for a, b in zip(frontier, frontier[1:]))
    assert all(row["charged_pair_add_attempts"] == row["table_states"] +
               2 * row["query_representatives"] - row["identity_queries"] for row in frontier)
    assert all(row["query_representatives"] <= full["query_representatives"] and
               row["verified_relations_at_stop"] >= 227 for row in frontier)
    best = result["best_frozen_prefix"]
    assert {k: best[k] for k in frontier[0]} == min(
        frontier, key=lambda x: (x["charged_pair_add_attempts"], x["table_states"]))
    assert best["saved_pair_add_attempts"] == full["charged_pair_add_attempts"] - best["charged_pair_add_attempts"]
    assert math.isclose(best["saved_work_bits"], math.log2(full["charged_pair_add_attempts"] /
                                                       best["charged_pair_add_attempts"]))
    assert result["rank_grid"][-1]["rank_at_30m_queries"] == 227
    assert result["complete_n131_solve_operation_log2"] is None
    print("PASS Q1511 frozen prefix frontier and source binding")


if __name__ == "__main__":
    main()

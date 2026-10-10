#!/usr/bin/env python3
"""Verify frozen sources and custody of all N41 same-pair stage outcomes."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PRIOR = ROOT / "n41_w5_ten_native_join_20261010"
GATE = ROOT / "n41_w5_ten_source_gate_20261010"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(name):
    return json.loads((HERE / name).read_text())


def main():
    source = read("protocol.json")
    assert source["status"] == "FROZEN_BEFORE_NATIVE_SEARCH"
    assert source["source_sha256"] == {
        "prepare": sha(HERE / "prepare.py"),
        "geometry": sha(GATE / "geometry_result.json"),
        "prior_input": sha(PRIOR / "input.txt"),
        "join_source": sha(PRIOR / "join.cpp"),
        "join_binary": sha(PRIOR / "join"),
        "input": sha(HERE / "input.txt")}
    native = read("run/result.json")
    sage = read("sage_audit.json")
    assert native["status"] == "FOUND_PENDING_SAGE_REPLAY"
    assert sage["status"] == "PASS_INDEPENDENT_SAGE_SAMEPAIR_PUBLIC_RELATION"
    assert sage["source_sha256"]["native_result"] == sha(HERE / "run/result.json")
    assert sage["source_sha256"]["native_hit"] == sha(HERE / "run/hits.jsonl")
    assert native["right_distinct_probes"] == 15847
    assert len(set(sage["folded_columns"])) == 10
    assert source["actual_factor_base_points_B"] == 170
    assert source["folded_columns_K"] == 14

    hybrid = read("hybrid_protocol.json")
    preflight = read("preflight.json")
    query = read("query_result.json")
    assert hybrid["status"] == "FROZEN_BEFORE_HYBRID_FORMULA"
    assert preflight["status"] == "PASS_FULL_HYBRID_FORMULA_PUBLIC_RELATION"
    assert preflight["relation"]["valid"]
    assert preflight["xcnf_check"] == {
        "cnf_clauses": preflight["formula"]["clauses"],
        "xor_rows": preflight["formula"]["xor_rows"]}
    assert preflight["formula"]["sha256"] == sha(HERE / "public_hybrid.xcnf")
    assert query["status"] == "CENSORED_TIME"
    assert query["stop_reason"] == "SOLVER_WALL_CAP"
    assert query["model_lines"] == 0 and query["solver_status_lines"] == []
    assert query["source_sha256"]["stdout"] == sha(HERE / "solver.stdout.txt")
    assert query["source_sha256"]["stderr"] == sha(HERE / "solver.stderr.txt")
    stdout = (HERE / "solver.stdout.txt").read_text()
    restarts = sum(line.startswith("c rst") for line in stdout.splitlines())
    assert restarts > 0 and not (HERE / "solver.stderr.txt").read_text()

    comparison = read("formula_comparison.json")
    assert comparison["status"] == "PASS_MATCHED_EXACT_AND_RELAXED_FORMULA_CONTROLS"
    assert comparison["exact"]["sha256"] == sha(HERE / "exact_samepair.xcnf")
    assert comparison["relaxed"] == preflight["formula"]
    assert comparison["exact_full_assignment_check"] == {
        "cnf_clauses": comparison["exact"]["clauses"],
        "xor_rows": comparison["exact"]["xor_rows"]}

    pair_protocol = read("pair_analysis_protocol_v2.json")
    pair = read("pair_analysis.json")
    assert pair_protocol["status"] == "FROZEN_BEFORE_PAIR_CARDINALITY_RUN_V2"
    assert pair_protocol["source_sha256"] == sha(HERE / "analyze_pairs.cpp")
    assert pair["status"] == "PASS_EXACT_PAIR_IMAGE_COUNTS"
    assert pair["pair_rows_per_block"] == [1056] * 5
    assert pair["unique_pair_sums"] == [528] * 5
    assert pair["left_four_rows"] == native["left_distinct_four_sums"]
    assert pair["unique_left_four_sums"] == 191136

    repeats = read("repeat_result.json")
    repeat_protocol = read("repeat_protocol.json")
    assert repeats["status"] == "COMPLETE_FOUR_BOUNDED_SAME_TARGET_REPEATS"
    assert repeats["source_sha256"]["protocol"] == sha(HERE / "repeat_protocol.json")
    assert len(repeats["repeats"]) == 4
    for row in repeats["repeats"]:
        folder = HERE / "repeats" / f"R{row['repeat']}"
        result = json.loads((folder / "result.json").read_text())
        assert row["input_sha256"] == repeat_protocol["repeat_input_sha256"][f"R{row['repeat']}"]
        assert row["input_sha256"] == sha(folder / "input.txt")
        assert row["result_sha256"] == sha(folder / "result.json")
        assert row["hits_sha256"] == sha(folder / "hits.jsonl")
        assert result["status"] == row["status"] == "CENSORED_PROBES"
        assert result["right_distinct_probes"] == 2000000
        assert result["group_hits"] == result["column_rejects"]

    receipt = {"status": "PASS_FROZEN_SAMEPAIR_STAGE_AUDIT",
               "curve_id": source["curve_id"],
               "public_target_q": source["public_q"],
               "actual_factor_base_points_B": 170,
               "folded_columns_K": 14,
               "native_first_hit_probes": native["right_distinct_probes"],
               "same_target_repeat_count": 4,
               "repeat_censored_probes_total": 8000000,
               "repeat_group_hits_rejected_columns": sum(
                   row["column_rejects"] for row in repeats["repeats"]),
               "hybrid_formula": preflight["formula"],
               "exact_formula": comparison["exact"],
               "hybrid_solver_restarts_logged": restarts,
               "hybrid_solver_status": query["status"],
               "source_sha256": {"script": sha(Path(__file__)),
                                 "source_protocol": sha(HERE / "protocol.json"),
                                 "native": sha(HERE / "run/result.json"),
                                 "sage": sha(HERE / "sage_audit.json"),
                                 "hybrid_protocol": sha(HERE / "hybrid_protocol.json"),
                                 "preflight": sha(HERE / "preflight.json"),
                                 "query": sha(HERE / "query_result.json"),
                                 "comparison": sha(HERE / "formula_comparison.json"),
                                 "pair": sha(HERE / "pair_analysis.json"),
                                 "repeats": sha(HERE / "repeat_result.json")}}
    with (HERE / "terminal_audit.json").open("x") as out:
        json.dump(receipt, out, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps({"status": receipt["status"],
                      "search_restarts": restarts,
                      "repeat_rejected_group_hits": receipt["repeat_group_hits_rejected_columns"]}))


if __name__ == "__main__":
    main()

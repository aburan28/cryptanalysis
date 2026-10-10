#!/usr/bin/env python3
"""Check five-pair formula, pre-search failure, and all-fixed gate custody."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PRIOR = ROOT / "n41_w5_pair_index_20261010"
SAMEPAIR = ROOT / "n41_w5_samepair_hybrid_20261010"
SOURCE = ROOT / "n41_w5_ten_source_gate_20261010"
SOLVER = Path("/opt/homebrew/bin/cryptominisat5")
sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
read = lambda path: json.loads((HERE / path).read_text())


def main():
    runtime = read("sage_runtime_info.json")
    protocol = read("protocol.json")
    preflight = read("preflight.json")
    failure = read("failure_v1.json")
    result = read("all_fixed_query/result.json")
    gate = read("gate_result.json")
    assert runtime["status"] == "verified"
    assert protocol["status"] == "FROZEN_BEFORE_ALL_PAIR_FORMULA_AND_QUERIES"
    assert protocol["source_sha256"] == {
        "runner": sha(HERE / "run.py"),
        "circuit": sha(HERE / "circuit.py"),
        "single_runner": sha(PRIOR / "run.py"),
        "single_circuit": sha(PRIOR / "circuit.py"),
        "pair_index": sha(PRIOR / "pair_index.json"),
        "pair_index_sage_audit": sha(PRIOR / "sage_index_audit.json"),
        "samepair_hit": sha(SAMEPAIR / "run/hits.jsonl"),
        "samepair_sage_audit": sha(SAMEPAIR / "sage_audit.json"),
        "geometry": sha(SOURCE / "geometry_result.json"),
        "runtime": sha(HERE / "sage_runtime_info.json"),
        "solver": sha(SOLVER)}
    assert protocol["actual_factor_base_points_B"] == 170
    assert protocol["folded_columns_K"] == 14
    assert protocol["known_relation_selectors"] == [240, 172, 138, 253, 178]
    assert preflight["status"] == "PASS_FULL_FIVE_PAIR_INDEX_CONTROLS"
    assert preflight["known_relation"]["valid"]
    assert preflight["known_selectors"] == protocol["known_relation_selectors"]
    for name, path in (("public", "public_allpair.xcnf"),
                       ("four_fixed", "four_fixed.xcnf"),
                       ("all_fixed", "all_fixed.xcnf")):
        formula = preflight["formulas"][name]
        assert formula["sha256"] == sha(HERE / path)
        assert preflight["xcnf_checks"][name] == {
            "cnf_clauses": formula["clauses"],
            "xor_rows": formula["xor_rows"]}
    assert failure["status"] == "PRODUCER_FAILURE_ENOSPC_BEFORE_SEARCH"
    assert failure["solver_started"] is False
    assert failure["protocol_sha256"] == sha(HERE / "protocol.json")
    assert failure["runner_sha256"] == sha(HERE / "run.py")
    assert result["status"] == "CENSORED_TIME"
    assert result["stop_reason"] == "SOLVER_WALL_CAP"
    assert result["model_lines"] == 0 and result["solver_status_lines"] == []
    stdout = HERE / "all_fixed_query/solver.stdout.txt"
    stderr = HERE / "all_fixed_query/solver.stderr.txt"
    assert result["source_sha256"]["stdout"] == sha(stdout)
    assert result["source_sha256"]["stderr"] == sha(stderr)
    assert not stderr.read_text()
    restarts = sum(row.startswith("c rst") for row in stdout.read_text().splitlines())
    assert restarts > 0
    assert gate["status"] == "GATE_CLOSED_UPPER_S3_FIXED_CONTROL_CENSORED"
    assert gate["source_sha256"]["protocol"] == sha(HERE / "protocol.json")
    assert gate["source_sha256"]["all_fixed_result"] == sha(HERE / "all_fixed_query/result.json")
    assert gate["four_fixed_status"] == gate["public_status"] == "NOT_RUN_GATE_CLOSED"
    assert not (HERE / "four_fixed_query").exists()
    assert not (HERE / "public_query").exists()
    receipt = {"status": "PASS_FROZEN_FIVE_PAIR_INDEX_GATE",
               "curve_id": protocol["curve_id"],
               "public_target_q": protocol["public_target_q"],
               "actual_factor_base_points_B": 170,
               "folded_columns_K": 14,
               "entries_per_pair": 264,
               "public_formula": preflight["formulas"]["public"],
               "all_fixed_search": {"status": result["status"],
                                    "solver_wall_seconds": result["solver_wall_seconds"],
                                    "logged_restarts": restarts,
                                    "sampled_solver_peak_rss_bytes": result["sampled_solver_peak_rss_bytes"]},
               "gate_status": gate["status"],
               "source_sha256": {"script": sha(Path(__file__)),
                                 "protocol": sha(HERE / "protocol.json"),
                                 "preflight": sha(HERE / "preflight.json"),
                                 "failure": sha(HERE / "failure_v1.json"),
                                 "all_fixed_result": sha(HERE / "all_fixed_query/result.json"),
                                 "gate": sha(HERE / "gate_result.json")}}
    with (HERE / "terminal_audit.json").open("x") as out:
        json.dump(receipt, out, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps({"status": receipt["status"],
                      "restarts": restarts}))


if __name__ == "__main__":
    main()

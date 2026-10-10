#!/usr/bin/env python3
"""Audit exact pair index, complete witness, and bounded search receipts."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SOURCE = ROOT / "n41_w5_ten_source_gate_20261010"
SAMEPAIR = ROOT / "n41_w5_samepair_hybrid_20261010"
LOW = ROOT / "n41_w5_ten_lowproduct_20261010" / "circuit.py"
SOLVER = Path("/opt/homebrew/bin/cryptominisat5")
sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
read = lambda path: json.loads((HERE / path).read_text())


def main():
    index = read("pair_index.json")
    sage = read("sage_index_audit.json")
    runtime = read("sage_runtime_info.json")
    assert runtime["status"] == "verified"
    assert index["status"] == "PASS_EXACT_W5_UNORDERED_PAIR_INDEX"
    assert sage["status"] == "PASS_INDEPENDENT_SAGE_COMPLETE_W5_PAIR_INDEX"
    assert sage["source_sha256"]["index"] == sha(HERE / "pair_index.json")
    assert index["source_sha256"]["script"] == sha(HERE / "build_index.py")
    assert index["source_sha256"]["geometry"] == sha(SOURCE / "geometry_result.json")
    assert index["signature_count"] == sage["exact_signatures"] == 264
    assert index["accepted_unordered_signed_pair_rows"] == \
        sage["enumerated_unordered_signed_rows"] == 528
    assert index["distinct_transformed_outputs"] == 264

    protocol = read("protocol.json")
    assert protocol["status"] == "FROZEN_BEFORE_INDEXED_FORMULA_AND_SEARCH"
    assert protocol["source_sha256"] == {
        "runner": sha(HERE / "run.py"),
        "circuit": sha(HERE / "circuit.py"),
        "index_builder": sha(HERE / "build_index.py"),
        "pair_index": sha(HERE / "pair_index.json"),
        "index_sage_audit": sha(HERE / "sage_index_audit.json"),
        "runtime": sha(HERE / "sage_runtime_info.json"),
        "geometry": sha(SOURCE / "geometry_result.json"),
        "source_runner": sha(SOURCE / "run.py"),
        "lowproduct_circuit": sha(LOW),
        "public_hit": sha(SAMEPAIR / "run/hits.jsonl"),
        "public_hit_sage_audit": sha(SAMEPAIR / "sage_audit.json"),
        "solver": sha(SOLVER)}
    assert protocol["actual_factor_base_points_B"] == 170
    assert protocol["folded_columns_K"] == 14
    assert protocol["known_relation_selector_index"] == 178

    preflight = read("preflight.json")
    assert preflight["status"] == "PASS_FULL_INDEXED_PUBLIC_AND_FIXED_CONTROLS"
    assert preflight["known_relation"]["valid"]
    assert preflight["known_selector_index"] == 178
    for mode, path in (("public", "public_indexed.xcnf"),
                       ("fixed", "fixed_selector.xcnf")):
        stats = preflight[f"{mode}_formula"]
        assert stats["sha256"] == sha(HERE / path)
        assert preflight[f"{mode}_xcnf_check"] == {
            "cnf_clauses": stats["clauses"],
            "xor_rows": stats["xor_rows"]}

    search = {}
    for mode in ("fixed", "public"):
        folder = HERE / f"{mode}_query"
        result = json.loads((folder / "result.json").read_text())
        stdout = folder / "solver.stdout.txt"
        stderr = folder / "solver.stderr.txt"
        assert result["status"] == "CENSORED_TIME"
        assert result["stop_reason"] == "SOLVER_WALL_CAP"
        assert result["solver_status_lines"] == [] and result["model_lines"] == 0
        assert result["source_sha256"]["formula"] == \
            preflight[f"{mode}_formula"]["sha256"]
        assert result["source_sha256"]["stdout"] == sha(stdout)
        assert result["source_sha256"]["stderr"] == sha(stderr)
        assert not stderr.read_text()
        restarts = sum(line.startswith("c rst") for line in stdout.read_text().splitlines())
        assert restarts > 0
        search[mode] = {"status": result["status"],
                        "wall_seconds": result["solver_wall_seconds"],
                        "restarts_logged": restarts,
                        "peak_rss_bytes": result["sampled_solver_peak_rss_bytes"],
                        "result_sha256": sha(folder / "result.json")}

    receipt = {"status": "PASS_FROZEN_N41_EXACT_PAIR_INDEX_GATE",
               "curve_id": protocol["curve_id"],
               "public_target_q": protocol["public_target_q"],
               "actual_factor_base_points_B": 170,
               "folded_columns_K": 14,
               "exact_pair_signatures": 264,
               "public_formula": preflight["public_formula"],
               "fixed_formula": preflight["fixed_formula"],
               "search": search,
               "source_sha256": {"script": sha(Path(__file__)),
                                 "index": sha(HERE / "pair_index.json"),
                                 "sage": sha(HERE / "sage_index_audit.json"),
                                 "protocol": sha(HERE / "protocol.json"),
                                 "preflight": sha(HERE / "preflight.json")}}
    with (HERE / "terminal_audit.json").open("x") as out:
        json.dump(receipt, out, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps({"status": receipt["status"],
                      "fixed_restarts": search["fixed"]["restarts_logged"],
                      "public_restarts": search["public"]["restarts_logged"]}))


if __name__ == "__main__":
    main()

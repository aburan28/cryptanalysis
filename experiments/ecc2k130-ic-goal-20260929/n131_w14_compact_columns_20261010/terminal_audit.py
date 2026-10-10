#!/usr/bin/env sage -python
"""Audit the frozen N131 compact-column construction and capped public run."""

import gzip
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ORIGINAL = HERE.parent / "n131_w14_coupled_sixpair_sat_20261010"


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        while block := stream.read(1 << 20):
            digest.update(block)
    return digest.hexdigest()


def lines(path):
    return Path(path).read_text(errors="replace").splitlines()


def formula_audit(path, expected):
    digest = hashlib.sha256()
    byte_count = 0
    header = None
    cnf = xor = 0
    with gzip.open(path, "rb") as stream:
        for line in stream:
            digest.update(line)
            byte_count += len(line)
            if line.startswith(b"p "):
                assert header is None
                header = line.decode().strip()
            elif line.startswith(b"x"):
                xor += 1
            else:
                cnf += 1
    assert digest.hexdigest() == expected["sha256"]
    assert byte_count == expected["bytes"]
    assert header == f"p cnf {expected['variables']} {expected['clauses']+expected['xor_rows']}"
    assert cnf == expected["clauses"] and xor == expected["xor_rows"]
    return {"header": header, "bytes": byte_count,
            "cnf_clauses": cnf, "native_xor_rows": xor,
            "uncompressed_sha256": digest.hexdigest()}


def last_restart_conflicts(output):
    restarts = [line for line in output if line.startswith("c rst ")]
    assert restarts
    return restarts[-1].split()[6]


def main():
    protocol = json.loads((HERE / "protocol.json").read_text())
    control = json.loads((HERE / "control_result.json").read_text())
    result = json.loads((HERE / "public_query/result.json").read_text())
    baseline = json.loads((ORIGINAL / "public_query/result.json").read_text())
    assert protocol["status"] == "FROZEN_BEFORE_COMPACT_N131_CONTROL_AND_PUBLIC_QUERY"
    assert control["status"] == "PASS_FULL_COMPACT_N131_CONSTRUCTED_ASSIGNMENT"
    assert control["source_sha256"]["protocol"] == sha(HERE / "protocol.json")
    assert result["sha256"]["protocol"] == sha(HERE / "protocol.json")
    assert result["sha256"]["control"] == sha(HERE / "control_result.json")
    assert result["target_q"] == baseline["target_q"] == protocol["public_target_q"]
    assert result["status"] == baseline["status"] == "CENSORED_TIME"
    assert result["stop_reason"] == "SOLVER_WALL_CAP"
    assert result["solver_exit_code"] == -15
    assert result["solver_status_lines"] == [] and result["model_lines"] == 0
    assert result["verified_relations"] == result["useful_rank"] == 0
    assert result["sampled_peak_combined_rss_bytes"] < protocol["rss_cap_bytes"]
    assert result["phase_seconds"]["construction_plus_search"] < protocol[
        "public_construction_plus_search_cap_seconds"]
    assert result["formula"]["column_clauses"] == protocol[
        "expected_compact_column_clauses"]
    assert control["formula"]["column_clauses"] == protocol[
        "expected_compact_column_clauses"]
    assert control["full_xcnf_assignment_check"] == {
        "cnf_clauses": control["formula"]["clauses"],
        "xor_rows": control["formula"]["xor_rows"]}
    assert result["formula"]["clauses"] < baseline["formula"]["clauses"]
    assert result["formula"]["xor_rows"] > baseline["formula"]["xor_rows"]
    for name, relative in {
        "experiment": HERE / "experiment.py",
        "compact_circuit": HERE / "circuit.py",
        "original_run": ORIGINAL / "run.py",
        "original_circuit": ORIGINAL / "circuit.py",
        "original_control": ORIGINAL / "control.json",
        "original_sage_audit": ORIGINAL / "sage_audit.json",
        "original_public_protocol": ORIGINAL / "query_protocol.json",
        "original_group_lift": ORIGINAL / "lift.py",
        "checked_sage_runtime": HERE / "sage_runtime_info.json",
        "solver": Path("/opt/homebrew/bin/cryptominisat5"),
    }.items():
        assert protocol["source_sha256"][name] == sha(relative), name
    new_log = lines(HERE / "public_query/solver.stdout.txt")
    old_log = lines(ORIGINAL / "public_query/solver.stdout.txt")
    assert result["sha256"]["stdout"] == sha(HERE / "public_query/solver.stdout.txt")
    assert result["sha256"]["stderr"] == sha(HERE / "public_query/solver.stderr.txt")
    assert not [line for line in new_log if line.startswith("s ")]
    assert any("[matrix]" in line for line in new_log)
    control_formula = formula_audit(HERE / "constructed.xcnf.gz",
                                    control["formula"])
    public_formula = formula_audit(HERE / "public_query/system.xcnf.gz",
                                   result["formula"])
    receipt = {
        "status": "PASS_COMPACT_N131_TERMINAL_CENSORED_AUDIT",
        "candidate_id": None, "curve_id": protocol["curve_id"],
        "target_q": result["target_q"],
        "constructed_assignment": control["full_xcnf_assignment_check"],
        "control_formula": control_formula, "public_formula": public_formula,
        "column_clause_reduction": {
            "baseline": protocol["original_duplicate_column_clauses"],
            "compact": protocol["expected_compact_column_clauses"]},
        "paired_public_status": {
            "baseline": baseline["status"], "compact": result["status"]},
        "last_logged_conflicts": {
            "baseline": last_restart_conflicts(old_log),
            "compact": last_restart_conflicts(new_log)},
        "sampled_solver_cpu_seconds": {
            "baseline": baseline["sampled_solver_cpu_seconds"],
            "compact": result["sampled_solver_cpu_seconds"]},
        "verified_public_relations": 0, "useful_rank": 0,
        "source_sha256": {name: sha(path) for name, path in {
            "script": __file__, "protocol": HERE / "protocol.json",
            "control": HERE / "control_result.json",
            "result": HERE / "public_query/result.json",
            "baseline_result": ORIGINAL / "public_query/result.json",
            "control_formula_gzip": HERE / "constructed.xcnf.gz",
            "public_formula_gzip": HERE / "public_query/system.xcnf.gz",
            "new_solver_log": HERE / "public_query/solver.stdout.txt",
            "baseline_solver_log": ORIGINAL / "public_query/solver.stdout.txt",
        }.items()},
    }
    with (HERE / "terminal_audit.json").open("x") as out:
        json.dump(receipt,out,indent=2,sort_keys=True)
        out.write("\n")
    print(json.dumps({"status": receipt["status"],
                      "column_clause_reduction": receipt["column_clause_reduction"],
                      "last_logged_conflicts": receipt["last_logged_conflicts"]}))


if __name__ == "__main__":
    main()

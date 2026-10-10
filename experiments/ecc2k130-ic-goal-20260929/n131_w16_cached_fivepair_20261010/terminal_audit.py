#!/usr/bin/env python3
"""Read-only archive audit of the cached W16 control and bounded query."""

import gzip
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
OLD = HERE.parent / "n131_w16_fivepair_sat_gate_20261010"
WIDTH = HERE.parent / "n131_w16_w18_sixpair_width_gate_20261010"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    base = json.loads((HERE / "protocol.json").read_text())
    core = json.loads((HERE / "core_result.json").read_text())
    control = json.loads((HERE / "control_result.json").read_text())
    frozen = json.loads((HERE / "query_protocol.json").read_text())
    query = json.loads((HERE / "query_result.json").read_text())
    assert base["status"] == "FROZEN_BEFORE_W16_CACHED_CORE"
    assert base["source_sha256"] == {name: sha(path) for name, path in {
        "runner": HERE / "run.py", "core": HERE / "core.py",
        "input": OLD / "fivepair_input.json",
        "prior_runner": OLD / "fivepair_run.py",
        "prior_circuit": OLD / "fivepair_circuit.py",
        "prior_lift": OLD / "fivepair_lift.py",
        "prior_query": OLD / "query_v2_result.json",
        "width_result": WIDTH / "result.json",
        "width_audit": WIDTH / "audit_result.json",
        "width_support": WIDTH / "support_w16.tsv",
        "runtime": HERE / "sage_runtime_info.json",
        "solver": Path("/opt/homebrew/bin/cryptominisat5")}.items()}
    assert core["status"] == "PASS_REUSABLE_W16_SOURCE_CORE"
    assert core["source_sha256"] == base["source_sha256"]
    assert core["protocol_sha256"] == sha(HERE / "protocol.json")
    assert core["core_gzip_sha256"] == sha(HERE / "core.pickle.gz")
    assert core["core_bytes"] == (HERE / "core.pickle.gz").stat().st_size
    assert control["status"] == "PASS_CACHED_W16_FULL_XCNF_AND_GROUP_CONTROL"
    assert control["group_lift_status"] == "GROUP_LIFT_FOUND"
    assert control["source_sha256"] == {
        "protocol": sha(HERE / "protocol.json"),
        "core_result": sha(HERE / "core_result.json"),
        "group_lift": sha(HERE / "control_group_lift.json")}
    assert control["formula"]["gzip_sha256"] == sha(HERE / "control.xcnf.gz")
    whole = hashlib.sha256()
    clauses = xors = 0
    with gzip.open(HERE / "control.xcnf.gz", "rb") as stream:
        header = stream.readline().decode()
        whole.update(header.encode())
        for line in stream:
            whole.update(line)
            if line.startswith(b"x "):
                xors += 1
            else:
                clauses += 1
    assert whole.hexdigest() == control["formula"]["sha256"]
    assert header == f"p cnf {control['formula']['variables']} {clauses+xors}\n"
    assert (clauses, xors) == (control["formula"]["cnf_clauses"],
                              control["formula"]["native_xor_rows"])
    assert control["full_assignment_check"] == {
        "cnf_clauses": clauses, "xor_rows": xors}
    assert frozen["status"] == "FROZEN_BEFORE_CACHED_W16_QUERY"
    assert frozen["source_sha256"] == {name: sha(path) for name, path in {
        "query": HERE / "query.py", "runner": HERE / "run.py",
        "core_source": HERE / "core.py", "core": HERE / "core.pickle.gz",
        "core_result": HERE / "core_result.json",
        "base_protocol": HERE / "protocol.json",
        "control_result": HERE / "control_result.json",
        "control_formula": HERE / "control.xcnf.gz",
        "input": OLD / "fivepair_input.json",
        "runtime": HERE / "sage_runtime_info.json",
        "solver": Path("/opt/homebrew/bin/cryptominisat5")}.items()}
    assert query["formula"]["sha256"] == control["formula"]["sha256"]
    assert query["status"] == "CENSORED_TIME"
    assert query["stop_reason"] == "PARENT_SAFE_STOP"
    assert query["phase_ns"]["charged_total"] <= frozen["wall_cap_seconds"]*10**9
    assert query["sampled_peak_combined_rss_bytes"] < frozen["rss_cap_bytes"]
    assert query["source_sha256"] == {
        "protocol": sha(HERE / "query_protocol.json"),
        "control_formula": sha(HERE / "control.xcnf.gz"),
        "stdout": sha(HERE / "solver.stdout.txt"),
        "stderr": sha(HERE / "solver.stderr.txt")}
    output = (HERE / "solver.stdout.txt").read_text()
    statuses = [line for line in output.splitlines() if line.startswith("s ")]
    models = [line for line in output.splitlines() if line.startswith("v ")]
    restarts = [line for line in output.splitlines() if line.startswith("c rst ")]
    assert statuses == query["solver_status_lines"] == []
    assert len(models) == query["model_lines"] == 0
    assert "c Parsing time:" in output
    phases = query["phase_ns"]
    accounted = sum(phases[name] for name in
                    ("target_preimages", "target_suffix", "formula_write", "solver_search"))
    overhead = phases["charged_total"] - accounted
    assert overhead >= 0
    row = {"status": "PASS_CACHED_W16_CENSORED_QUERY_AUDIT",
           "candidate_id": None, "formula_sha256": whole.hexdigest(),
           "core_variables": core["variables"],
           "core_cnf_clauses": core["cnf_clauses"],
           "core_native_xor_rows": core["native_xor_rows"],
           "formula_variables": control["formula"]["variables"],
           "formula_cnf_clauses": clauses,
           "formula_native_xor_rows": xors,
           "solver_log_restart_lines": len(restarts),
           "solver_branch_search_observed": bool(restarts),
           "charged_unclassified_overhead_ns": overhead,
           "source_sha256": {name: sha(path) for name, path in {
               "audit": HERE / "terminal_audit.py",
               "core_result": HERE / "core_result.json",
               "control_result": HERE / "control_result.json",
               "query_protocol": HERE / "query_protocol.json",
               "query_result": HERE / "query_result.json",
               "stdout": HERE / "solver.stdout.txt",
               "stderr": HERE / "solver.stderr.txt"}.items()}}
    (HERE / "terminal_audit.json").write_text(json.dumps(row, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"status": row["status"],
                      "solver_branch_search_observed": bool(restarts),
                      "charged_unclassified_overhead_ns": overhead}))


if __name__ == "__main__":
    main()

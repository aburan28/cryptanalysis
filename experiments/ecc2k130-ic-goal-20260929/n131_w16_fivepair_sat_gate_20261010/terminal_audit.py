#!/usr/bin/env python3
"""Bind W16 support, complete control, and bounded native-XOR search."""

import gzip
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
W16 = HERE.parent / "n131_w16_w18_sixpair_width_gate_20261010"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    support = json.loads((W16 / "result.json").read_text())
    projection = json.loads((W16 / "audit_result.json").read_text())
    control_protocol = json.loads((HERE / "fivepair_protocol.json").read_text())
    control = json.loads((HERE / "fivepair_control_result.json").read_text())
    query_protocol = json.loads((HERE / "query_v2_protocol.json").read_text())
    query = json.loads((HERE / "query_v2_result.json").read_text())
    assert support["status"] == "PASS_N131_W15_W18_WIDTH_GATE"
    assert projection["status"] == "PASS_INDEPENDENT_PROJECTED_BASE_AUDIT"
    assert support["widths"][1]["actual_factor_base_B"] == 393552
    assert support["widths"][1]["folded_columns_K"] == 32675
    assert control_protocol["source_sha256"] == {
        name: sha(path) for name, path in load_control_paths().items()}
    assert query_protocol["source_sha256"] == {
        name: sha(path) for name, path in load_query_paths().items()}
    assert control["status"] == "PASS_FULL_XCNF_AND_GROUP_FIVE_PAIR_CONTROL"
    assert control["group_lift_status"] == "GROUP_LIFT_FOUND"
    assert control["full_assignment_check"] == {
        "cnf_clauses": control["formula"]["cnf_clauses"],
        "xor_rows": control["formula"]["native_xor_rows"]}
    assert control["source_sha256"]["protocol"] == sha(HERE / "fivepair_protocol.json")
    assert control["source_sha256"]["group_lift"] == sha(HERE / "fivepair_control_group_lift.json")
    assert control["formula"]["gzip_sha256"] == sha(HERE / "fivepair_control.xcnf.gz")
    digest = hashlib.sha256()
    with gzip.open(HERE / "fivepair_control.xcnf.gz", "rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    assert digest.hexdigest() == control["formula"]["sha256"]
    assert query["formula"]["sha256"] == control["formula"]["sha256"]
    assert query["status"] == "CENSORED_TIME"
    assert query["stop_reason"] == "PARENT_SAFE_STOP"
    assert query["phase_seconds"]["build_plus_search"] <= query_protocol["wall_cap_seconds"]
    assert query["sampled_peak_combined_rss_bytes"] < query_protocol["rss_cap_bytes"]
    assert query["solver_status_lines"] == [] and query["model_lines"] == 0
    assert query["source_sha256"] == {
        "protocol": sha(HERE / "query_v2_protocol.json"),
        "formula_gzip": sha(HERE / "fivepair_control.xcnf.gz"),
        "stdout": sha(HERE / "query_v2_solver.stdout.txt"),
        "stderr": sha(HERE / "query_v2_solver.stderr.txt")}
    output = (HERE / "query_v2_solver.stdout.txt").read_text()
    assert not any(line.startswith("s ") or line.startswith("v ")
                   for line in output.splitlines())
    restarts = [line for line in output.splitlines() if line.startswith("c rst ")]
    assert len(restarts) >= 1
    row = {"status": "PASS_W16_CENSORED_QUERY_ARTIFACT_AUDIT",
           "candidate_id": None, "curve_id": support["curve_id"],
           "width": 16, "factor_base_B": support["widths"][1]["actual_factor_base_B"],
           "folded_columns_K": support["widths"][1]["folded_columns_K"],
           "control_formula_sha256": digest.hexdigest(),
           "active_search_restart_lines": len(restarts),
           "last_restart_line": restarts[-1],
           "source_sha256": {name: sha(path) for name, path in {
               "audit": HERE / "terminal_audit.py",
               "support_result": W16 / "result.json",
               "projection_audit": W16 / "audit_result.json",
               "control_result": HERE / "fivepair_control_result.json",
               "query_protocol": HERE / "query_v2_protocol.json",
               "query_result": HERE / "query_v2_result.json",
               "solver_stdout": HERE / "query_v2_solver.stdout.txt",
               "solver_stderr": HERE / "query_v2_solver.stderr.txt"}.items()}}
    (HERE / "terminal_audit.json").write_text(json.dumps(row, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"status": row["status"],
                      "active_search_restart_lines": len(restarts)}))


def load_control_paths():
    run = HERE / "fivepair_run.py"
    w15 = HERE.parent / "n131_w15_coupled_sixpair_20261010"
    old = HERE.parent / "n131_w15_onepair_fixed_sat_gate_20261010"
    return {"runner": run, "circuit": HERE / "fivepair_circuit.py",
            "group_lift": HERE / "fivepair_lift.py", "input": HERE / "fivepair_input.json",
            "input_preparation": old / "prepare_fivepair.py",
            "w15_experiment": w15 / "experiment.py", "w15_circuit": w15 / "w15_circuit.py",
            "w15_support": w15 / "support_w15.tsv",
            "w16_support": W16 / "support_w16.tsv",
            "w16_width_result": W16 / "result.json",
            "w16_projection_audit": W16 / "audit_result.json",
            "w15_group_control": w15 / "control_group_lift.json",
            "runtime": HERE / "sage_runtime_info.json",
            "solver": Path("/opt/homebrew/bin/cryptominisat5")}


def load_query_paths():
    return {"query": HERE / "query_v2.py", "control_runner": HERE / "fivepair_run.py",
            "circuit": HERE / "fivepair_circuit.py", "lift": HERE / "fivepair_lift.py",
            "input": HERE / "fivepair_input.json", "control_protocol": HERE / "fivepair_protocol.json",
            "control_result": HERE / "fivepair_control_result.json",
            "control_formula": HERE / "fivepair_control.xcnf.gz",
            "control_group_lift": HERE / "fivepair_control_group_lift.json",
            "support": W16 / "support_w16.tsv", "support_audit": W16 / "audit_result.json",
            "runtime": HERE / "sage_runtime_info.json",
            "solver": Path("/opt/homebrew/bin/cryptominisat5")}


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Audit the source-identical W15 Gaussian-matrix eligibility comparison."""

import gzip
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PRIOR = HERE.parent / "n131_w15_trace_fiber_gate_20261010"
FORMULA = PRIOR / "trace_fiber.xcnf.gz"
SOLVER = Path("/opt/homebrew/bin/cryptominisat5")


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def load(path):
    return json.loads(Path(path).read_text())


def audit_row(protocol_name, result_name, runner_name, stdout_name, stderr_name,
              expected_flags, expected_statuses, expected_stop):
    protocol_path = HERE / protocol_name
    protocol = load(protocol_path)
    result = load(HERE / result_name)
    assert protocol["source_sha256"]["runner"] == sha(HERE / runner_name)
    assert protocol["source_sha256"]["runtime"] == sha(HERE / "sage_runtime_info.json")
    assert protocol["source_sha256"]["prior_formula_gzip"] == sha(FORMULA)
    assert protocol["source_sha256"]["solver"] == sha(SOLVER)
    assert result["source_sha256"]["protocol"] == sha(protocol_path)
    assert result["source_sha256"]["formula_gzip"] == sha(FORMULA)
    assert result["source_sha256"]["stdout"] == sha(HERE / stdout_name)
    assert result["source_sha256"]["stderr"] == sha(HERE / stderr_name)
    assert result["formula_sha256"] == protocol["formula_sha256"]
    assert result["target_q"] == protocol["target_q"]
    assert result["solver_command"][:-1] == [str(SOLVER), *expected_flags]
    assert result["status"] == "CENSORED_TIME"
    assert result["stop_reason"] == expected_stop
    assert result["solver_status_lines"] == expected_statuses
    assert result["model_lines"] == 0
    assert result["sampled_combined_peak_rss_bytes"] < protocol["rss_cap_bytes"]
    assert result["solver_stage_wall_seconds"] < protocol["solver_stage_cap_seconds"]
    output = (HERE / stdout_name).read_text(errors="replace")
    statuses = [line for line in output.splitlines() if line.startswith("s ")]
    restarts = [line for line in output.splitlines() if line.startswith("c rst ")]
    matrix_uses = [line for line in output.splitlines() if "[matrix] Using" in line]
    assert statuses == expected_statuses and restarts
    assert result["model_lines"] == sum(line.startswith("v ") for line in output.splitlines())
    if expected_stop == "PARENT_SAFE_STOP":
        assert result["solver_exit_code"] == -15
        assert result["solver_stage_wall_seconds"] >= protocol["parent_safe_stop_seconds"]
    else:
        assert expected_stop is None and result["solver_exit_code"] == 15
        assert expected_statuses == ["s INDETERMINATE"]
    return {"solver_stage_wall_seconds": result["solver_stage_wall_seconds"],
            "peak_rss_bytes": result["sampled_combined_peak_rss_bytes"],
            "restarts_observed": len(restarts),
            "last_logged_conflicts": restarts[-1].split()[6],
            "matrix_using_lines": matrix_uses,
            "result_sha256": sha(HERE / result_name)}


def main():
    baseline = load(PRIOR / "query_result.json")
    prior_control = load(PRIOR / "control_result.json")
    prior_audit = load(PRIOR / "terminal_audit.json")
    prior_sage = load(PRIOR / "sage_trace_audit.json")
    assert baseline["status"] == "CENSORED_TIME"
    assert prior_control["status"] == "PASS_FULL_TRACE_FIBER_XCNF_CONTROL"
    assert prior_audit["status"] == "PASS_TRACE_FIBER_TERMINAL_AUDIT"
    assert prior_sage["status"] == "PASS_INDEPENDENT_SAGE_TRACE_FIBER_AUDIT"
    with gzip.open(FORMULA, "rb") as source:
        digest = hashlib.sha256(source.read()).hexdigest()
    assert digest == baseline["formula"]["sha256"]
    assert digest == load(HERE / "protocol.json")["formula_sha256"]
    assert digest == load(HERE / "protocol_rows.json")["formula_sha256"]
    baseline_log = (PRIOR / "solver.stdout.txt").read_text(errors="replace")
    assert baseline_log.count("Too many columns in matrix: 3929") >= 5
    width_protocol = load(HERE / "protocol.json")
    rows_protocol = load(HERE / "protocol_rows.json")
    assert width_protocol["variant_flags"] == [*width_protocol["baseline_flags"],
                                                "--maxmatrixcols=4096"]
    assert rows_protocol["variant_flags"] == [*width_protocol["baseline_flags"],
                                               "--maxmatrixcols=10000",
                                               "--maxmatrixrows=4000"]
    for key, path in (("width_runner", HERE / "run.py"),
                      ("width_protocol", HERE / "protocol.json"),
                      ("width_result", HERE / "query_result.json"),
                      ("prior_control", PRIOR / "control_result.json"),
                      ("prior_sage_audit", PRIOR / "sage_trace_audit.json")):
        assert rows_protocol["source_sha256"][key] == sha(path)
    for key, path in (("prior_protocol", PRIOR / "protocol.json"),
                      ("prior_control", PRIOR / "control_result.json"),
                      ("prior_query", PRIOR / "query_result.json"),
                      ("prior_terminal_audit", PRIOR / "terminal_audit.json"),
                      ("prior_sage_audit", PRIOR / "sage_trace_audit.json")):
        assert width_protocol["source_sha256"][key] == sha(path)
    width = audit_row("protocol.json", "query_result.json", "run.py",
                      "solver.stdout.txt", "solver.stderr.txt",
                      width_protocol["variant_flags"], [], "PARENT_SAFE_STOP")
    rows = audit_row("protocol_rows.json", "query_rows_result.json", "run_rows.py",
                     "solver_rows.stdout.txt", "solver_rows.stderr.txt",
                     rows_protocol["variant_flags"], ["s INDETERMINATE"], None)
    assert any("Using 5 matrices" in line for line in width["matrix_using_lines"])
    assert any("Using 4 matrices" in line for line in rows["matrix_using_lines"])
    assert "Too many rows in matrix: 3315" in (HERE / "solver.stdout.txt").read_text()
    assert "Too many rows in matrix: 3315" not in (HERE / "solver_rows.stdout.txt").read_text()
    receipt = {
        "status": "PASS_SOURCE_IDENTICAL_GAUSS_ELIGIBILITY_AUDIT",
        "formula_sha256": digest,
        "baseline_result_sha256": sha(PRIOR / "query_result.json"),
        "width": width,
        "rows": rows,
        "audit_source_sha256": sha(__file__),
    }
    with (HERE / "terminal_audit.json").open("x") as sink:
        json.dump(receipt, sink, indent=2, sort_keys=True)
        sink.write("\n")
    print(json.dumps({"status": receipt["status"],
                      "width_conflicts": width["last_logged_conflicts"],
                      "rows_conflicts": rows["last_logged_conflicts"]}))


if __name__ == "__main__":
    main()

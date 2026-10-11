"""Audit frozen N131 W15 quartic construction, query formula, and transcript."""

import gzip
import hashlib
import json
from pathlib import Path

import run

HERE = Path(__file__).resolve().parent
GOAL = HERE.parent
PRIOR_CONTROL = GOAL / "n131_w15_unrestricted_fivepair_public_20261010/control.json"
BASELINE = GOAL / "n131_w15_unrestricted_fivepair_public_20261010/result.json"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    protocol = run.checked()
    arith = json.loads((HERE / "arith_control.json").read_text())
    fibers = json.loads((HERE / "fibers.json").read_text())
    control = json.loads((HERE / "control_result.json").read_text())
    query = json.loads((HERE / "query_result.json").read_text())
    prior = json.loads(PRIOR_CONTROL.read_text())
    baseline = json.loads(BASELINE.read_text())
    assert arith["status"] == "PASS_N131_W15_TWO_QUARTIC_CONSTRUCTED_CONTROL"
    assert [len(row["branches"]) for row in arith["blocks"]] == [1, 1]
    assert fibers["status"] == "PASS_N131_W15_TARGET_FIBER_EXTRACT"
    assert prior["group_lift_status"] == "GROUP_LIFT_FOUND"
    assert control["status"] == "PASS_N131_W15_FULL_QUARTIC_CONSTRUCTED_ASSIGNMENT"
    assert control["formula"]["clauses"] == control["assignment_check"]["clauses"]
    assert control["formula"]["native_xor_rows"] == control["assignment_check"]["native_xor_rows"]
    assert query["target"] == protocol["public_target_q"] == baseline["target_q"]
    assert query["residual_target"] == protocol["public_residual_target_q"]
    assert query["protocol_sha256"] == sha(HERE / "protocol.json")
    assert query["solver_started"]
    assert query["peak_combined_rss_bytes"] < protocol["rss_cap_bytes"] or query["status"] == "RESOURCE_CAP"
    form = query["formula"]
    for key in ("and_gates", "quartic_and_gates", "quartic_sparse_multiplications",
                "quartic_generic_multiplications", "quartic_sparse_pair_products",
                "last_pair_bilinear_ands", "target_linear_ands"):
        assert form[key] == control["formula"][key], key
    with gzip.open(HERE / "query.xcnf.gz", "rb") as stream:
        formula_bytes = stream.read()
    assert len(formula_bytes) == form["bytes"]
    assert hashlib.sha256(formula_bytes).hexdigest() == form["sha256"]
    assert formula_bytes.startswith(f"p cnf {form['variables']} ".encode())
    stdout = gzip.open(HERE / "solver.stdout.gz", "rb").read()
    stderr = gzip.open(HERE / "solver.stderr.gz", "rb").read()
    assert hashlib.sha256(stdout).hexdigest() == query["stdout_sha256"]
    assert hashlib.sha256(stderr).hexdigest() == query["stderr_sha256"]
    assert sha(HERE / "query.xcnf.gz") == query["query_xcnf_gzip_sha256"]
    phases = query["phase_seconds"]
    assert abs(phases["total"] - sum(phases[key] for key in
               ("construction", "write_and_hash", "solver"))) < 1e-5
    assert phases["total"] < protocol["construction_plus_search_cap_seconds"]
    restart_rows = [row for row in stdout.splitlines() if row.startswith(b"c rst ")]
    assert len(restart_rows) >= 1
    if query["status"] == "BOUNDED_UNKNOWN":
        assert query["solver_stop"] == "TIME_CAP" or "s INDETERMINATE" in query["solver_status_lines"]
        assert not query["model_lines"] and b"s SATISFIABLE" not in stdout
        assert b"s UNSATISFIABLE" not in stdout
    result = {"status": "PASS_N131_W15_QUARTIC_BOUNDARY_ARCHIVE",
              "query_status": query["status"], "curve_id": protocol["curve_id"],
              "public_target_q": query["target"], "candidate_id": None,
              "solver_restart_rows": len(restart_rows),
              "last_solver_restart": restart_rows[-1].decode(errors="replace"),
              "basis_aware_formula": {key: form[key] for key in
                                      ("variables", "and_gates", "clauses",
                                       "native_xor_rows", "bytes", "sha256")},
              "baseline_formula": baseline["formula"],
              "source_sha256": {name: sha(HERE / name) for name in
                                ("protocol.json", "arith_control.json",
                                 "fibers.json", "control_result.json",
                                 "query_result.json", "query.xcnf.gz",
                                 "solver.stdout.gz", "solver.stderr.gz")}}
    (HERE / "terminal_audit.json").write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"status": result["status"],
                      "query_status": query["status"],
                      "formula_bytes": form["bytes"]}, sort_keys=True))


if __name__ == "__main__":
    main()

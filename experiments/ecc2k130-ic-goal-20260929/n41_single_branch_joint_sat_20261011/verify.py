"""Rebuild the exact public formula and audit the bounded solver receipt."""

import gzip
import hashlib
import json
import tempfile
from pathlib import Path

import run

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    protocol = run.checked_protocol()
    control = json.loads((HERE / "control_result.json").read_text())
    query = json.loads((HERE / "query_result.json").read_text())
    replay = json.loads((HERE / "control_replay_result.json").read_text())
    norm = json.loads((HERE / "factor_result.json").read_text())
    coefficients = json.loads((HERE / "coefficient_result.json").read_text())
    runtime = json.loads((HERE / "sage_runtime_info.json").read_text())
    assert runtime["status"] == "verified"
    assert norm["status"] == "PASS_EXACT_COEFFICIENT_FACTORIZATION"
    assert coefficients["status"] == "PASS_EXACT_PQ_COEFFICIENT_FACTORIZATION"
    assert control["status"] == "PASS_FULL_N41_PUBLIC_WITNESS_ASSIGNMENT"
    assert replay["status"] == "PASS_VERIFIED_PUBLIC_RELATION"
    assert len(replay["verified_relations"]) == 1
    assert replay["target"] == query["target"] == protocol["target_q"]
    assert query["status"] == "BOUNDED_UNKNOWN"
    assert query["solver_started"] and query["solver_timed_out"]
    assert not query["solver_rss_exceeded"] and not query["primary_model_saved"]
    assert query["peak_combined_rss_bytes"] < protocol["rss_cap_bytes"]
    phases = query["phase_seconds"]
    assert abs(phases["total"] - sum(phases[key] for key in
               ("construction", "write_and_hash", "solver"))) < 1e-6
    stdout = gzip.open(HERE / "solver.stdout.gz", "rb").read()
    stderr = gzip.open(HERE / "solver.stderr.gz", "rb").read()
    assert hashlib.sha256(stdout).hexdigest() == query["stdout_sha256"]
    assert hashlib.sha256(stderr).hexdigest() == query["stderr_sha256"]
    assert sha(HERE / "solver.stdout.gz") == query["stdout_gzip_sha256"]
    assert sha(HERE / "solver.stderr.gz") == query["stderr_gzip_sha256"]
    assert b"c rst " in stdout and b"s SATISFIABLE" not in stdout
    assert b"s UNSATISFIABLE" not in stdout
    circuit, meta, _ = run.build()
    with tempfile.NamedTemporaryFile(suffix=".xcnf", dir="/private/tmp") as stream:
        formula = Path(stream.name)
        circuit.write(formula)
        assert sha(formula) == query["formula"]["sha256"]
        assert formula.stat().st_size == query["formula"]["bytes"]
    for key, actual in (("variables", circuit.next_var - 1),
                        ("and_gates", circuit.and_count),
                        ("clauses", len(circuit.clauses)),
                        ("native_xor_rows", len(circuit.xors)),
                        ("quartic_field_multiplications", meta["quartic_field_multiplications"])):
        assert actual == query["formula"][key] == control["formula"][key], key
    result = {"status": "PASS_EXACT_BOUNDED_QUERY_ARCHIVE",
              "formula_sha256": query["formula"]["sha256"],
              "solver_status": query["status"],
              "solver_log_activity": "restart rows observed; no SAT or UNSAT terminal line",
              "public_positive_assignment": control["status"],
              "independent_positive_group_replay": replay["status"],
              "input_sha256": {name: sha(HERE / name) for name in
                               ("protocol.json", "control_result.json",
                                "query_result.json", "control_replay_result.json",
                                "factor_result.json", "coefficient_result.json",
                                "sage_runtime_info.json", "solver.stdout.gz",
                                "solver.stderr.gz")}}
    (HERE / "terminal_audit.json").write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"status": result["status"],
                      "formula_sha256": result["formula_sha256"]}, sort_keys=True))


if __name__ == "__main__":
    main()

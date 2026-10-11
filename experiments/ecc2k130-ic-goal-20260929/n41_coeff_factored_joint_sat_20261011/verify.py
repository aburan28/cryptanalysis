"""Audit the paired factored and unfactored N41 public-query records."""

import gzip
import hashlib
import json
import tempfile
from pathlib import Path

import run

HERE = Path(__file__).resolve().parent
OLD = HERE.parent / "n41_single_branch_joint_sat_20261011"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    protocol = run.base.checked_protocol()
    control = json.loads((HERE / "control_result.json").read_text())
    replay = json.loads((HERE / "control_replay_result.json").read_text())
    arithmetic = json.loads((HERE / "arith_replay.json").read_text())
    query = json.loads((HERE / "query_result.json").read_text())
    baseline = json.loads((OLD / "query_result.json").read_text())
    assert protocol["target_q"] == query["target"] == baseline["target"]
    assert control["status"] == "PASS_FULL_N41_PUBLIC_WITNESS_ASSIGNMENT"
    assert replay["status"] == "PASS_VERIFIED_PUBLIC_RELATION"
    assert arithmetic["status"] == "PASS_FACTORED_BOOLEAN_COEFFICIENT_REPLAY"
    assert query["status"] == baseline["status"] == "BOUNDED_UNKNOWN"
    assert query["solver_started"] and query["solver_timed_out"]
    assert not query["solver_rss_exceeded"] and not query["primary_model_saved"]
    assert query["peak_combined_rss_bytes"] < protocol["rss_cap_bytes"]
    phases = query["phase_seconds"]
    assert abs(phases["total"] - sum(phases[k] for k in
               ("construction", "write_and_hash", "solver"))) < 1e-6
    stdout = gzip.open(HERE / "solver.stdout.gz", "rb").read()
    stderr = gzip.open(HERE / "solver.stderr.gz", "rb").read()
    assert hashlib.sha256(stdout).hexdigest() == query["stdout_sha256"]
    assert hashlib.sha256(stderr).hexdigest() == query["stderr_sha256"]
    assert sha(HERE / "solver.stdout.gz") == query["stdout_gzip_sha256"]
    assert sha(HERE / "solver.stderr.gz") == query["stderr_gzip_sha256"]
    assert b"c rst " in stdout and b"s SATISFIABLE" not in stdout
    assert b"s UNSATISFIABLE" not in stdout
    circuit, meta, _ = run.base.build()
    with tempfile.NamedTemporaryFile(suffix=".xcnf", dir="/private/tmp") as stream:
        formula = Path(stream.name)
        circuit.write(formula)
        assert sha(formula) == query["formula"]["sha256"]
        assert formula.stat().st_size == query["formula"]["bytes"]
    for key, value in (("variables", circuit.next_var - 1),
                       ("and_gates", circuit.and_count),
                       ("clauses", len(circuit.clauses)),
                       ("native_xor_rows", len(circuit.xors)),
                       ("quartic_field_multiplications", meta["quartic_field_multiplications"])):
        assert query["formula"][key] == control["formula"][key] == value
    assert query["formula"]["and_gates"] < baseline["formula"]["and_gates"]
    assert query["formula"]["quartic_field_multiplications"] < baseline["formula"]["quartic_field_multiplications"]
    result = {"status": "PASS_PAIRED_FACTORED_N41_BOUNDARY_ARCHIVE",
              "target": query["target"], "query_status": query["status"],
              "formula_sha256": query["formula"]["sha256"],
              "factored_and_gates": query["formula"]["and_gates"],
              "baseline_and_gates": baseline["formula"]["and_gates"],
              "factored_field_multiplications": query["formula"]["quartic_field_multiplications"],
              "baseline_field_multiplications": baseline["formula"]["quartic_field_multiplications"],
              "positive_assignment": control["status"],
              "independent_group_replay": replay["status"],
              "input_sha256": {name: sha(HERE / name) for name in
                               ("protocol.json", "control_result.json",
                                "control_replay_result.json", "arith_replay.json",
                                "query_result.json", "solver.stdout.gz",
                                "solver.stderr.gz")}}
    (HERE / "terminal_audit.json").write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"status": result["status"],
                      "factored_and_gates": result["factored_and_gates"]}, sort_keys=True))


if __name__ == "__main__":
    main()

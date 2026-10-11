"""Audit frozen inputs, exact formula, controls, and bounded solver receipt."""

import gzip
import hashlib
import json
import tempfile
from pathlib import Path

import run

HERE = Path(__file__).resolve().parent


def main():
    protocol = run.base.checked_protocol()
    control = json.loads((HERE / "control_result.json").read_text())
    query = json.loads((HERE / "query_result.json").read_text())
    audit = json.loads((HERE / "audit_result.json").read_text())
    assert protocol["candidate_id"] is None
    assert control["status"] == "PASS_FULL_N41_PUBLIC_WITNESS_ASSIGNMENT"
    assert audit["status"] == "PASS_ALL_N41_SOURCE_PAIR_S3"
    assert audit["pairs_checked"] == 5952
    assert audit["arbitrary_triples_checked"] == 1000
    assert query["status"] == "BOUNDED_UNKNOWN"
    assert query["solver_started"] and query["solver_timed_out"]
    assert not query["solver_rss_exceeded"]
    assert query["target"] == control["target"] == protocol["target_q"]
    assert query["source_sha256"]["protocol.json"] == run.base.sha(HERE / "protocol.json")
    circuit, meta, elapsed = run.base.build()
    with tempfile.NamedTemporaryFile(suffix=".xcnf", dir="/private/tmp") as stream:
        formula = Path(stream.name)
        circuit.write(formula)
        assert formula.stat().st_size == query["formula"]["bytes"]
        assert run.base.sha(formula) == query["formula"]["sha256"]
    for key in ("variables", "and_gates", "clauses", "native_xor_rows",
                "column_and_order_forbids", "pair_and_gates", "joint_link_and_gates"):
        assert query["formula"][key] == control["formula"][key]
    phases = query["phase_seconds"]
    assert abs(sum(phases[key] for key in ("construction", "write_and_hash", "solver"))
               - phases["total"]) < 0.01
    stdout = gzip.open(HERE / "solver.stdout.gz", "rb").read()
    stderr = gzip.open(HERE / "solver.stderr.gz", "rb").read()
    assert hashlib.sha256(stdout).hexdigest() == query["stdout_sha256"]
    assert hashlib.sha256(stderr).hexdigest() == query["stderr_sha256"]
    assert run.base.sha(HERE / "solver.stdout.gz") == query["stdout_gzip_sha256"]
    assert run.base.sha(HERE / "solver.stderr.gz") == query["stderr_gzip_sha256"]
    assert b"c rst " in stdout and b"s SATISFIABLE" not in stdout
    assert b"s UNSATISFIABLE" not in stdout and not stderr
    result = {"status": "PASS", "formula_sha256": query["formula"]["sha256"],
              "formula_bytes": query["formula"]["bytes"],
              "and_gates": query["formula"]["and_gates"],
              "source_pairs_checked": audit["pairs_checked"],
              "solver_status": query["status"],
              "solver_restart_lines": stdout.count(b"c rst "),
              "source_sha256": {"protocol.json": run.base.sha(HERE / "protocol.json"),
                                "query_result.json": run.base.sha(HERE / "query_result.json")}}
    (HERE / "terminal_audit.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()

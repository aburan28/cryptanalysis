"""Bind the W18 cutoff-one construction, positive audit, and capped control."""

import gzip
import hashlib
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024*1024), b""):
            h.update(block)
    return h.hexdigest()


def unpacked_digest(path):
    h = hashlib.sha256()
    with gzip.open(path, "rb") as source:
        for block in iter(lambda: source.read(1024*1024), b""):
            h.update(block)
    return h.hexdigest()


def main():
    names = ("terminal_audit.py", "formula_protocol.json", "ir_protocol.json",
             "ir_result.json", "four_constructed_build.json",
             "four_unpinned_constructed_build.json", "four_constructed.xcnf.gz",
             "four_unpinned_constructed.xcnf.gz", "constructed_audit_protocol.json",
             "constructed_audit_result.json", "unpinned_audit_protocol.json",
             "unpinned_audit_result.json", "solver_protocol.json",
             "constructed_solver_result.json", "unpinned_constructed_solver_result.json",
             "constructed_solver.stdout.txt", "constructed_solver.stderr.txt",
             "unpinned_constructed_solver.stdout.txt", "unpinned_constructed_solver.stderr.txt")
    paths = {name: HERE / name for name in names}
    protocol = json.loads((HERE / "terminal_protocol.json").read_text())
    assert protocol["source_sha256"] == {name: digest(path) for name, path in paths.items()}
    result = json.loads(paths["ir_result.json"].read_text())
    assert result["status"] == "PASS_W18_CUTOFF_GATE_CENSUS"
    assert [(row["cutoff"], row["live_and_gates"], row["live_xor_gates"])
            for row in result["rows"]] == [(1, 64272, 404731), (3, 94851, 295002)]
    for mode in ("constructed", "unpinned_constructed"):
        build = json.loads(paths["four_%s_build.json" % mode].read_text())
        assert unpacked_digest(paths["four_%s.xcnf.gz" % mode]) == build["xcnf"]["sha256"]
        run = json.loads(paths["%s_solver_result.json" % mode].read_text())
        assert run["stdout_sha256"] == digest(paths["%s_solver.stdout.txt" % mode])
        assert run["stderr_sha256"] == digest(paths["%s_solver.stderr.txt" % mode])
    constructed = json.loads(paths["constructed_solver_result.json"].read_text())
    assert constructed["status"] == "SAT_MODEL_UNAUDITED"
    assert json.loads(paths["constructed_audit_result.json"].read_text())["status"] == \
        "PASS_INDEPENDENT_FOUR_PREIMAGE_CONSTRUCTED_MODEL"
    assert json.loads(paths["unpinned_audit_result.json"].read_text())["status"] == \
        "PASS_EXACT_WITNESS_PIN_REMOVAL"
    unpinned = json.loads(paths["unpinned_constructed_solver_result.json"].read_text())
    assert unpinned["status"] == "PARENT_TIMEOUT" and unpinned["exit_code"] == -9
    log = paths["unpinned_constructed_solver.stdout.txt"].read_text()
    restarts = [line for line in log.splitlines() if re.match(r"^c rst\s", line)]
    assert restarts and not re.search(r"^s (?:UNSATISFIABLE|SATISFIABLE)$", log, re.M)
    assert paths["unpinned_constructed_solver.stderr.txt"].stat().st_size == 0
    audit = {"status": "PASS_CUTOFF_ONE_TERMINAL_AUDIT",
             "cutoff_one_live_and_gates": 64272,
             "cutoff_three_live_and_gates": 94851,
             "cutoff_one_live_xor_gates": 404731,
             "cutoff_three_live_xor_gates": 295002,
             "constructed_model_audited": True,
             "unpinned_known_satisfiable": True,
             "unpinned_run_status": unpinned["status"],
             "unpinned_parent_wall_ns": unpinned["wall_ns"],
             "logged_search_restart_lines": len(restarts),
             "last_restart_line": restarts[-1],
             "source_sha256": protocol["source_sha256"],
             "protocol_sha256": digest(HERE / "terminal_protocol.json")}
    (HERE / "terminal_result.json").write_text(json.dumps(audit, indent=2, sort_keys=True)+"\n")
    print(json.dumps({"status": audit["status"],
                      "logged_search_restart_lines": len(restarts)}))


if __name__ == "__main__":
    main()

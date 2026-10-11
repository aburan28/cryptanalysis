"""Check frozen quartic formula, positive witness, and bounded search receipt."""

import json
import re
from pathlib import Path

import build

HERE = Path(__file__).resolve().parent


def main():
    protocol = json.loads((HERE / "protocol.json").read_text())
    build_result = json.loads((HERE / "factor0_build.json").read_text())
    witness_audit = json.loads((HERE / "audit_result.json").read_text())
    solver_protocol = json.loads((HERE / "solver_protocol.json").read_text())
    solver_result = json.loads((HERE / "solver_result.json").read_text())
    assert protocol["source_sha256"]["build"] == build.sha(HERE / "build.py")
    assert build_result["source_sha256"]["build.py"] == build.sha(HERE / "build.py")
    assert build_result["formula_gzip_sha256"] == build.sha(HERE / "factor0.xcnf.gz")
    assert witness_audit["status"] == "PASS_FULL_POSITIVE_QUARTIC_XCNF_ASSIGNMENT"
    assert witness_audit["formula_gzip_sha256"] == build_result["formula_gzip_sha256"]
    paths = {"script": HERE / "run_solver.py",
             "solver": Path("/opt/homebrew/bin/cryptominisat5"),
             "formula": HERE / "factor0.xcnf.gz",
             "build": HERE / "factor0_build.json",
             "audit": HERE / "audit_result.json"}
    assert solver_protocol["source_sha256"] == {name: build.sha(path)
                                                    for name, path in paths.items()}
    assert solver_result["protocol_sha256"] == build.sha(HERE / "solver_protocol.json")
    stdout = (HERE / "solver.stdout.txt").read_text()
    stderr = (HERE / "solver.stderr.txt").read_text()
    assert solver_result["stdout_sha256"] == build.sha(HERE / "solver.stdout.txt")
    assert solver_result["stderr_sha256"] == build.sha(HERE / "solver.stderr.txt")
    assert solver_result["status"] == "PARENT_TIMEOUT"
    assert solver_result["peak_child_rss_bytes"] < solver_protocol["rss_cap_bytes"]
    assert solver_result["solver_wall_ns"] >= solver_protocol["parent_cap_seconds"] * 10**9
    restarts = re.findall(r"^c rst .*?\s+(\d+)\s+\d+[KMG]?\s+", stdout, re.M)
    assert len(restarts) >= 10 and int(restarts[-1]) >= 10
    assert not re.search(r"^s (?:SATISFIABLE|UNSATISFIABLE)", stdout, re.M)
    assert not re.search(r"^v [\d\s-]+0$", stdout, re.M)
    assert not stderr.strip()
    result = {"status": "PASS_QUARTIC_SAT_TERMINAL_AUDIT",
              "positive_witness": witness_audit["status"],
              "solver_status": solver_result["status"],
              "logged_restart_lines": len(restarts),
              "last_logged_restart": int(restarts[-1]),
              "model_or_proof": False,
              "source_sha256": {"terminal_audit.py": build.sha(__file__),
                                "protocol.json": build.sha(HERE / "protocol.json"),
                                "solver_protocol.json": build.sha(HERE / "solver_protocol.json"),
                                "solver_result.json": build.sha(HERE / "solver_result.json")}}
    (HERE / "terminal_result.json").write_text(json.dumps(result, indent=2, sort_keys=True)+"\n")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()

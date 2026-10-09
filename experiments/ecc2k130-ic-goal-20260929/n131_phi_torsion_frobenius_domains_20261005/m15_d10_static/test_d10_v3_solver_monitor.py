#!/usr/bin/env python3
"""Exercise the v3 parent/child RSS guard on a satisfiable CNF control."""

import hashlib
import json
import subprocess
from pathlib import Path

import run_d10_m15_single_target as runner

HERE = Path(__file__).resolve().parent
OUT = HERE / "v3_solver_monitor_control"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    if OUT.exists():
        raise FileExistsError(OUT)
    OUT.mkdir()
    runtime = subprocess.run([str(runner.ROOT / "sage"), "--runtime-info"],
                             check=True, capture_output=True, text=True).stdout
    (OUT / "sage_runtime_info.json").write_text(runtime)
    assert json.loads(runtime)["status"] == "verified"
    formula = runner.gate.RecordingCnf()
    variable = formula.newVar()
    formula.addClause([variable])
    result = runner.run_measured_solver(formula, OUT, 2026100603, 15)
    if (result["status"] is not True or result["stop_reason"] is not None or
            result["returncode"] not in (0, 10) or
            result["combined_peak_rss_bytes"] <= 0 or
            variable not in result["model"]):
        raise ValueError("v3 solver/RSS monitor control did not pass")
    receipt = {
        "status": "PASS",
        "scope": "small satisfiable formula, checking solver launch, monitored RSS, output drain, and complete assignment",
        "solver_result": result,
        "source_sha256": {"runner": sha(runner.__file__),
                          "solver": sha(runner.SOLVER),
                          "test": sha(Path(__file__)),
                          "runtime": sha(OUT / "sage_runtime_info.json")},
    }
    (OUT / "receipt.json").write_text(json.dumps(receipt, sort_keys=True,
                                                   indent=2) + "\n")
    print(json.dumps({"status": "PASS", "combined_peak_rss_bytes":
                      result["combined_peak_rss_bytes"]}))


if __name__ == "__main__":
    main()

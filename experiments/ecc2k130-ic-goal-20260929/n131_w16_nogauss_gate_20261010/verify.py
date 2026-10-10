#!/usr/bin/env python3
"""Audit a one-flag no-Gauss replay of the frozen W16 XCNF."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent / "n131_w16_cached_fivepair_20261010"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    protocol = json.loads((HERE / "protocol.json").read_text())
    result = json.loads((HERE / "result.json").read_text())
    control = json.loads((BASE / "control_result.json").read_text())
    prior = json.loads((BASE / "query_result.json").read_text())
    assert protocol["status"] == "FROZEN_BEFORE_W16_NO_GAUSS_GATE"
    assert protocol["source_sha256"] == {name: sha(path) for name, path in {
        "runner": HERE / "run.py",
        "formula_gzip": BASE / "control.xcnf.gz",
        "control_result": BASE / "control_result.json",
        "prior_query_result": BASE / "query_result.json",
        "prior_query_protocol": BASE / "query_protocol.json",
        "runtime": HERE / "sage_runtime_info.json",
        "solver": Path("/opt/homebrew/bin/cryptominisat5")}.items()}
    assert control["status"] == "PASS_CACHED_W16_FULL_XCNF_AND_GROUP_CONTROL"
    assert protocol["formula_sha256"] == control["formula"]["sha256"]
    assert result["formula_sha256"] == protocol["formula_sha256"]
    assert protocol["solver_flags"] == prior["solver_command"][1:-1] + [
        "--maxnummatrices=0"]
    assert result["status"] == "CENSORED_TIME"
    assert result["stop_reason"] == "PARENT_SAFE_STOP"
    assert result["phase_ns"]["solver_subprocess"] <= protocol["parent_cap_seconds"]*10**9
    assert result["sampled_peak_combined_rss_bytes"] < protocol["rss_cap_bytes"]
    assert result["source_sha256"] == {
        "protocol": sha(HERE / "protocol.json"),
        "stdout": sha(HERE / "solver.stdout.txt"),
        "stderr": sha(HERE / "solver.stderr.txt")}
    stdout = (HERE / "solver.stdout.txt").read_text()
    assert "c -- xor clauses added: 34600" in stdout
    statuses = [line for line in stdout.splitlines() if line.startswith("s ")]
    models = [line for line in stdout.splitlines() if line.startswith("v ")]
    restarts = [line for line in stdout.splitlines() if line.startswith("c rst ")]
    assert statuses == result["solver_status_lines"] == []
    assert len(models) == result["model_lines"] == 0
    assert len(restarts) == result["restart_lines"] == 0
    audit = {"status": "PASS_W16_NO_GAUSS_CENSORED_ARTIFACT_AUDIT",
             "candidate_id": None, "formula_sha256": protocol["formula_sha256"],
             "only_flag_change": "--maxnummatrices=0",
             "branch_search_observed": False,
             "source_sha256": {name: sha(path) for name, path in {
                 "audit": HERE / "verify.py", "protocol": HERE / "protocol.json",
                 "result": HERE / "result.json", "stdout": HERE / "solver.stdout.txt",
                 "stderr": HERE / "solver.stderr.txt"}.items()}}
    (HERE / "audit.json").write_text(json.dumps(audit, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"status": audit["status"]}))


if __name__ == "__main__":
    main()

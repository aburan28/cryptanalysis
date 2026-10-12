#!/usr/bin/env python3
"""Replay Q1523 receipt, input, binary, and solver-output checks."""
from __future__ import annotations

import json
import re
from pathlib import Path

import run


def main() -> None:
    assert run.sha(run.SOLVER) == run.EXPECTED_SOLVER
    assert run.sha(run.SOURCE) == run.EXPECTED_SOURCE
    checked = []
    for directory in sorted((run.HERE / "runs").iterdir()):
        receipt = json.loads((directory / "receipt.json").read_text())
        input_name, option_name = receipt["input"], receipt["option"]
        assert directory.name == f"{input_name}_{option_name}"
        n, complement, filename, digest = run.INPUTS[input_name]
        assert run.sha(run.PARENT / filename) == digest == receipt["input_sha256"]
        assert receipt["source_sha256"] == run.EXPECTED_SOURCE
        assert receipt["solver_sha256"] == run.EXPECTED_SOLVER
        assert receipt["candidate_id"] is None and receipt["isogeny"] == "none"
        assert receipt["cpu_cap_seconds"] == run.CPU_CAP
        assert receipt["wall_cap_seconds"] == run.WALL_CAP
        assert receipt["conflict_cap"] == run.CONFLICT_CAP
        assert receipt["command"][-1] == str(run.PARENT / filename)
        assert receipt["command"][9:-1] == run.OPTIONS[option_name]
        stdout_path, stderr_path = directory / "stdout.txt", directory / "stderr.txt"
        assert run.sha(stdout_path) == receipt["stdout_sha256"]
        assert run.sha(stderr_path) == receipt["stderr_sha256"]
        stdout = stdout_path.read_text()
        conflicts = re.findall(r"^c conflicts\s*:\s*([0-9]+)", stdout, re.I | re.M)
        final_conflicts = int(conflicts[-1]) if conflicts else None
        assert receipt["reported_conflicts_last"] == final_conflicts
        if receipt["status"] == "SAT_VERIFIED":
            formula, raw, leaves, onb = run.parent.build(n, complement)
            assignment = run.parent.parse_assignment(stdout, formula.variables)
            assert run.parent.verify(formula, raw, leaves, onb, complement, assignment) == receipt["verification"]
        else:
            assert receipt["verification"] is None
            assert "s SATISFIABLE" not in stdout
        if receipt["status"] == "INDETERMINATE":
            assert "s INDETERMINATE" in stdout
        if receipt["status"] == "WALL_CAP":
            assert receipt["return_code"] is None
        checked.append((directory.name, receipt["status"], final_conflicts))
    assert checked
    print(json.dumps(checked, indent=2))


if __name__ == "__main__":
    main()

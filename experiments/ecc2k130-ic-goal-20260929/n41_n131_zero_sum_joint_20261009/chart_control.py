#!/usr/bin/env python3
"""Freeze and solve an all-chart-pinned correctness control for the joint circuit."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time

from run import CMS, model_bits, verify_formula

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build():
    formula = HERE / "chart_control.xcnf"
    protocol = HERE / "chart_protocol.json"
    if formula.exists() or protocol.exists():
        raise FileExistsError("preserve previous chart control")
    source = HERE / "control.xcnf"
    chart = json.loads((HERE / "witness_chart.json").read_text())
    wiring = json.loads((HERE / "control_build.json").read_text())
    assert chart["status"] == "PASS_EXACT_ALGEBRAIC_CHART"
    assert wiring["sha256"]["xcnf"] == sha(source)
    assignments = []
    for wires, value in zip(wiring["block_output_wire_rows"], chart["block_u"]):
        assignments.extend((wire, (value >> i) & 1)
                           for i, wire in enumerate(wires))
    for wires, value in zip(wiring["middle_wire_rows"], chart["middle_u"]):
        assignments.extend((wire, (value >> i) & 1)
                           for i, wire in enumerate(wires))
    assignments.extend((wire, i == chart["target_fiber_index"])
                       for i, wire in enumerate(wiring["target_flag_wires"]))
    original = source.read_text().splitlines()
    header = original[0].split()
    assert header[:2] == ["p", "cnf"]
    variable_count = int(header[2])
    clause_count = int(header[3])
    assert len(assignments) == 4*41 + 2*41 + 4
    assert len({wire for wire, _ in assignments}) == len(assignments)
    header[3] = str(clause_count + len(assignments))
    with formula.open("w") as handle:
        handle.write(" ".join(header) + "\n")
        handle.write("\n".join(original[1:]) + "\n")
        for wire, bit in assignments:
            handle.write(f"{wire if bit else -wire} 0\n")
    files = {"source": "chart_control.py", "runner": "run.py",
             "control_formula": "control.xcnf",
             "control_build": "control_build.json",
             "witness_chart": "witness_chart.json",
             "formula": "chart_control.xcnf"}
    receipt = {"status": "FROZEN_CHART_CONTROL",
               "proposal_id": "Q20261009200400", "candidate_id": None,
               "pinned_field_bits": len(assignments),
               "formula_variables": variable_count,
               "formula_constraints": clause_count + len(assignments),
               "limit_seconds": 30,
               "files": files,
               "sha256": {key: sha(HERE / name) for key, name in files.items()} |
                         {"cms_binary": sha(CMS)}}
    protocol.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": receipt["status"],
                      "pinned_field_bits": len(assignments),
                      "formula_sha256": sha(formula)}, sort_keys=True))


def run():
    output = HERE / "chart_control"
    if output.exists():
        raise FileExistsError(output)
    protocol = json.loads((HERE / "chart_protocol.json").read_text())
    assert protocol["status"] == "FROZEN_CHART_CONTROL"
    assert all(protocol["sha256"][key] == sha(HERE / name)
               for key, name in protocol["files"].items())
    assert protocol["sha256"]["cms_binary"] == sha(CMS)
    output.mkdir()
    command = [str(CMS), "--threads=1", "--verb=1", "--printsol=1",
               "--maxtime=30", str(HERE / "chart_control.xcnf")]
    start = time.monotonic_ns()
    try:
        completed = subprocess.run(command, capture_output=True, timeout=35)
        timed_out = False
    except subprocess.TimeoutExpired as error:
        completed = error
        timed_out = True
    wall = time.monotonic_ns() - start
    stdout = completed.stdout or b""
    stderr = completed.stderr or b""
    (output / "stdout.txt").write_bytes(stdout)
    (output / "stderr.txt").write_bytes(stderr)
    status_lines = [line for line in stdout.decode(errors="replace").splitlines()
                    if line.startswith("s ")]
    checked = None
    if not timed_out and "s SATISFIABLE" in status_lines:
        try:
            bits = model_bits(stdout.decode(errors="replace"),
                              protocol["formula_variables"])
            valid, checked = verify_formula(HERE / "chart_control.xcnf", bits)
            status = "SAT_MODEL_PASS" if valid else "MODEL_CHECK_FAILED"
            if valid:
                (output / "model_bits.txt").write_text(bits + "\n")
        except (AssertionError, ValueError) as error:
            status = "MODEL_CHECK_FAILED"
            checked = {"error": str(error)}
    elif not timed_out and "s UNSATISFIABLE" in status_lines:
        status = "UNSAT"
    else:
        status = "BOUNDED_UNKNOWN"
    receipt = {"status": status, "timed_out": timed_out,
               "returncode": None if timed_out else completed.returncode,
               "wall_ns": wall, "status_lines": status_lines,
               "formula_assignment_check": checked,
               "sha256": {"protocol": sha(HERE / "chart_protocol.json"),
                          "formula": sha(HERE / "chart_control.xcnf"),
                          "stdout": sha(output / "stdout.txt"),
                          "stderr": sha(output / "stderr.txt")}}
    if (output / "model_bits.txt").exists():
        receipt["sha256"]["model_bits"] = sha(output / "model_bits.txt")
    (output / "result.json").write_text(json.dumps(receipt, indent=2,
                                                 sort_keys=True) + "\n")
    print(json.dumps({"status": status, "wall_ns": wall,
                      "formula_assignment_check": checked}, sort_keys=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("build", "run"))
    action = parser.parse_args().action
    build() if action == "build" else run()

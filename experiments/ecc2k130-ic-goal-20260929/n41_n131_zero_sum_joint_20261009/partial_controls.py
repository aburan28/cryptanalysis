#!/usr/bin/env python3
"""Freeze and run chart-partition controls for the implicit N41 formula."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time

from run import CMS, model_bits, verify_formula

HERE = Path(__file__).resolve().parent
MODES = {"blocks": "block_output_wire_rows", "middle": "middle_wire_rows"}
VALUES = {"blocks": "block_u", "middle": "middle_u"}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def paths(mode):
    return (HERE / f"{mode}_control.xcnf",
            HERE / f"{mode}_protocol.json",
            HERE / f"{mode}_control")


def build(mode):
    formula, protocol_path, output = paths(mode)
    if any(path.exists() for path in (formula, protocol_path, output)):
        raise FileExistsError("preserve the earlier partial-control instance")
    source = HERE / "control.xcnf"
    chart = json.loads((HERE / "witness_chart.json").read_text())
    wiring = json.loads((HERE / "control_build.json").read_text())
    assert chart["status"] == "PASS_EXACT_ALGEBRAIC_CHART"
    assert wiring["sha256"]["xcnf"] == sha(source)
    assignments = [(wire, bool((value >> i) & 1))
                   for wires, value in zip(wiring[MODES[mode]], chart[VALUES[mode]])
                   for i, wire in enumerate(wires)]
    expected = 4*41 if mode == "blocks" else 2*41
    assert len(assignments) == expected
    lines = source.read_text().splitlines()
    header = lines[0].split()
    assert header[:2] == ["p", "cnf"]
    header[3] = str(int(header[3]) + len(assignments))
    with formula.open("w") as handle:
        handle.write(" ".join(header) + "\n")
        handle.write("\n".join(lines[1:]) + "\n")
        handle.writelines(f"{wire if bit else -wire} 0\n"
                          for wire, bit in assignments)
    files = {"source": "partial_controls.py", "runner": "run.py",
             "control_formula": "control.xcnf",
             "control_build": "control_build.json",
             "witness_chart": "witness_chart.json",
             "formula": formula.name}
    protocol = {"status": "FROZEN_PARTIAL_CONTROL",
                "proposal_id": "Q20261009200400", "candidate_id": None,
                "mode": mode, "pinned_field_bits": len(assignments),
                "formula_variables": int(header[2]),
                "limit_seconds": 30,
                "files": files,
                "sha256": {key: sha(HERE / name) for key, name in files.items()} |
                          {"cms_binary": sha(CMS)}}
    protocol_path.write_text(json.dumps(protocol, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": protocol["status"], "mode": mode,
                      "pinned_field_bits": len(assignments),
                      "formula_sha256": sha(formula)}, sort_keys=True))


def run(mode):
    formula, protocol_path, output = paths(mode)
    if output.exists():
        raise FileExistsError(output)
    protocol = json.loads(protocol_path.read_text())
    assert protocol["status"] == "FROZEN_PARTIAL_CONTROL"
    assert all(protocol["sha256"][key] == sha(HERE / name)
               for key, name in protocol["files"].items())
    assert protocol["sha256"]["cms_binary"] == sha(CMS)
    output.mkdir()
    command = [str(CMS), "--threads=1", "--verb=1", "--printsol=1",
               "--maxtime=30", str(formula)]
    started = time.monotonic_ns()
    try:
        completed = subprocess.run(command, capture_output=True, timeout=35)
        timed_out = False
    except subprocess.TimeoutExpired as error:
        completed = error
        timed_out = True
    wall_ns = time.monotonic_ns() - started
    stdout = completed.stdout or b""
    stderr = completed.stderr or b""
    (output / "stdout.txt").write_bytes(stdout)
    (output / "stderr.txt").write_bytes(stderr)
    statuses = [line for line in stdout.decode(errors="replace").splitlines()
                if line.startswith("s ")]
    checked = None
    if not timed_out and "s SATISFIABLE" in statuses:
        try:
            bits = model_bits(stdout.decode(errors="replace"),
                              protocol["formula_variables"])
            valid, checked = verify_formula(formula, bits)
            status = "SAT_MODEL_PASS" if valid else "MODEL_CHECK_FAILED"
            if valid:
                (output / "model_bits.txt").write_text(bits + "\n")
        except (AssertionError, ValueError) as error:
            status = "MODEL_CHECK_FAILED"
            checked = {"error": str(error)}
    elif not timed_out and "s UNSATISFIABLE" in statuses:
        status = "UNSAT"
    else:
        status = "BOUNDED_UNKNOWN"
    receipt = {"status": status, "mode": mode,
               "timed_out": timed_out,
               "returncode": None if timed_out else completed.returncode,
               "wall_ns": wall_ns,
               "status_lines": statuses,
               "formula_assignment_check": checked,
               "sha256": {"protocol": sha(protocol_path),
                          "formula": sha(formula),
                          "stdout": sha(output / "stdout.txt"),
                          "stderr": sha(output / "stderr.txt")}}
    if (output / "model_bits.txt").exists():
        receipt["sha256"]["model_bits"] = sha(output / "model_bits.txt")
    (output / "result.json").write_text(json.dumps(receipt, indent=2,
                                                 sort_keys=True) + "\n")
    print(json.dumps({"status": status, "mode": mode,
                      "wall_ns": wall_ns,
                      "formula_assignment_check": checked}, sort_keys=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("build", "run"))
    parser.add_argument("mode", choices=tuple(MODES))
    args = parser.parse_args()
    build(args.mode) if args.action == "build" else run(args.mode)

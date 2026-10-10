#!/usr/bin/env python3
"""Check S5 target propagation after fixing only the four block outputs."""

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
    formula = HERE / "s5_blocks_control.xcnf"
    protocol_path = HERE / "s5_blocks_protocol.json"
    if formula.exists() or protocol_path.exists():
        raise FileExistsError("preserve previous block-output control")
    chart = json.loads((HERE / "witness_chart.json").read_text())
    control = json.loads((HERE / "s5_control_build.json").read_text())
    assert chart["status"] == "PASS_EXACT_ALGEBRAIC_CHART"
    assert control["sha256"]["formula"] == sha(HERE / "s5_control.xcnf")
    assignments = [(wire, bool((value >> i) & 1))
                   for wires, value in zip(control["block_output_wire_rows"],
                                           chart["block_u"])
                   for i, wire in enumerate(wires)]
    assert len(assignments) == 4*41
    lines = (HERE / "s5_control.xcnf").read_text().splitlines()
    header = lines[0].split()
    assert header[:2] == ["p", "cnf"]
    header[3] = str(int(header[3]) + len(assignments))
    with formula.open("w") as handle:
        handle.write(" ".join(header) + "\n")
        handle.write("\n".join(lines[1:]) + "\n")
        handle.writelines(f"{wire if bit else -wire} 0\n"
                          for wire, bit in assignments)
    files = {"source": "s5_blocks_control.py", "checker": "run.py",
             "control_formula": "s5_control.xcnf",
             "control_build": "s5_control_build.json",
             "witness_chart": "witness_chart.json",
             "formula": formula.name}
    receipt = {"status": "FROZEN_BLOCK_OUTPUT_CONTROL",
               "proposal_id": "Q20261009205500", "candidate_id": None,
               "pinned_field_bits": len(assignments),
               "formula_variables": int(header[2]),
               "limit_seconds": 30,
               "files": files,
               "sha256": {key: sha(HERE / name) for key, name in files.items()} |
                         {"cms_binary": sha(CMS)}}
    protocol_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": receipt["status"],
                      "pinned_field_bits": len(assignments),
                      "formula_sha256": sha(formula)}, sort_keys=True))


def run():
    output = HERE / "s5_blocks_control"
    if output.exists():
        raise FileExistsError(output)
    protocol_path = HERE / "s5_blocks_protocol.json"
    protocol = json.loads(protocol_path.read_text())
    assert protocol["status"] == "FROZEN_BLOCK_OUTPUT_CONTROL"
    assert all(protocol["sha256"][key] == sha(HERE / name)
               for key, name in protocol["files"].items())
    assert protocol["sha256"]["cms_binary"] == sha(CMS)
    output.mkdir()
    formula = HERE / "s5_blocks_control.xcnf"
    command = [str(CMS), "--threads=1", "--verb=1", "--printsol=1",
               "--maxtime=30", str(formula)]
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
    statuses = [line for line in stdout.decode(errors="replace").splitlines()
                if line.startswith("s ")]
    checked = None
    flag = None
    if not timed_out and "s SATISFIABLE" in statuses:
        try:
            bits = model_bits(stdout.decode(errors="replace"),
                              protocol["formula_variables"])
            valid, checked = verify_formula(formula, bits)
            status = "SAT_MODEL_PASS" if valid else "MODEL_CHECK_FAILED"
            if valid:
                (output / "model_bits.txt").write_text(bits + "\n")
                build = json.loads((HERE / "s5_control_build.json").read_text())
                flags = [bits[wire-1] == "1" for wire in build["target_flag_wires"]]
                flag = flags.index(True) if sum(flags) == 1 else None
        except (AssertionError, ValueError) as error:
            status = "MODEL_CHECK_FAILED"
            checked = {"error": str(error)}
    elif not timed_out and "s UNSATISFIABLE" in statuses:
        status = "UNSAT"
    else:
        status = "BOUNDED_UNKNOWN"
    receipt = {"status": status, "timed_out": timed_out,
               "returncode": None if timed_out else completed.returncode,
               "wall_ns": wall, "status_lines": statuses,
               "target_fiber_index": flag,
               "formula_assignment_check": checked,
               "sha256": {"protocol": sha(protocol_path),
                          "formula": sha(formula),
                          "stdout": sha(output / "stdout.txt"),
                          "stderr": sha(output / "stderr.txt")}}
    if (output / "model_bits.txt").exists():
        receipt["sha256"]["model_bits"] = sha(output / "model_bits.txt")
    (output / "result.json").write_text(json.dumps(receipt, indent=2,
                                                 sort_keys=True) + "\n")
    print(json.dumps({"status": status, "wall_ns": wall,
                      "target_fiber_index": flag,
                      "formula_assignment_check": checked}, sort_keys=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("build", "run"))
    build() if parser.parse_args().action == "build" else run()

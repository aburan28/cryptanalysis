#!/usr/bin/env python3
"""Measure the frozen-mask, pinned-root propagation diagnostic."""

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

import psutil

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "n41_n131_zero_sum_joint_20261009"))
from run import model_bits, verify_formula


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    output = HERE / "branch_probe"
    if output.exists():
        raise FileExistsError(output)
    parent_protocol = json.loads((HERE / "protocol.json").read_text())
    for key, relative in parent_protocol["files"].items():
        assert parent_protocol["sha256"][key] == sha(HERE / relative), key
    build = json.loads((HERE / "branch_probe_build.json").read_text())
    assert build["sha256"]["formula"] == sha(HERE / "branch_probe.xcnf")
    assert build["sha256"]["source"] == sha(HERE / "branch_probe_build.py")
    assert build["sha256"]["runner"] == sha(Path(__file__))
    binary = HERE / parent_protocol["files"]["solver_binary"]
    assert sha(binary) == parent_protocol["sha256"]["solver_binary"]
    control = json.loads((HERE / "control_build.json").read_text())
    chart = json.loads((HERE / "forward_chart.json").read_text())
    output.mkdir()
    limit = 30
    command = [str(binary), "--threads=1", "--verb=1", "--printsol=1",
               f"--maxtime={limit}", str(HERE / "branch_probe.xcnf")]
    started = time.monotonic_ns()
    peak = 0
    stop_reason = None
    parent = psutil.Process()
    with (output / "stdout.txt").open("wb") as stdout, \
         (output / "stderr.txt").open("wb") as stderr:
        process = subprocess.Popen(command, stdout=stdout, stderr=stderr)
        child = psutil.Process(process.pid)
        while process.poll() is None:
            try:
                peak = max(peak, parent.memory_info().rss + child.memory_info().rss)
            except psutil.NoSuchProcess:
                break
            if peak >= 4_294_967_296:
                stop_reason = "RSS_CAP"
            elif (time.monotonic_ns() - started)/1e9 > limit + 5:
                stop_reason = "WALL_CAP"
            if stop_reason:
                process.terminate()
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
                break
            time.sleep(0.2)
        returncode = process.wait()
    wall = time.monotonic_ns() - started
    stdout_text = (output / "stdout.txt").read_text(errors="replace")
    statuses = [line.strip() for line in stdout_text.splitlines()
                if line.startswith("s ")]
    checked = None
    masks = pair_u = block_u = branch_bits = fiber = None
    if stop_reason:
        status = "OOM_CAP" if stop_reason == "RSS_CAP" else "BOUNDED_UNKNOWN"
    elif "s SATISFIABLE" in statuses:
        bits = model_bits(stdout_text, build["formula_variables"])
        valid, checked = verify_formula(HERE / "branch_probe.xcnf", bits)
        if not valid:
            status = "PRODUCER_FAILURE"
        else:
            (output / "model_bits.txt").write_text(bits + "\n")
            def unpack(wires):
                return sum((bits[wire-1] == "1") << i
                           for i, wire in enumerate(wires))
            masks = [[unpack(a), unpack(b), unpack(a)^unpack(b)]
                     for a, b in control["mask_wire_rows"]]
            pair_u = [unpack(row) for row in control["pair_output_wire_rows"]]
            block_u = [unpack(row) for row in control["block_output_wire_rows"]]
            branch_bits = [[int(bits[wire-1] == "1") for wire in row]
                           for row in control["root_branch_wires"]]
            flags = [bits[wire-1] == "1" for wire in control["target_flag_wires"]]
            fiber = flags.index(True) if sum(flags) == 1 else None
            status = "SAT_MODEL"
    elif "s UNSATISFIABLE" in statuses:
        status = "UNSAT"
    elif "s INDETERMINATE" in statuses or returncode == 0:
        status = "BOUNDED_UNKNOWN"
    else:
        status = "PRODUCER_FAILURE"
    chart_match = (masks == chart["source_masks"] and
                   pair_u == chart["pair_u"] and block_u == chart["block_u"] and
                   branch_bits == chart["root_branch_bits"] and
                   fiber == chart["target_fiber_index"])
    receipt = {"status": status, "proposal_id": chart["proposal_id"],
               "candidate_id": None, "control": "source masks and root bits pinned",
               "chart_match": chart_match if status == "SAT_MODEL" else None,
               "solver_wall_ns": wall, "peak_combined_rss_bytes_sampled": peak,
               "stop_reason": stop_reason, "returncode": returncode,
               "solver_status_lines": statuses,
               "formula_assignment_check": checked,
               "model_masks": masks, "model_pair_u": pair_u,
               "model_block_u": block_u, "model_root_branch_bits": branch_bits,
               "model_target_fiber_index": fiber,
               "sha256": {"source": sha(Path(__file__)),
                          "parent_protocol": sha(HERE / "protocol.json"),
                          "build": sha(HERE / "branch_probe_build.json"),
                          "formula": sha(HERE / "branch_probe.xcnf"),
                          "stdout": sha(output / "stdout.txt"),
                          "stderr": sha(output / "stderr.txt")}}
    if (output / "model_bits.txt").exists():
        receipt["sha256"]["model_bits"] = sha(output / "model_bits.txt")
    (output / "result.json").write_text(json.dumps(receipt, indent=2,
                                                 sort_keys=True) + "\n")
    print(json.dumps({key: receipt[key] for key in
                      ("status", "chart_match", "solver_wall_ns",
                       "peak_combined_rss_bytes_sampled")}, sort_keys=True))


if __name__ == "__main__":
    main()

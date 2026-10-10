#!/usr/bin/env python3
"""One-worker, bounded SAT diagnostic of a frozen forward circuit."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

import psutil

HERE = Path(__file__).resolve().parent
JOINT = HERE.parent / "n41_n131_zero_sum_joint_20261009"
sys.path.insert(0, str(JOINT))
from run import model_bits, verify_formula


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(mode):
    output = HERE / mode
    if output.exists():
        raise FileExistsError(output)
    protocol_path = HERE / "protocol.json"
    protocol = json.loads(protocol_path.read_text())
    assert protocol["status"] == "FROZEN_FORWARD"
    for key, relative in protocol["files"].items():
        assert protocol["sha256"][key] == sha(HERE / relative), key
    formula = HERE / f"{mode}.xcnf"
    build = json.loads((HERE / f"{mode}_build.json").read_text())
    assert build["sha256"]["formula"] == sha(formula)
    output.mkdir()
    limit = protocol["limits"][f"{mode}_seconds"]
    command = [str(HERE / protocol["files"]["solver_binary"]),
               "--threads=1", "--verb=1", "--printsol=1",
               f"--maxtime={limit}", str(formula)]
    started = time.monotonic_ns()
    parent = psutil.Process()
    peak = 0
    stop_reason = None
    with (output / "stdout.txt").open("wb") as stdout, \
         (output / "stderr.txt").open("wb") as stderr:
        process = subprocess.Popen(command, stdout=stdout, stderr=stderr)
        child = psutil.Process(process.pid)
        while process.poll() is None:
            try:
                combined = parent.memory_info().rss + child.memory_info().rss
                peak = max(peak, combined)
            except psutil.NoSuchProcess:
                break
            if combined >= protocol["limits"]["combined_rss_bytes"]:
                stop_reason = "RSS_CAP"
            elif (time.monotonic_ns() - started) / 1e9 > limit + 5:
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
    bits = None
    checked = None
    if stop_reason:
        status = "OOM_CAP" if stop_reason == "RSS_CAP" else "BOUNDED_UNKNOWN"
    elif "s SATISFIABLE" in statuses:
        try:
            bits = model_bits(stdout_text, build["formula_variables"])
            valid, checked = verify_formula(formula, bits)
            if not valid:
                raise ValueError(f"source XCNF assignment failed: {checked}")
            (output / "model_bits.txt").write_text(bits + "\n")
            status = "SAT_MODEL"
        except (AssertionError, ValueError) as error:
            status = "PRODUCER_FAILURE"
            checked = {"error": str(error), "partial_check": checked}
    elif "s UNSATISFIABLE" in statuses:
        status = "UNSAT"
    elif "s INDETERMINATE" in statuses or returncode == 0:
        status = "BOUNDED_UNKNOWN"
    else:
        status = "PRODUCER_FAILURE"
    masks = pair_us = block_us = branches = fiber = None
    if bits is not None:
        def unpack(wires):
            return sum((bits[wire-1] == "1") << i
                       for i, wire in enumerate(wires))
        masks = [[unpack(a), unpack(b), unpack(a) ^ unpack(b)]
                 for a, b in build["mask_wire_rows"]]
        pair_us = [unpack(row) for row in build["pair_output_wire_rows"]]
        block_us = [unpack(row) for row in build["block_output_wire_rows"]]
        branches = [[int(bits[wire-1] == "1") for wire in row]
                    for row in build["root_branch_wires"]]
        flags = [bits[wire-1] == "1" for wire in build["target_flag_wires"]]
        fiber = flags.index(True) if sum(flags) == 1 else None
    receipt = {
        "status": status, "mode": mode,
        "proposal_id": protocol["proposal_id"], "candidate_id": None,
        "target_count": 1, "target": protocol["target"],
        "command": command, "returncode": returncode,
        "stop_reason": stop_reason, "solver_status_lines": statuses,
        "solver_wall_ns": wall, "peak_combined_rss_bytes_sampled": peak,
        "formula_assignment_check": checked,
        "model_masks": masks, "model_pair_u": pair_us,
        "model_block_u": block_us, "model_root_branch_bits": branches,
        "model_target_fiber_index": fiber,
        "sha256": {"protocol": sha(protocol_path), "formula": sha(formula),
                   "stdout": sha(output / "stdout.txt"),
                   "stderr": sha(output / "stderr.txt")},
    }
    if (output / "model_bits.txt").exists():
        receipt["sha256"]["model_bits"] = sha(output / "model_bits.txt")
    (output / "result.json").write_text(json.dumps(receipt, indent=2,
                                                 sort_keys=True) + "\n")
    print(json.dumps({key: receipt[key] for key in
                      ("status", "mode", "solver_wall_ns",
                       "peak_combined_rss_bytes_sampled", "model_masks",
                       "model_target_fiber_index")}, sort_keys=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("chart", "control", "public"))
    main(parser.parse_args().mode)

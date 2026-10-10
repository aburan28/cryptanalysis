#!/usr/bin/env python3
"""Run one frozen target-ended S5 formula under a one-worker resource cap."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time

import psutil

from run import CMS, model_bits, verify_formula

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main(mode):
    output = HERE / f"s5_{mode}"
    if output.exists():
        raise FileExistsError(output)
    protocol = json.loads((HERE / "s5_protocol.json").read_text())
    assert protocol["status"] == "FROZEN_S5"
    for key, name in protocol["files"].items():
        assert protocol["sha256"][key] == sha(HERE / name), key
    assert protocol["sha256"]["cryptominisat_binary"] == sha(CMS)
    build_name = "s5_control_build.json" if mode == "chart" else f"s5_{mode}_build.json"
    build = json.loads((HERE / build_name).read_text())
    formula = HERE / f"s5_{mode}.xcnf"
    assert build["sha256"]["formula"] == sha(
        HERE / ("s5_control.xcnf" if mode == "chart" else formula.name))
    if mode == "chart":
        chart = json.loads((HERE / "s5_chart_build.json").read_text())
        assert chart["sha256"]["formula"] == sha(formula)
    output.mkdir()
    limit = protocol["limits"][f"{mode}_seconds"]
    command = [str(CMS), "--threads=1", "--verb=1", "--printsol=1",
               f"--maxtime={limit}", str(formula)]
    start = time.monotonic_ns()
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
            elif (time.monotonic_ns() - start) / 1e9 > limit + 5:
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
    wall = time.monotonic_ns() - start
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
    masks = None
    output_us = None
    flag = None
    if bits is not None:
        def unpack(wires):
            return sum((bits[wire-1] == "1") << i
                       for i, wire in enumerate(wires))
        masks = [[unpack(a), unpack(b), unpack(a) ^ unpack(b)]
                 for a, b in build["mask_wire_rows"]]
        output_us = [unpack(row) for row in build["block_output_wire_rows"]]
        flags = [bits[wire-1] == "1" for wire in build["target_flag_wires"]]
        flag = flags.index(True) if sum(flags) == 1 else None
    receipt = {
        "status": status, "mode": mode,
        "proposal_id": protocol["proposal_id"], "candidate_id": None,
        "target_count": 1, "command": command,
        "returncode": returncode, "stop_reason": stop_reason,
        "solver_status_lines": statuses,
        "target_dependent_build_ns": build["build_ns"],
        "solver_wall_ns": wall,
        "peak_combined_rss_bytes_sampled": peak,
        "formula_assignment_check": checked,
        "model_masks": masks, "model_block_u": output_us,
        "model_target_fiber_index": flag,
        "sha256": {"protocol": sha(HERE / "s5_protocol.json"),
                   "formula": sha(formula),
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

#!/usr/bin/env python3
"""Bounded one-worker search on matched original and reindexed formulas."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

import psutil

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / "n41_n131_zero_sum_forward_20261009"
JOINT = HERE.parent / "n41_n131_zero_sum_joint_20261009"
sys.path.insert(0, str(JOINT))
from run import model_bits, verify_formula


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_bits(bits, build):
    primary = build["primary_old_wires"]
    n = build["formula_variables"]
    selected = set(primary)
    new_to_old = primary + [i for i in range(1, n + 1)
                            if i not in selected]
    assert len(bits) == len(new_to_old) == n
    answer = [None] * n
    for new, old in enumerate(new_to_old):
        answer[old-1] = bits[new]
    assert all(bit in ("0", "1") for bit in answer)
    return "".join(answer)


def main(mode):
    output = HERE / mode
    if output.exists():
        raise FileExistsError(output)
    protocol_file = HERE / "protocol.json"
    protocol = json.loads(protocol_file.read_text())
    assert protocol["status"] == "FROZEN_PRIMARY_ORDER"
    for key, relative in protocol["files"].items():
        assert protocol["sha256"][key] == sha(HERE / relative), key
    build = json.loads((HERE / "build.json").read_text())
    source_build = json.loads((SOURCE / "control_build.json").read_text())
    binary = HERE / protocol["files"]["solver_binary"]
    formula = (SOURCE / "control.xcnf" if mode == "original_control" else
               HERE / ("ordered_control.xcnf" if mode == "ordered_control"
                       else "ordered_public.xcnf"))
    assert sha(formula) == protocol["sha256"][f"{mode}_formula"]
    output.mkdir()
    limit = protocol["limits"][f"{mode}_seconds"]
    command = [str(binary), "--threads=1", "--verb=1", "--printsol=1",
               "--renumber=0", "--branchstr=vmtf", f"--maxtime={limit}",
               str(formula)]
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
                peak = max(peak, parent.memory_info().rss + child.memory_info().rss)
            except psutil.NoSuchProcess:
                break
            if peak >= protocol["limits"]["rss_bytes"]:
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
    checked = None
    masks = pair_u = block_u = branches = fiber = None
    if stop_reason:
        status = "OOM_CAP" if stop_reason == "RSS_CAP" else "BOUNDED_UNKNOWN"
    elif "s SATISFIABLE" in statuses:
        try:
            bits = model_bits(stdout_text, build["formula_variables"])
            valid, checked = verify_formula(formula, bits)
            if not valid:
                raise ValueError(f"run formula assignment failure: {checked}")
            original_bits = (bits if mode == "original_control"
                             else source_bits(bits, build))
            source_formula = (SOURCE / "public.xcnf" if mode == "ordered_public"
                              else SOURCE / "control.xcnf")
            valid_source, source_check = verify_formula(source_formula, original_bits)
            if not valid_source:
                raise ValueError(f"source formula assignment failure: {source_check}")
            (output / "model_bits.txt").write_text(bits + "\n")
            (output / "source_model_bits.txt").write_text(original_bits + "\n")

            def unpack(wires):
                return sum((original_bits[wire-1] == "1") << i
                           for i, wire in enumerate(wires))

            masks = [[unpack(a), unpack(b), unpack(a)^unpack(b)]
                     for a, b in source_build["mask_wire_rows"]]
            pair_u = [unpack(row) for row in source_build["pair_output_wire_rows"]]
            block_u = [unpack(row) for row in source_build["block_output_wire_rows"]]
            branches = [[int(original_bits[wire-1] == "1") for wire in row]
                        for row in source_build["root_branch_wires"]]
            flags = [original_bits[wire-1] == "1"
                     for wire in source_build["target_flag_wires"]]
            fiber = flags.index(True) if sum(flags) == 1 else None
            checked = {"run_formula": checked, "source_formula": source_check}
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
    receipt = {"status": status, "mode": mode,
               "proposal_id": protocol["proposal_id"], "candidate_id": None,
               "target_count": 1, "target": protocol["target"],
               "command": command, "returncode": returncode,
               "stop_reason": stop_reason, "solver_status_lines": statuses,
               "solver_wall_ns": wall, "peak_combined_rss_bytes_sampled": peak,
               "assignment_check": checked,
               "model_masks": masks, "model_pair_u": pair_u,
               "model_block_u": block_u, "model_root_branch_bits": branches,
               "model_target_fiber_index": fiber,
               "sha256": {"protocol": sha(protocol_file), "formula": sha(formula),
                          "stdout": sha(output / "stdout.txt"),
                          "stderr": sha(output / "stderr.txt")}}
    for name in ("model_bits.txt", "source_model_bits.txt"):
        if (output / name).exists():
            receipt["sha256"][name] = sha(output / name)
    (output / "result.json").write_text(json.dumps(receipt, indent=2,
                                                 sort_keys=True) + "\n")
    print(json.dumps({key: receipt[key] for key in
                      ("status", "mode", "solver_wall_ns",
                       "peak_combined_rss_bytes_sampled", "model_masks")},
                     sort_keys=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("original_control", "ordered_control",
                                         "ordered_public"))
    main(parser.parse_args().mode)

#!/usr/bin/env python3
"""Bounded one-worker CryptoMiniSat diagnostic for the frozen joint formula."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time

import psutil

HERE = Path(__file__).resolve().parent
CMS = Path("/opt/homebrew/bin/cryptominisat5")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify_formula(path, bits):
    clauses = xors = 0
    with path.open() as handle:
        header = handle.readline().split()
        assert header[:2] == ["p", "cnf"] and int(header[2]) == len(bits)
        for line in handle:
            row = line.split()
            if not row or row[0] == "c":
                continue
            assert row[-1] == "0"
            if row[0] == "x":
                parity = 0
                for item in row[1:-1]:
                    literal = int(item)
                    parity ^= (bits[abs(literal) - 1] == "1") ^ (literal < 0)
                if parity != 1:
                    return False, {"failed": "xor", "clauses": clauses,
                                   "xors": xors}
                xors += 1
            else:
                if not any((bits[abs(int(item)) - 1] == "1") ==
                           (int(item) > 0) for item in row[:-1]):
                    return False, {"failed": "clause", "clauses": clauses,
                                   "xors": xors}
                clauses += 1
    return True, {"clauses": clauses, "xors": xors}


def model_bits(stdout, variables):
    assignment = {}
    for line in stdout.splitlines():
        if not line.startswith("v "):
            continue
        for item in line.split()[1:]:
            literal = int(item)
            if literal:
                key = abs(literal)
                if key in assignment and assignment[key] != (literal > 0):
                    raise ValueError("contradictory solver assignment")
                assignment[key] = literal > 0
    if set(assignment) != set(range(1, variables + 1)):
        raise ValueError(f"incomplete solver assignment: {len(assignment)}/{variables}")
    return "".join("1" if assignment[i] else "0"
                   for i in range(1, variables + 1))


def read_protocol(mode):
    protocol = json.loads((HERE / "protocol.json").read_text())
    assert protocol["status"] == "FROZEN"
    for key, name in protocol["files"].items():
        assert sha(HERE / name) == protocol["sha256"][key], key
    assert sha(CMS) == protocol["sha256"]["cryptominisat_binary"]
    build = json.loads((HERE / f"{mode}_build.json").read_text())
    assert build["mode"] == mode and build["status"] == "BUILT"
    assert build["sha256"]["xcnf"] == sha(HERE / f"{mode}.xcnf")
    return protocol, build


def main(mode):
    output = HERE / mode
    if output.exists():
        raise FileExistsError(output)
    protocol, build = read_protocol(mode)
    output.mkdir()
    maximum = protocol["limits"][f"{mode}_seconds"]
    command = [str(CMS), "--threads=1", "--verb=1", "--printsol=1",
               f"--maxtime={maximum}", str(HERE / f"{mode}.xcnf")]
    started = time.monotonic_ns()
    parent = psutil.Process()
    peak_rss = 0
    stop_reason = None
    with (output / "stdout.txt").open("wb") as stdout, \
         (output / "stderr.txt").open("wb") as stderr:
        process = subprocess.Popen(command, stdout=stdout, stderr=stderr)
        child = psutil.Process(process.pid)
        while process.poll() is None:
            try:
                combined = parent.memory_info().rss + child.memory_info().rss
                peak_rss = max(peak_rss, combined)
            except psutil.NoSuchProcess:
                break
            if combined >= protocol["limits"]["combined_rss_bytes"]:
                stop_reason = "RSS_CAP"
            elif (time.monotonic_ns() - started) / 1e9 > maximum + 5:
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
    solver_wall_ns = time.monotonic_ns() - started
    text = (output / "stdout.txt").read_text(errors="replace")
    status_lines = [line.strip() for line in text.splitlines()
                    if line.startswith("s ")]
    model = None
    checked = None
    if stop_reason:
        status = "OOM_CAP" if stop_reason == "RSS_CAP" else "BOUNDED_UNKNOWN"
    elif "s SATISFIABLE" in status_lines:
        try:
            model = model_bits(text, build["formula_variables"])
            valid, checked = verify_formula(HERE / f"{mode}.xcnf", model)
            if not valid:
                raise ValueError(f"SAT model failed source formula: {checked}")
            (output / "model_bits.txt").write_text(model + "\n")
            status = "SAT_MODEL"
        except (AssertionError, ValueError) as error:
            status = "PRODUCER_FAILURE"
            checked = {"error": str(error), "partial_check": checked}
    elif "s UNSATISFIABLE" in status_lines:
        status = "UNSAT"
    elif "s INDETERMINATE" in status_lines or returncode == 0:
        status = "BOUNDED_UNKNOWN"
    else:
        status = "PRODUCER_FAILURE"
    masks = None
    if model is not None:
        masks = []
        for a, b in build["mask_wire_rows"]:
            av = sum((model[wire-1] == "1") << i for i, wire in enumerate(a))
            bv = sum((model[wire-1] == "1") << i for i, wire in enumerate(b))
            masks.append([av, bv, av ^ bv])
    receipt = {
        "status": status, "mode": mode, "proposal_id": protocol["proposal_id"],
        "candidate_id": None, "target_count": 1,
        "command": command, "returncode": returncode,
        "stop_reason": stop_reason, "solver_status_lines": status_lines,
        "target_dependent_build_ns": build["build_ns"],
        "solver_wall_ns": solver_wall_ns,
        "peak_combined_rss_bytes_sampled": peak_rss,
        "formula_assignment_check": checked,
        "model_masks": masks,
        "sha256": {"protocol": sha(HERE / "protocol.json"),
                   "formula": sha(HERE / f"{mode}.xcnf"),
                   "stdout": sha(output / "stdout.txt"),
                   "stderr": sha(output / "stderr.txt")},
    }
    if (output / "model_bits.txt").exists():
        receipt["sha256"]["model_bits"] = sha(output / "model_bits.txt")
    (output / "result.json").write_text(json.dumps(receipt, indent=2,
                                                 sort_keys=True) + "\n")
    print(json.dumps({key: receipt[key] for key in
                      ("status", "mode", "solver_wall_ns",
                       "peak_combined_rss_bytes_sampled", "model_masks")},
                     sort_keys=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("control", "public"))
    main(parser.parse_args().mode)

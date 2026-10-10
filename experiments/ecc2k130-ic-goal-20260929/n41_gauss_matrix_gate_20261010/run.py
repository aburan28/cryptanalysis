#!/usr/bin/env python3
"""One-worker bounded CryptoMiniSat comparison on frozen N41 XCNFs."""

import argparse
import hashlib
import json
import re
import subprocess
import time
from pathlib import Path

import psutil

HERE = Path(__file__).resolve().parent
GOAL = HERE.parent
SOURCE = GOAL / "n41_upper_xor_projection_20261010"
SOLVER = Path("/opt/homebrew/bin/cryptominisat5")
CASES = ("baseline_all_fixed", "gauss_all_fixed", "gauss_public")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(case):
    protocol = json.loads((HERE / "protocol.json").read_text())
    assert protocol["status"] == "FROZEN_BEFORE_N41_GAUSSIAN_MATRIX_GATE"
    for name, path in {
        "runner": Path(__file__),
        "solver": SOLVER,
        "all_fixed_formula": SOURCE / "all_fixed/projected.xcnf",
        "public_formula": SOURCE / "public/projected.xcnf",
        "sage_runtime": HERE / "sage_runtime_info.json",
    }.items():
        assert protocol["source_sha256"][name] == sha(path), name
    if case == "gauss_public":
        audit = json.loads((HERE / "gauss_all_fixed/audit.json").read_text())
        assert audit["status"] == "PASS_PROJECTED_AND_LIFTED_SAT_MODEL"
    folder = HERE / case
    folder.mkdir(exist_ok=False)
    mode = "public" if case == "gauss_public" else "all_fixed"
    formula = SOURCE / mode / "projected.xcnf"
    cap = protocol["caps_seconds"][case]
    command = [str(SOLVER), *protocol["flags"][case],
               f"--maxtime={cap-2}", str(formula)]
    stdout, stderr = folder / "solver.stdout.txt", folder / "solver.stderr.txt"
    started = time.monotonic_ns()
    peak = 0
    stop = None
    with stdout.open("xb") as out, stderr.open("xb") as err:
        proc = subprocess.Popen(command, stdout=out, stderr=err,
                                start_new_session=True)
        child = psutil.Process(proc.pid)
        while proc.poll() is None:
            try:
                peak = max(peak, child.memory_info().rss)
            except psutil.NoSuchProcess:
                pass
            if peak > protocol["rss_cap_bytes"]:
                stop = "RSS_CAP"
            elif time.monotonic_ns() - started >= cap * 10**9:
                stop = "WALL_CAP"
            if stop:
                proc.terminate()
                break
            time.sleep(0.05)
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
            stop = (stop or "DRAIN_TIMEOUT") + "_KILLED"
    wall = time.monotonic_ns() - started
    output = stdout.read_text(errors="replace")
    statuses = [line for line in output.splitlines() if line.startswith("s ")]
    model_lines = sum(line.startswith("v ") for line in output.splitlines())
    matrix_counts = [int(value) for value in re.findall(
        r"Using (\d+) matrices recovered from", output)]
    too_large = len(re.findall(r"Too many (?:rows|cols) in matrix", output))
    if statuses == ["s SATISFIABLE"] and model_lines:
        status = "SAT_MODEL_PENDING_AUDIT"
    elif statuses == ["s UNSATISFIABLE"]:
        status = "UNSAT_FORMULA"
    elif stop == "RSS_CAP":
        status = "OOM"
    elif stop is not None or "s INDETERMINATE" in statuses:
        status = "CENSORED_TIME"
    else:
        status = "PRODUCER_OR_SOLVER_FAILURE"
    receipt = {
        "status": status,
        "case": case,
        "mode": mode,
        "candidate_id": None,
        "target_count": 1,
        "public_target_q": protocol["public_target_q"],
        "command": command,
        "solver_exit_code": proc.returncode,
        "solver_status_lines": statuses,
        "model_lines": model_lines,
        "matrix_counts": matrix_counts,
        "too_large_matrix_messages": too_large,
        "stop_reason": stop,
        "parent_wall_ns": wall,
        "sampled_solver_peak_rss_bytes": peak,
        "source_sha256": {
            "runner": sha(Path(__file__)),
            "protocol": sha(HERE / "protocol.json"),
            "formula": sha(formula),
            "solver": sha(SOLVER),
            "stdout": sha(stdout),
            "stderr": sha(stderr),
        },
    }
    with (folder / "result.json").open("x") as out:
        json.dump(receipt, out, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps({"status": status, "case": case,
                      "parent_wall_s": wall / 1e9,
                      "matrix_counts_first": matrix_counts[:2],
                      "peak_rss_bytes": peak}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("case", choices=CASES)
    main(parser.parse_args().case)

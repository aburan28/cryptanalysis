#!/usr/bin/env python3
"""Run one frozen, sound WDSat four-point stage cell."""

import argparse
import gzip
import hashlib
import json
import platform
import re
import resource
import subprocess
import time
from pathlib import Path

from factor_xcnf import translate
from verify_factor_xcnf import audit, count_violations, read_formula


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
PROTOCOL = HERE / "protocol.json"
SAGE = "/Volumes/SSD990/cryptanalysis/sage"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(cell, binary):
    protocol = json.loads(PROTOCOL.read_text())
    frozen = protocol["cells"][cell]
    assert sha(binary) == protocol["binaries"][frozen["degree"]]["binary_sha256"]
    assert sha(HERE / "sage_runtime_info.json") == protocol[
        "sage_runtime_info_sha256"]
    assert sha(HERE / "solver_validation.json") == protocol[
        "solver_validation_sha256"]
    source = REPO / frozen["source_formula"]
    assert sha(source) == frozen["source_gzip_sha256"]
    output = HERE / "runs" / cell
    assert not output.exists(), "refuse to overwrite frozen run"
    output.mkdir(parents=True)
    formula = output / "system.factored.xcnf"
    started = time.perf_counter()
    stats = translate(str(source), str(formula))
    prep_seconds = time.perf_counter() - started
    assert sha(formula) == frozen["factored_sha256"]
    check = audit(source, formula)
    assert check == frozen["audit"]
    assert stats["new_vars"] == frozen["factored_variables"]
    command = [str(binary), "-i", str(formula)]
    started = time.perf_counter()
    timed_out = False
    try:
        result = subprocess.run(command, capture_output=True, text=True,
                                timeout=protocol["wall_cap_seconds"])
        stdout, stderr, code = result.stdout, result.stderr, result.returncode
    except subprocess.TimeoutExpired as error:
        timed_out = True
        stdout = (error.stdout or b"").decode("utf-8", "replace")
        stderr = (error.stderr or b"").decode("utf-8", "replace")
        code = None
    solve_seconds = time.perf_counter() - started
    after = resource.getrusage(resource.RUSAGE_CHILDREN)
    (output / "solver.stdout.txt").write_text(stdout)
    (output / "solver.stderr.txt").write_text(stderr)
    branch_points = [int(x) for x in re.findall(
        r"q1444_branch_counter=([0-9]+)", stderr)]
    model_lines = [row for row in stdout.splitlines()
                   if len(row) == frozen["factored_variables"]
                   and set(row) <= {"0", "1"}]
    assert len(model_lines) <= 1
    status = "external_timeout" if timed_out else "no_model"
    if not timed_out and "UNSAT" in stdout:
        status = "solver_reported_unsat"
    model_check = None
    replay = None
    replay_seconds = None
    if model_lines:
        bits = model_lines[0]
        (output / "model.bits.txt").write_text(bits + "\n")
        values = {j: digit == "1" for j, digit in enumerate(bits, 1)}
        oldvars, original = read_formula(source)
        newvars, converted = read_formula(formula)
        assert oldvars == frozen["source_variables"]
        assert newvars == len(bits)
        original_bad = count_violations(original, values)
        converted_bad = count_violations(converted, values)
        model_check = {"original_cnf_bad": original_bad[0],
                       "original_xor_bad": original_bad[1],
                       "converted_cnf_bad": converted_bad[0],
                       "converted_xor_bad": converted_bad[1]}
        status = "invalid_model" if any(model_check.values()) else "formula_sat"
        if status == "formula_sat":
            check_started = time.perf_counter()
            checked = subprocess.run(
                [SAGE, "-python", str(HERE / "replay_relation.py"),
                 "--cell", cell, "--model", str(output / "model.bits.txt")],
                capture_output=True, text=True, timeout=120)
            replay_seconds = time.perf_counter() - check_started
            (output / "replay.stdout.txt").write_text(checked.stdout)
            (output / "replay.stderr.txt").write_text(checked.stderr)
            if checked.returncode == 0:
                replay = json.loads(checked.stdout.splitlines()[-1])
                status = replay["status"]
            else:
                status = "replay_error"
    with (output / "system.factored.xcnf.gz").open("wb") as stream:
        with gzip.GzipFile(filename="", mode="wb", fileobj=stream,
                           mtime=0, compresslevel=9) as zipped:
            zipped.write(formula.read_bytes())
    formula.unlink()
    receipt = {
        "proposal_id": "Q1444",
        "candidate_id": None,
        "isogeny": "none",
        "cell": cell,
        "curve_id": frozen["curve_id"],
        "factor_base_actual_B": frozen["factor_base_actual_B"],
        "folded_columns_K": frozen["folded_columns_K"],
        "factor_base_enumerated_set_sha256": frozen["factor_base_enumerated_set_sha256"],
        "workload_id": frozen["workload_id"],
        "ordinary_query": frozen["ordinary_query"],
        "status": status,
        "verified_relations": int(status == "verified_four_point_relation"),
        "command": command,
        "return_code": code,
        "wall_cap_seconds": protocol["wall_cap_seconds"],
        "formula_preparation_seconds": prep_seconds,
        "solver_wall_seconds": solve_seconds,
        "replay_seconds": replay_seconds,
        "child_peak_rss_raw": after.ru_maxrss,
        "child_peak_rss_unit": "bytes" if platform.system() == "Darwin" else "kilobytes",
        "branch_counter_checkpoint_lower_bound": max(branch_points, default=0),
        "branch_counter_final": int(stdout.splitlines()[-1])
        if model_lines and stdout.splitlines()[-1].isdigit() else None,
        "model_check": model_check,
        "group_replay": replay,
        "source_formula_gzip_sha256": sha(source),
        "factored_formula_raw_sha256": frozen["factored_sha256"],
        "factored_formula_gzip_sha256": sha(output / "system.factored.xcnf.gz"),
        "solver_binary_sha256": sha(binary),
        "solver_stdout_sha256": sha(output / "solver.stdout.txt"),
        "solver_stderr_sha256": sha(output / "solver.stderr.txt"),
        "unisolated_host_exploratory": True,
        "complete_n131_log2_work": None,
    }
    (output / "receipt.json").write_text(json.dumps(receipt, indent=2,
                                                   sort_keys=True) + "\n")
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--cell", required=True)
    parser.add_argument("--binary", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.cell, args.binary), sort_keys=True))

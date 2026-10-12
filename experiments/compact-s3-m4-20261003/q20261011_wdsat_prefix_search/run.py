#!/usr/bin/env python3
"""Run one Q1469 priority prefix on a frozen control or ordinary query."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import re
import resource
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
Q1460 = PARENT / "q20261011_wdsat_shared_prefix"
Q1463 = PARENT / "q20261011_wdsat_ordinary"
from priorities import MODES, priorities
sys.path.insert(0, str(Q1460))
from prepare import evaluate  # noqa: E402


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def cpu_limit(soft: int, hard: int):
    def apply() -> None:
        resource.setrlimit(resource.RLIMIT_CPU, (soft, hard))
    return apply


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("degree", type=int, choices=(53, 83))
    parser.add_argument("kind", choices=("full_lock", "ordinary"))
    parser.add_argument("mode", choices=MODES)
    args = parser.parse_args()
    name = f"n{args.degree}"
    cell = f"{name}_{args.kind}"
    protocol_bytes = (HERE / "protocol.json").read_bytes()
    protocol = json.loads(protocol_bytes)
    assert f"{cell}_{args.mode}" in protocol["limits"]["run_order"]
    freeze_bytes = (HERE / "freeze.json").read_bytes()
    freeze = json.loads(freeze_bytes)
    build_bytes = (HERE / "build_receipt.json").read_bytes()
    build = json.loads(build_bytes)
    assert freeze["protocol_sha256"] == sha(protocol_bytes)
    assert build["freeze_sha256"] == sha(freeze_bytes)
    assert freeze["runner_source_sha256"] == sha(Path(__file__).read_bytes())
    order = priorities(args.degree)
    assert freeze["priority_source_sha256"] == sha((HERE / "priorities.py").read_bytes())
    record = freeze["cells"][cell]
    if args.kind == "ordinary":
        archive_path = Q1463 / f"{name}_ordinary.xcnf.gz"
        source_path = PARENT / "runs" / f"{name}_q{1410 if args.degree == 53 else 1408}_ordinary.xcnf.gz"
    else:
        archive_path = Q1460 / f"{name}_full_lock.xcnf.gz"
        source_path = PARENT / "q1419_partial_pin/runs" / f"{name}_full_lock/system.xcnf.gz"
    archive_bytes = archive_path.read_bytes()
    source_bytes = source_path.read_bytes()
    assert sha(archive_bytes) == record["derived_archive_sha256"]
    assert sha(source_bytes) == record["source_archive_sha256"]
    derived = gzip.decompress(archive_bytes)
    original = gzip.decompress(source_bytes)
    assert sha(derived) == record["derived_raw_sha256"]
    original_variables = int(original.splitlines()[0].split()[2])
    binary_record = build["per_degree"][name]
    binary = Path(binary_record["binary_path"])
    assert sha(binary.read_bytes()) == binary_record["binary_sha256"]
    out = HERE / "runs" / cell / args.mode
    assert not out.exists()
    out.mkdir(parents=True)
    limits = protocol["limits"]
    command = [str(binary), "-i", "INPUT"]
    start = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="q1469_prefix_", dir="/Volumes/SSD990/llm/tmp") as directory:
        input_path = Path(directory) / "system.xcnf"
        input_path.write_bytes(derived)
        actual = [str(input_path) if token == "INPUT" else token for token in command]
        child_env = os.environ.copy()
        child_env["Q1469_ORDER_MODE"] = args.mode
        try:
            process = subprocess.run(actual, capture_output=True,
                                     timeout=limits["wall_seconds_per_run"],
                                     preexec_fn=cpu_limit(limits["cpu_seconds_soft"],
                                                          limits["cpu_seconds_hard"]),
                                     env=child_env)
            stdout, stderr, code = process.stdout, process.stderr, process.returncode
            timed_out = False
        except subprocess.TimeoutExpired as error:
            stdout, stderr, code = error.stdout or b"", error.stderr or b"", None
            timed_out = True
    wall = time.monotonic() - start
    usage = resource.getrusage(resource.RUSAGE_CHILDREN)
    (out / "solver.stdout.txt").write_bytes(stdout)
    (out / "solver.stderr.txt").write_bytes(stderr)
    output_text = stdout.decode("utf-8", "replace")
    error_text = stderr.decode("utf-8", "replace")
    expected_priority = order[args.mode]
    order_marker = f"Q1469_ORDER {args.mode} {len(expected_priority)}"
    assert error_text.splitlines().count(order_marker) == 1, error_text[-2000:]
    assert "Q1469_BAD_" not in error_text
    checkpoints = [int(value) for value in re.findall(r"^Q1464_BRANCH (\d+)$",
                                                      error_text, re.MULTILINE)]
    branch_cap = limits["left_branch_attempts_per_run"]
    assert all(value == 1 << index for index, value in enumerate(checkpoints))
    assert not checkpoints or checkpoints[-1] <= branch_cap
    cap_markers = [int(value) for value in re.findall(r"^Q1464_BRANCH_CAP (\d+)$",
                                                       error_text, re.MULTILINE)]
    models = [line.strip() for line in output_text.splitlines()
              if len(line.strip()) == record["derived_variables"] and
              set(line.strip()) <= {"0", "1", "2"}]
    replay = None
    if timed_out:
        status = "WALL_CAP_SEARCH_STARTED" if "Q1458_SEARCH_START" in error_text else "CENSORED_BEFORE_SEARCH"
    elif code == 42 and cap_markers == [branch_cap] and checkpoints[-1] == branch_cap:
        status = "BRANCH_CAP_REACHED"
    elif code in (-signal.SIGXCPU, -signal.SIGKILL) and usage.ru_utime + usage.ru_stime >= limits["cpu_seconds_soft"] - 2:
        status = "CPU_CAP_SEARCH_STARTED" if "Q1458_SEARCH_START" in error_text else "CPU_CAP_BEFORE_SEARCH"
    elif code != 0:
        status = "PRODUCER_FAILURE"
    elif "UNSAT" in output_text:
        status = "UNSAT_REPORTED_UNVERIFIED"
    elif len(models) == 1 and set(models[0]) <= {"0", "1"}:
        model = {index + 1: value == "1" for index, value in enumerate(models[0])}
        try:
            replay = {"derived": evaluate(derived, model),
                      "original": evaluate(original, {index: model[index]
                                                      for index in range(1, original_variables + 1)})}
            status = "SAT_REPLAYED_XCNF"
        except (AssertionError, ValueError) as error:
            replay = {"error": repr(error)}
            status = "MODEL_REPLAY_FAILED"
    else:
        status = "PRODUCER_FAILURE_NO_MODEL"
    receipt = {"proposal_id": "Q1469", "candidate_id": None, "run_id": None,
               "isogeny": "none", "degree": args.degree, "kind": args.kind,
               "variant": args.mode, "ordinary_query": args.kind == "ordinary",
               "branch_order_priority_count": len(expected_priority),
               "branch_order_marker": order_marker,
               "curve_id": record["curve_id"], "workload_id": record["workload_id"],
               "public_target": record["public_target"],
               "factor_base_actual_B": record["factor_base_actual_B"],
               "factor_base_folded_columns_K": record["factor_base_folded_columns_K"],
               "factor_base_enumerated_set_sha256": record["factor_base_enumerated_set_sha256"],
               "status": status, "return_code": code, "timed_out": timed_out,
               "search_started": "Q1458_SEARCH_START" in error_text,
               "after_xor_init": "Q1458_AFTER_XOR_INIT" in error_text,
               "branch_checkpoints": checkpoints,
               "branch_lower_bound": checkpoints[-1] if checkpoints else 0,
               "branch_exact_at_cap": branch_cap if status == "BRANCH_CAP_REACHED" else None,
               "model_count": len(models), "model_replay": replay,
               "wall_seconds_exploratory": wall,
               "user_cpu_seconds": usage.ru_utime,
               "system_cpu_seconds": usage.ru_stime,
               "maxrss_child_bytes_darwin": usage.ru_maxrss,
               "wall_limit_seconds": limits["wall_seconds_per_run"],
               "cpu_soft_limit_seconds": limits["cpu_seconds_soft"],
               "cpu_hard_limit_seconds": limits["cpu_seconds_hard"],
               "left_branch_attempt_limit": branch_cap,
               "address_space_limit_mib": None,
               "verified_natural_relations": None if status == "SAT_REPLAYED_XCNF" else 0,
               "natural_relation_yield_estimate": None,
               "complete_solve_work_log2": None,
               "protocol_sha256": sha(protocol_bytes), "freeze_sha256": sha(freeze_bytes),
               "build_receipt_sha256": sha(build_bytes),
               "archive_sha256": sha(archive_bytes), "source_archive_sha256": sha(source_bytes),
               "binary_sha256": sha(binary.read_bytes()),
               "runner_sha256": sha(Path(__file__).read_bytes()),
               "stdout_sha256": sha(stdout), "stderr_sha256": sha(stderr),
               "command_template": command}
    (out / "receipt.json").write_text(json.dumps(receipt, indent=2,
                                                 sort_keys=True) + "\n")
    print(json.dumps({"cell": cell, "mode": args.mode, "status": status,
                      "branch_lower_bound": receipt["branch_lower_bound"],
                      "wall_seconds": wall, "user_cpu_seconds": usage.ru_utime}))


if __name__ == "__main__":
    main()

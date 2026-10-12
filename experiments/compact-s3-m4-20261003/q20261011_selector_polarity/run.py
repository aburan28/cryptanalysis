#!/usr/bin/env python3
"""Run one frozen selector polarity on the same ordinary N83 point."""
from __future__ import annotations

import argparse
import copy
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
Q1419 = PARENT / "q1419_partial_pin"
sys.path.insert(0, str(Q1460))
from prepare import evaluate  # noqa: E402
from phase_schedule import INDICES, phases  # noqa: E402


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def cpu_limit(soft: int, hard: int):
    def apply() -> None:
        resource.setrlimit(resource.RLIMIT_CPU, (soft, hard))
    return apply


def check_group_relation(model: dict[int, bool], public: list[int],
                         raw_xs: list[int]) -> dict:
    sys.path.insert(0, str(PARENT))
    sys.path.insert(0, str(Q1419))
    from chain_s3_balanced_multitarget import build_balanced  # noqa: E402
    from run_cell import verify_relation  # noqa: E402
    profile = copy.deepcopy(json.loads((Q1419 / "protocol.json").read_text())[
        "profiles"]["83"])
    profile["public_target"] = public
    formula, leaves, _, _, _ = build_balanced(83, 5, raw_xs)
    assert formula.variables == len([key for key in model if key <= formula.variables])
    return verify_relation(profile, model, leaves)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("kind", choices=("control", "ordinary"))
    parser.add_argument("phase", type=int, choices=INDICES)
    args = parser.parse_args()
    protocol_bytes = (HERE / "protocol.json").read_bytes()
    protocol = json.loads(protocol_bytes)
    freeze_bytes = (HERE / "freeze.json").read_bytes()
    freeze = json.loads(freeze_bytes)
    build_bytes = (HERE / "build_receipt.json").read_bytes()
    build = json.loads(build_bytes)
    target_bytes = (HERE / "target.json").read_bytes()
    target = json.loads(target_bytes)
    assert freeze["protocol_sha256"] == sha(protocol_bytes)
    assert freeze["runner_source_sha256"] == sha(Path(__file__).read_bytes())
    assert freeze["target_sha256"] == sha(target_bytes)
    assert build["freeze_sha256"] == sha(freeze_bytes)
    schedule = phases()
    phase = schedule[args.phase]
    assert freeze["phase_schedule"][str(args.phase)] == phase
    assert protocol["workload_id"] == target["workload_id"]
    record = freeze["cells"][args.kind]
    archive_path = Path(record["derived_archive_path"])
    source_path = Path(record["source_archive_path"])
    archive_bytes, source_bytes = archive_path.read_bytes(), source_path.read_bytes()
    assert sha(archive_bytes) == record["derived_archive_sha256"]
    assert sha(source_bytes) == record["source_archive_sha256"]
    derived, original = gzip.decompress(archive_bytes), gzip.decompress(source_bytes)
    assert sha(derived) == record["derived_raw_sha256"]
    assert sha(original) == record["source_raw_sha256"]
    original_variables = int(original.splitlines()[0].split()[2])
    binary = Path(build["binary_path"])
    assert sha(binary.read_bytes()) == build["binary_sha256"]
    out = HERE / "runs" / args.kind / f"phase{args.phase}"
    assert not out.exists()
    out.mkdir(parents=True)
    limits = protocol["limits"]
    command = [str(binary), "-i", "INPUT"]
    child_env = os.environ.copy()
    child_env["Q1469_ORDER_MODE"] = "selector_pair_mids"
    child_env["Q1472_PHASE_INDEX"] = "0"
    child_env["Q1473_SELECTOR_PHASE"] = str(args.phase)
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="q1473_selector_", dir="/Volumes/SSD990/llm/tmp") as directory:
        input_path = Path(directory) / "system.xcnf"
        input_path.write_bytes(derived)
        actual = [str(input_path) if token == "INPUT" else token for token in command]
        solver_started = time.monotonic()
        try:
            process = subprocess.run(actual, capture_output=True,
                                     timeout=limits["wall_seconds_per_phase"],
                                     preexec_fn=cpu_limit(limits["cpu_seconds_soft_per_phase"],
                                                          limits["cpu_seconds_hard_per_phase"]),
                                     env=child_env)
            stdout, stderr, code = process.stdout, process.stderr, process.returncode
            timed_out = False
        except subprocess.TimeoutExpired as error:
            stdout, stderr, code = error.stdout or b"", error.stderr or b"", None
            timed_out = True
        solver_wall = time.monotonic() - solver_started
    usage = resource.getrusage(resource.RUSAGE_CHILDREN)
    (out / "solver.stdout.txt").write_bytes(stdout)
    (out / "solver.stderr.txt").write_bytes(stderr)
    output_text = stdout.decode("utf-8", "replace")
    error_text = stderr.decode("utf-8", "replace")
    order_marker = "Q1469_ORDER selector_pair_mids 168"
    phase_marker = f"Q1473_SELECTOR_PHASE {args.phase} 2140 2141"
    order_seen = error_text.splitlines().count(order_marker) == 1
    phase_seen = (error_text.splitlines().count("Q1472_PHASE 0 0") == 1 and
                  error_text.splitlines().count(phase_marker) == 1)
    checkpoints = [int(value) for value in re.findall(r"^Q1464_BRANCH (\d+)$",
                                                      error_text, re.MULTILINE)]
    assert all(value == 1 << index for index, value in enumerate(checkpoints))
    cap = limits["left_branch_attempts_per_phase"]
    assert not checkpoints or checkpoints[-1] <= cap
    work_checkpoints = [tuple(map(int, values)) for values in re.findall(
        r"^Q1473_WORK (\d+) (\d+) (\d+)$", error_text, re.MULTILINE)]
    assert [row[0] for row in work_checkpoints] == checkpoints
    assert all(work_checkpoints[i][1] >= work_checkpoints[i - 1][1] and
               work_checkpoints[i][2] >= work_checkpoints[i - 1][2]
               for i in range(1, len(work_checkpoints)))
    final_work_rows = [tuple(map(int, values)) for values in re.findall(
        r"^Q1473_WORK_FINAL (\d+) (\d+)$", error_text, re.MULTILINE)]
    assert len(final_work_rows) <= 1
    if final_work_rows and work_checkpoints:
        assert final_work_rows[0][0] >= work_checkpoints[-1][1]
        assert final_work_rows[0][1] >= work_checkpoints[-1][2]
    cap_markers = [int(value) for value in re.findall(r"^Q1464_BRANCH_CAP (\d+)$",
                                                       error_text, re.MULTILINE)]
    models = [line.strip() for line in output_text.splitlines()
              if len(line.strip()) == record["derived_variables"] and
              set(line.strip()) <= {"0", "1", "2"}]
    xcnf_replay = None
    group_replay = None
    group_seconds = 0.0
    search_started = "Q1458_SEARCH_START" in error_text
    if timed_out:
        status = "WALL_CAP_SEARCH_STARTED" if search_started else "CENSORED_BEFORE_SEARCH"
    elif code == 42 and cap_markers == [cap] and checkpoints[-1] == cap:
        status = "BRANCH_CAP_REACHED"
    elif code in (-signal.SIGXCPU, -signal.SIGKILL) and usage.ru_utime + usage.ru_stime >= limits["cpu_seconds_soft_per_phase"] - 2:
        status = "CPU_CAP_SEARCH_STARTED" if search_started else "CPU_CAP_BEFORE_SEARCH"
    elif code != 0:
        status = "PRODUCER_FAILURE"
    elif "UNSAT" in output_text:
        status = "UNSAT_REPORTED_UNVERIFIED"
    elif len(models) == 1 and set(models[0]) <= {"0", "1"}:
        model = {index + 1: value == "1" for index, value in enumerate(models[0])}
        try:
            xcnf_replay = {"derived": evaluate(derived, model),
                           "original": evaluate(original, {index: model[index]
                                                           for index in range(1, original_variables + 1)})}
            status = "SAT_REPLAYED_XCNF"
            if args.kind == "ordinary":
                group_started = time.monotonic()
                group_replay = check_group_relation(model, target["public_target"],
                                                    target["raw_preimage_x_coordinates"])
                group_seconds = time.monotonic() - group_started
                if group_replay["status"] == "verified_four_point_relation":
                    status = "VERIFIED_RELATION"
                else:
                    status = "SAT_XCNF_NOT_RELATION"
        except (AssertionError, ValueError) as error:
            xcnf_replay = {"error": repr(error)}
            status = "MODEL_REPLAY_FAILED"
    else:
        status = "PRODUCER_FAILURE_NO_MODEL"
    wall = time.monotonic() - started
    receipt = {"proposal_id": "Q1473", "candidate_id": None, "run_id": None,
               "isogeny": "none", "kind": args.kind, "phase_index": args.phase,
               "phase_seed": phase["seed"], "phase_flip_ids": phase["flip_ids"],
               "phase_flip_count": len(phase["flip_ids"]),
               "curve_id": record["curve_id"], "workload_id": record["workload_id"],
               "public_target": record["public_target"],
               "factor_base_actual_B": record["factor_base_actual_B"],
               "factor_base_folded_columns_K": record["factor_base_folded_columns_K"],
               "factor_base_enumerated_set_sha256": record["factor_base_enumerated_set_sha256"],
               "status": status, "return_code": code, "timed_out": timed_out,
               "search_started": search_started,
               "after_xor_init": "Q1458_AFTER_XOR_INIT" in error_text,
               "order_marker_seen": order_seen, "phase_marker_seen": phase_seen,
               "branch_checkpoints": checkpoints,
               "branch_lower_bound": checkpoints[-1] if checkpoints else 0,
               "branch_exact_at_cap": cap if status == "BRANCH_CAP_REACHED" else None,
               "work_checkpoints": work_checkpoints,
               "cnf_set_true_calls_lower_bound": (
                   work_checkpoints[-1][1] if work_checkpoints else 0),
               "xor_set_true_calls_lower_bound": (
                   work_checkpoints[-1][2] if work_checkpoints else 0),
               "cnf_set_true_calls_final": (
                   final_work_rows[0][0] if final_work_rows else None),
               "xor_set_true_calls_final": (
                   final_work_rows[0][1] if final_work_rows else None),
               "model_count": len(models), "xcnf_replay": xcnf_replay,
               "group_replay": group_replay,
               "verified_natural_relations": int(status == "VERIFIED_RELATION"),
               "natural_relation_yield_estimate": None,
               "complete_solve_work_log2": None,
               "solver_wall_seconds_exploratory": solver_wall,
               "group_replay_wall_seconds": group_seconds,
               "run_wall_seconds_exploratory": wall,
               "user_cpu_seconds": usage.ru_utime,
               "system_cpu_seconds": usage.ru_stime,
               "maxrss_child_bytes_darwin": usage.ru_maxrss,
               "left_branch_attempt_limit": cap,
               "cpu_soft_limit_seconds": limits["cpu_seconds_soft_per_phase"],
               "cpu_hard_limit_seconds": limits["cpu_seconds_hard_per_phase"],
               "wall_limit_seconds": limits["wall_seconds_per_phase"],
               "protocol_sha256": sha(protocol_bytes), "freeze_sha256": sha(freeze_bytes),
               "build_receipt_sha256": sha(build_bytes), "target_sha256": sha(target_bytes),
               "archive_sha256": sha(archive_bytes), "source_archive_sha256": sha(source_bytes),
               "binary_sha256": sha(binary.read_bytes()),
               "runner_sha256": sha(Path(__file__).read_bytes()),
               "stdout_sha256": sha(stdout), "stderr_sha256": sha(stderr),
               "command_template": command}
    (out / "receipt.json").write_text(json.dumps(receipt, indent=2,
                                                 sort_keys=True) + "\n")
    print(json.dumps({"kind": args.kind, "phase": args.phase,
                      "status": status, "branch_lower_bound": receipt["branch_lower_bound"],
                      "user_cpu_seconds": usage.ru_utime,
                      "solver_wall_seconds": solver_wall}))


if __name__ == "__main__":
    main()

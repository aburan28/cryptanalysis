#!/usr/bin/env python3
"""Measure a frozen Q1464 WDSat cell with exact branch and wall budgets."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
import resource
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
Q1460 = PARENT / "q20261011_wdsat_shared_prefix"
Q1463 = PARENT / "q20261011_wdsat_ordinary"
sys.path.insert(0, str(Q1460))
from prepare import evaluate  # noqa: E402


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("degree", type=int, choices=(53, 83))
    parser.add_argument("kind", choices=("full_lock", "ordinary"))
    parser.add_argument("variant", choices=("plain", "xor_gauss"))
    args = parser.parse_args()
    name = f"n{args.degree}"
    cell = f"{name}_{args.kind}_{args.variant}"
    protocol_bytes = (HERE / "protocol.json").read_bytes()
    protocol = json.loads(protocol_bytes)
    assert cell in protocol["limits"]["run_order"]
    freeze_bytes = (HERE / "freeze.json").read_bytes()
    freeze = json.loads(freeze_bytes)
    build_bytes = (HERE / "build_receipt.json").read_bytes()
    build = json.loads(build_bytes)
    assert freeze["protocol_sha256"] == sha(protocol_bytes)
    assert build["freeze_sha256"] == sha(freeze_bytes)
    record = freeze["cells"][name]
    if args.kind == "ordinary":
        archive_path = Q1463 / f"{name}_ordinary.xcnf.gz"
        source_path = PARENT / "runs" / f"{name}_q{1410 if args.degree == 53 else 1408}_ordinary.xcnf.gz"
        archive_key, source_key, raw_key, var_key = (
            "ordinary_archive_sha256", "ordinary_source_archive_sha256",
            "ordinary_raw_sha256", "ordinary_variables")
        workload_id = record["ordinary_workload_id"]
        public_target = record["public_target"]
    else:
        archive_path = Q1460 / f"{name}_full_lock.xcnf.gz"
        source_path = PARENT / "q1419_partial_pin/runs" / f"{name}_full_lock/system.xcnf.gz"
        archive_key, source_key, raw_key, var_key = (
            "control_archive_sha256", "control_source_archive_sha256",
            "control_raw_sha256", "control_variables")
        profiles = json.loads((PARENT / "q1419_partial_pin/protocol.json").read_text())["profiles"]
        workload_id = profiles[str(args.degree)]["workload_id"]
        public_target = profiles[str(args.degree)]["public_target"]
    archive_bytes = archive_path.read_bytes()
    source_bytes = source_path.read_bytes()
    assert sha(archive_bytes) == record[archive_key]
    assert sha(source_bytes) == record[source_key]
    derived = gzip.decompress(archive_bytes)
    original = gzip.decompress(source_bytes)
    assert sha(derived) == record[raw_key]
    binary_record = build["per_degree"][name]
    binary = Path(binary_record["binary_path"])
    assert sha(binary.read_bytes()) == binary_record["binary_sha256"]
    out = HERE / "runs" / f"{name}_{args.kind}" / args.variant
    assert not out.exists()
    out.mkdir(parents=True)
    command = [str(binary), "-i", "INPUT"] + (["-x"] if args.variant == "xor_gauss" else [])
    start = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="q1464_workprobe_") as directory:
        xcnf = Path(directory) / "system.xcnf"
        xcnf.write_bytes(derived)
        actual = [str(xcnf) if item == "INPUT" else item for item in command]
        try:
            process = subprocess.run(actual, capture_output=True,
                                     timeout=protocol["limits"]["wall_seconds_per_run"])
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
    checkpoints = [int(value) for value in re.findall(r"^Q1464_BRANCH (\d+)$",
                                                      error_text, re.MULTILINE)]
    branch_cap = protocol["limits"]["left_branch_attempts_per_run"]
    assert all(value == 1 << index for index, value in enumerate(checkpoints))
    assert not checkpoints or checkpoints[-1] <= branch_cap
    cap_markers = [int(value) for value in re.findall(r"^Q1464_BRANCH_CAP (\d+)$",
                                                       error_text, re.MULTILINE)]
    variables = record[var_key]
    models = [line.strip() for line in output_text.splitlines()
              if len(line.strip()) == variables and set(line.strip()) <= {"0", "1", "2"}]
    replay = None
    if timed_out:
        status = "WALL_CAP_SEARCH_STARTED" if "Q1458_SEARCH_START" in error_text else "CENSORED_BEFORE_SEARCH"
    elif code == 42 and cap_markers == [branch_cap] and checkpoints[-1] == branch_cap:
        status = "BRANCH_CAP_REACHED"
    elif code != 0:
        status = "PRODUCER_FAILURE"
    elif "UNSAT" in output_text:
        status = "UNSAT_REPORTED_UNVERIFIED"
    elif len(models) == 1 and set(models[0]) <= {"0", "1"}:
        model = {index + 1: value == "1" for index, value in enumerate(models[0])}
        try:
            replay = {
                "derived": evaluate(derived, model),
                "original": evaluate(original, {key: value for key, value in model.items()
                                               if key <= int(original.splitlines()[0].split()[2])})}
            status = "SAT_REPLAYED_XCNF"
        except (AssertionError, ValueError) as error:
            replay = {"error": repr(error)}
            status = "MODEL_REPLAY_FAILED"
    else:
        status = "PRODUCER_FAILURE_NO_MODEL"
    receipt = {"proposal_id": "Q1464", "candidate_id": None, "run_id": None,
               "isogeny": "none", "degree": args.degree, "kind": args.kind,
               "variant": args.variant, "ordinary_query": args.kind == "ordinary",
               "curve_id": record["curve_id"], "workload_id": workload_id,
               "factor_base_actual_B": record["factor_base_actual_B"],
               "factor_base_folded_columns_K": record["factor_base_folded_columns_K"],
               "factor_base_enumerated_set_sha256": record["factor_base_enumerated_set_sha256"],
               "public_target": public_target,
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
               "wall_limit_seconds": protocol["limits"]["wall_seconds_per_run"],
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
    print(json.dumps({"cell": cell, "status": status,
                      "branch_lower_bound": receipt["branch_lower_bound"],
                      "wall_seconds": wall, "user_cpu_seconds": usage.ru_utime}))


if __name__ == "__main__":
    main()

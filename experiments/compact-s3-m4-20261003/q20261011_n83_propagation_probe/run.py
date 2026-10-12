#!/usr/bin/env python3
"""Record Q1473 propagation work on the frozen N83 ordinary point."""
from __future__ import annotations

import gzip
import hashlib
import importlib.util
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
Q1473 = HERE.parent / "q20261011_selector_polarity"
Q1460 = HERE.parent / "q20261011_wdsat_shared_prefix"
sys.path.insert(0, str(Q1473))
sys.path.insert(0, str(Q1460))
from prepare import evaluate  # noqa: E402
spec = importlib.util.spec_from_file_location("q1473_run_for_q1474", Q1473 / "run.py")
assert spec is not None and spec.loader is not None
prior_run = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prior_run)
check_group_relation = prior_run.check_group_relation


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def cpu_limit(soft: int, hard: int):
    def apply() -> None:
        resource.setrlimit(resource.RLIMIT_CPU, (soft, hard))
    return apply


def parse_model(stdout: bytes, variables: int) -> dict[int, bool] | None:
    models = [line.strip() for line in stdout.decode("ascii", "replace").splitlines()
              if len(line.strip()) == variables and set(line.strip()) <= {"0", "1"}]
    assert len(models) <= 1
    return ({index + 1: bit == "1" for index, bit in enumerate(models[0])}
            if models else None)


def run_one(phase: int, protocol: dict, frozen: dict, derived: bytes,
            original: bytes, target: dict) -> dict:
    out = HERE / "runs" / f"phase{phase}"
    assert not out.exists()
    out.mkdir(parents=True)
    stdout_path, stderr_path = out / "solver.stdout.txt", out / "solver.stderr.txt"
    env = os.environ.copy()
    env.update(Q1469_ORDER_MODE="selector_pair_mids", Q1472_PHASE_INDEX="0",
               Q1473_SELECTOR_PHASE=str(phase))
    cap = protocol["checkpoint_left_branches"]
    started = time.monotonic()
    prior_usage = resource.getrusage(resource.RUSAGE_CHILDREN)
    checkpoint_seen = False
    wall_cap = False
    with tempfile.TemporaryDirectory(prefix="q1474_", dir="/Volumes/SSD990/llm/tmp") as tmp:
        input_path = Path(tmp) / "system.xcnf"
        input_path.write_bytes(derived)
        with stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
            process = subprocess.Popen([frozen["binary_path"], "-i", str(input_path)],
                                       stdout=stdout, stderr=stderr, env=env,
                                       preexec_fn=cpu_limit(
                                           protocol["cpu_soft_seconds_per_phase"],
                                           protocol["cpu_hard_seconds_per_phase"]))
            deadline = time.monotonic() + protocol["wall_seconds_per_phase"]
            marker = re.compile(rb"^Q1473_WORK " + str(cap).encode() + rb" \d+ \d+$", re.M)
            while process.poll() is None:
                if marker.search(stderr_path.read_bytes()):
                    checkpoint_seen = True
                    process.terminate()
                    break
                if time.monotonic() >= deadline:
                    wall_cap = True
                    process.terminate()
                    break
                time.sleep(0.25)
            try:
                code = process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                code = process.wait(timeout=5)
    elapsed = time.monotonic() - started
    usage = resource.getrusage(resource.RUSAGE_CHILDREN)
    stdout, stderr = stdout_path.read_bytes(), stderr_path.read_bytes()
    text = stderr.decode("ascii", "replace")
    checkpoints = [int(value) for value in re.findall(r"^Q1464_BRANCH (\d+)$", text, re.M)]
    work = [list(map(int, row)) for row in re.findall(
        r"^Q1473_WORK (\d+) (\d+) (\d+)$", text, re.M)]
    assert [row[0] for row in work] == checkpoints
    assert checkpoints == [1 << index for index in range(len(checkpoints))]
    assert all(work[i][1] >= work[i - 1][1] and work[i][2] >= work[i - 1][2]
               for i in range(1, len(work)))
    checkpoint_seen = checkpoint_seen or any(row[0] == cap for row in work)
    model = parse_model(stdout, frozen["ordinary_cell"]["derived_variables"])
    replay = None
    relation = None
    if model is not None:
        try:
            replay = {"derived": evaluate(derived, model),
                      "original": evaluate(original, {i: model[i] for i in range(
                          1, frozen["ordinary_cell"]["original_variables"] + 1)})}
            relation = check_group_relation(model, target["public_target"],
                                            target["raw_preimage_x_coordinates"])
        except (AssertionError, ValueError) as error:
            replay = {"error": repr(error)}
    marker_ok = (text.splitlines().count("Q1469_ORDER selector_pair_mids 168") == 1 and
                 text.splitlines().count("Q1472_PHASE 0 0") == 1 and
                 text.splitlines().count(f"Q1473_SELECTOR_PHASE {phase} 2140 2141") == 1)
    search_started = "Q1458_SEARCH_START" in text
    if relation and relation.get("status") == "verified_four_point_relation":
        status = "VERIFIED_RELATION"
    elif model is not None:
        status = "MODEL_REPLAY_FAILED"
    elif checkpoint_seen and search_started and marker_ok:
        status = "CHECKPOINT_TERMINATED"
    elif wall_cap and not search_started:
        status = "CENSORED_BEFORE_SEARCH"
    elif wall_cap:
        status = "WALL_CAP_SEARCH_STARTED"
    elif code in (-signal.SIGXCPU, -signal.SIGKILL):
        status = "CPU_CAP_SEARCH_STARTED" if search_started else "CPU_CAP_BEFORE_SEARCH"
    else:
        status = "PRODUCER_FAILURE"
    receipt = {
        "proposal_id": "Q1474", "candidate_id": None, "run_id": None,
        "curve_id": protocol["curve_id"], "workload_id": protocol["workload_id"],
        "isogeny": "none", "factor_base_actual_B": protocol["factor_base_actual_B"],
        "factor_base_folded_columns_K": protocol["factor_base_folded_columns_K"],
        "phase": phase, "flip_ids": frozen["phase_schedule"][str(phase)]["flip_ids"],
        "status": status, "return_code": code, "search_started": search_started,
        "marker_ok": marker_ok, "wall_cap": wall_cap,
        "branch_checkpoints": checkpoints, "work_checkpoints": work,
        "branch_lower_bound": checkpoints[-1] if checkpoints else 0,
        "checkpoint_left_branches": cap,
        "cnf_set_true_calls_at_checkpoint": next((row[1] for row in work if row[0] == cap), None),
        "xor_set_true_calls_at_checkpoint": next((row[2] for row in work if row[0] == cap), None),
        "model_replay": replay, "group_replay": relation,
        "verified_natural_relations": int(status == "VERIFIED_RELATION"),
        "natural_relation_yield_estimate": None,
        "solver_wall_seconds_exploratory": elapsed,
        "user_cpu_seconds": usage.ru_utime - prior_usage.ru_utime,
        "system_cpu_seconds": usage.ru_stime - prior_usage.ru_stime,
        "maxrss_children_cumulative_bytes_darwin": usage.ru_maxrss,
        "stdout_sha256": sha(stdout_path), "stderr_sha256": sha(stderr_path),
        "binary_sha256": frozen["binary_sha256"], "freeze_sha256": sha(HERE / "freeze.json"),
        "source_sha256": sha(Path(__file__)),
        "complete_n83_decomposition_work_log2": None,
        "complete_n131_solve_work_log2": None}
    (out / "receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    return receipt


def main() -> None:
    assert not (HERE / "drive_receipt.json").exists()
    protocol = json.loads((HERE / "protocol.json").read_text())
    frozen = json.loads((HERE / "freeze.json").read_text())
    for name, digest in frozen["files_sha256"].items():
        assert sha(HERE / name) == digest
    assert sha(Path(frozen["binary_path"])) == frozen["binary_sha256"]
    for name, file in (("q1473_freeze", "freeze.json"),
                       ("q1473_build", "build_receipt.json"),
                       ("q1473_smoke", "smoke_receipt.json"),
                       ("q1473_target", "target.json")):
        assert sha(Q1473 / file) == frozen[f"{name}_sha256"]
    cell = frozen["ordinary_cell"]
    archives = {}
    for key in ("derived", "source"):
        path = Path(cell[f"{key}_archive_path"])
        assert sha(path) == cell[f"{key}_archive_sha256"]
        archives[key] = gzip.decompress(path.read_bytes())
        assert hashlib.sha256(archives[key]).hexdigest() == cell[f"{key}_raw_sha256"]
    target = json.loads((Q1473 / "target.json").read_text())
    assert target["workload_id"] == protocol["workload_id"]
    rows = []
    for phase in protocol["phase_order"]:
        row = run_one(phase, protocol, frozen, archives["derived"],
                      archives["source"], target)
        rows.append(row)
        print("Q1474", phase, row["status"], row["branch_lower_bound"], flush=True)
        if row["status"] != "CHECKPOINT_TERMINATED":
            break
    result = {"proposal_id": "Q1474", "status": "COMPLETE_SCHEDULE" if len(rows) == 4
              else "STOPPED_AT_GATE", "phase_statuses": [row["status"] for row in rows],
              "new_ordinary_attempts": len(rows),
              "new_ordinary_wall_seconds_exploratory": sum(
                  row["solver_wall_seconds_exploratory"] for row in rows),
              "new_ordinary_user_cpu_seconds": sum(row["user_cpu_seconds"] for row in rows),
              "new_verified_relations": sum(row["verified_natural_relations"] for row in rows),
              "freeze_sha256": sha(HERE / "freeze.json"),
              "complete_n83_decomposition_work_log2": None,
              "complete_n131_solve_work_log2": None,
              "degree131_challenge_gap_bits": None}
    (HERE / "drive_receipt.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()

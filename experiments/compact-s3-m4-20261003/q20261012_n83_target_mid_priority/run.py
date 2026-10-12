#!/usr/bin/env python3
"""First-pair stop screen for target-side N83 chained-S3 priorities."""
import gzip
import hashlib
import json
import os
import re
import resource
import signal
import subprocess
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
Q1488 = PARENT / "q20261012_n83_first_pair_restart"
PAIR = re.compile(rb"^Q1488_FIRST_PAIR (\d+) (\d+) (\d+) ([01]{166})$", re.M)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def limit_cpu(soft, hard):
    def apply():
        resource.setrlimit(resource.RLIMIT_CPU, (soft, hard))
    return apply


def run_cell(label, phase, mode, protocol, frozen, build):
    folder = HERE / "runs" / f"{label}_phase{phase}_{mode}"
    assert not folder.exists()
    folder.mkdir(parents=True)
    cell = frozen["inputs"][label]
    archive = Path(cell["derived_path"])
    assert sha(archive) == cell["derived_sha256"]
    xcnf = gzip.decompress(archive.read_bytes())
    assert hashlib.sha256(xcnf).hexdigest() == cell["derived_raw_sha256"]
    binary = Path(build["binary_path"])
    assert sha(binary) == build["binary_sha256"]
    env = os.environ.copy()
    env.update(Q1469_ORDER_MODE=mode, Q1472_PHASE_INDEX="0",
               Q1473_SELECTOR_PHASE="0", Q1481_LEAF_MASK=str(phase))
    stdout, stderr = folder / "solver.stdout.txt", folder / "solver.stderr.txt"
    started = time.monotonic()
    terminated_reason = None
    with tempfile.TemporaryDirectory(prefix="q1507_", dir="/Volumes/SSD990/llm/tmp") as tmp:
        system = Path(tmp) / "system.xcnf"
        system.write_bytes(xcnf)
        with stdout.open("wb") as out, stderr.open("wb") as err:
            child = subprocess.Popen([str(binary), "-i", str(system)],
                                     stdout=out, stderr=err, env=env,
                                     preexec_fn=limit_cpu(
                                         protocol["cpu_soft_seconds_per_cell"],
                                         protocol["cpu_hard_seconds_per_cell"]))
            sent_at = None
            deadline = time.monotonic() + protocol["wall_seconds_per_cell"]
            while True:
                pid, status, usage = os.wait4(child.pid, os.WNOHANG)
                if pid:
                    child.returncode = os.waitstatus_to_exitcode(status)
                    break
                now = time.monotonic()
                if sent_at is None:
                    if PAIR.search(stderr.read_bytes()):
                        terminated_reason = "FIRST_PAIR_MARKER"
                    elif now >= deadline:
                        terminated_reason = "WALL_CAP"
                    if terminated_reason:
                        child.terminate()
                        sent_at = now
                elif now - sent_at > 5:
                    child.kill()
                time.sleep(0.05)
    elapsed = time.monotonic() - started
    log = stderr.read_text(errors="replace")
    markers = [(int(a), int(b), int(c), d.decode()) for a, b, c, d in
               PAIR.findall(stderr.read_bytes())]
    assert len(markers) <= 1
    pair = markers[0] if markers else None
    expected_priority_len = 334 if mode in ("q1507_target_leaf_first",
                                             "selector_leaf_interleave") else 168
    order_ok = f"Q1469_ORDER {mode} {expected_priority_len}" in log
    mask_count = len(frozen["mask_schedule"][str(phase)]["flip_ids"])
    mask_ok = f"Q1481_MASK {phase} {mask_count}" in log
    search_started = "Q1458_SEARCH_START" in log
    if pair and order_ok and mask_ok and search_started:
        outcome = "FIRST_PAIR_TERMINATED"
    elif "Q1464_BRANCH_CAP 1048576" in log and search_started:
        outcome = "BRANCH_CAP_SEARCH_STARTED"
    elif terminated_reason == "WALL_CAP":
        outcome = "WALL_CAP_SEARCH_STARTED" if search_started else "CENSORED_BEFORE_SEARCH"
    elif child.returncode in (-signal.SIGXCPU, -signal.SIGKILL):
        outcome = "CPU_CAP_SEARCH_STARTED" if search_started else "CPU_CAP_BEFORE_SEARCH"
    elif child.returncode == 0 and stdout.stat().st_size:
        outcome = "MODEL_REQUIRES_REPLAY"
    else:
        outcome = "PRODUCER_FAILURE"
    row = {"proposal_id": "Q1507", "candidate_id": None, "run_id": None,
           "curve_id": protocol["curve_id"], "workload_id": cell["workload_id"],
           "factor_base_actual_B": protocol["factor_base_actual_B"],
           "factor_base_folded_columns_K": protocol["factor_base_folded_columns_K"],
           "isogeny": "none", "point_decomposition_stage_code": "PDP4sat",
           "input": label, "mode": mode, "phase": phase,
           "status": outcome, "return_code": child.returncode,
           "terminated_reason": terminated_reason,
           "search_started": search_started, "order_marker_ok": order_ok,
           "mask_marker_ok": mask_ok,
           "first_pair_branch": pair[0] if pair else None,
           "first_pair_cnf_calls": pair[1] if pair else None,
           "first_pair_xor_calls": pair[2] if pair else None,
           "first_pair_combined_calls": pair[1] + pair[2] if pair else None,
           "first_pair_bits": pair[3] if pair else None,
           "solver_wall_seconds_exploratory": elapsed,
           "child_user_cpu_seconds": usage.ru_utime,
           "child_system_cpu_seconds": usage.ru_stime,
           "child_peak_rss_bytes_darwin": usage.ru_maxrss,
           "stdout_sha256": sha(stdout), "stderr_sha256": sha(stderr),
           "binary_sha256": build["binary_sha256"],
           "input_sha256": cell["derived_sha256"],
           "complete_n83_decomposition_work_log2": None,
           "complete_n131_solve_work_log2": None}
    (folder / "receipt.json").write_text(json.dumps(row, indent=2,
                                                   sort_keys=True) + "\n")
    print(label, mode, outcome, row["first_pair_branch"],
          row["first_pair_combined_calls"], flush=True)
    return row


def main():
    protocol = read(HERE / "protocol.json")
    frozen = read(Q1488 / "freeze.json")
    build = read(HERE / "build_receipt.json")
    assert sha(Q1488 / "freeze.json") == protocol["q1488_freeze_sha256"]
    assert sha(HERE / "build.py") == build["source_sha256"]
    assert not (HERE / "result.json").exists()
    rows = []
    for phase in protocol["phases"]:
        for label in ("selected", "holdout"):
            for mode in protocol["modes"]:
                folder = HERE / "runs" / f"{label}_phase{phase}_{mode}"
                if folder.exists():
                    row = read(folder / "receipt.json")
                    assert row["input"] == label and row["mode"] == mode and row["phase"] == phase
                else:
                    row = run_cell(label, phase, mode, protocol, frozen, build)
                rows.append(row)
    result = {"proposal_id": "Q1507", "candidate_id": None, "run_id": None,
              "curve_id": protocol["curve_id"], "isogeny": "none",
              "point_decomposition_stage_code": "PDP4sat",
              "protocol_sha256": sha(HERE / "protocol.json"),
              "source_sha256": sha(Path(__file__)),
              "build_receipt_sha256": sha(HERE / "build_receipt.json"),
              "rows": [{"input": row["input"], "phase": row["phase"],
                        "mode": row["mode"],
                        "status": row["status"],
                        "receipt_sha256": sha(HERE / "runs" /
                                              f"{row['input']}_phase{row['phase']}_{row['mode']}" /
                                              "receipt.json")} for row in rows],
              "complete_n83_decomposition_work_log2": None,
              "complete_n131_solve_work_log2": None}
    (HERE / "result.json").write_text(json.dumps(result, indent=2,
                                                sort_keys=True) + "\n")


if __name__ == "__main__":
    main()

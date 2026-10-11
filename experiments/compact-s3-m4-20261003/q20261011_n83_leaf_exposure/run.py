#!/usr/bin/env python3
"""Run matched branch-order leaf-exposure screens on frozen N83 points."""
from __future__ import annotations

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


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def cpu_limit(soft: int, hard: int):
    def apply() -> None:
        resource.setrlimit(resource.RLIMIT_CPU, (soft, hard))
    return apply


def run_one(name: str, order: str, protocol: dict, frozen: dict,
            binary: dict) -> dict:
    cell = frozen["inputs"][name]
    folder = HERE / "runs" / f"{name}_{order}"
    assert not folder.exists()
    folder.mkdir(parents=True)
    derived = Path(cell["derived_path"])
    assert sha(derived) == cell["derived_sha256"]
    data = gzip.decompress(derived.read_bytes())
    assert hashlib.sha256(data).hexdigest() == cell["derived_raw_sha256"]
    assert sha(Path(binary["binary_path"])) == binary["binary_sha256"]
    stdout_path, stderr_path = folder / "solver.stdout.txt", folder / "solver.stderr.txt"
    env = os.environ.copy()
    env.update(Q1469_ORDER_MODE=order, Q1472_PHASE_INDEX="0",
               Q1473_SELECTOR_PHASE="0")
    cap = protocol["branch_checkpoint"]
    start = time.monotonic()
    usage0 = resource.getrusage(resource.RUSAGE_CHILDREN)
    checkpoint_seen = False
    wall_cap = False
    with tempfile.TemporaryDirectory(prefix="q1478_", dir="/Volumes/SSD990/llm/tmp") as tmp:
        system = Path(tmp) / "system.xcnf"
        system.write_bytes(data)
        with stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
            child = subprocess.Popen([binary["binary_path"], "-i", str(system)],
                                     stdout=stdout, stderr=stderr, env=env,
                                     preexec_fn=cpu_limit(
                                         protocol["cpu_soft_seconds_per_cell"],
                                         protocol["cpu_hard_seconds_per_cell"]))
            deadline = time.monotonic() + protocol["wall_seconds_per_cell"]
            marker = re.compile(rb"^Q1478_READY " + str(cap).encode() + rb" ", re.M)
            while child.poll() is None:
                if marker.search(stderr_path.read_bytes()):
                    checkpoint_seen = True
                    child.terminate()
                    break
                if time.monotonic() >= deadline:
                    wall_cap = True
                    child.terminate()
                    break
                time.sleep(0.2)
            try:
                code = child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                child.kill()
                code = child.wait(timeout=5)
    elapsed = time.monotonic() - start
    usage = resource.getrusage(resource.RUSAGE_CHILDREN)
    output = stderr_path.read_text(errors="replace")
    ready = [tuple(map(int, row)) for row in re.findall(
        r"^Q1478_READY (\d+) (\d+) (\d+) (\d+) (\d+) (\d+)$", output, re.M)]
    work = [tuple(map(int, row)) for row in re.findall(
        r"^Q1473_WORK (\d+) (\d+) (\d+)$", output, re.M)]
    markers = [int(v) for v in re.findall(r"^Q1464_BRANCH (\d+)$", output, re.M)]
    assert [row[0] for row in ready] == [row[0] for row in work] == markers
    assert markers == [1 << i for i in range(len(markers))]
    assert all(all(row[j] >= old[j] for j in range(1, 6))
               for old, row in zip(ready, ready[1:]))
    assert all(row[1] <= row[0] and row[2] <= row[0] and row[5] <= min(row[1:3])
               and row[3] <= row[1] and row[4] <= row[2] for row in ready)
    checkpoint_seen = checkpoint_seen or cap in markers
    search_started = "Q1458_SEARCH_START" in output
    order_marker = output.splitlines().count(f"Q1469_ORDER {order} 168") == 1
    if checkpoint_seen and search_started and order_marker:
        status = "CHECKPOINT_TERMINATED"
    elif wall_cap and search_started:
        status = "WALL_CAP_SEARCH_STARTED"
    elif wall_cap:
        status = "CENSORED_BEFORE_SEARCH"
    elif code in (-signal.SIGXCPU, -signal.SIGKILL):
        status = "CPU_CAP_SEARCH_STARTED" if search_started else "CPU_CAP_BEFORE_SEARCH"
    elif code == 0 and stdout_path.stat().st_size:
        status = "MODEL_REQUIRES_REPLAY"
    else:
        status = "PRODUCER_FAILURE"
    row = {"proposal_id": "Q1478", "candidate_id": None, "run_id": None,
           "curve_id": protocol["curve_id"], "workload_id": cell["workload_id"],
           "factor_base_actual_B": protocol["factor_base_actual_B"],
           "factor_base_folded_columns_K": protocol["factor_base_folded_columns_K"],
           "isogeny": "none", "input": name, "order": order,
           "status": status, "return_code": code, "search_started": search_started,
           "order_marker_ok": order_marker, "wall_cap": wall_cap,
           "ready_checkpoints": ready, "work_checkpoints": work,
           "branch_lower_bound": markers[-1] if markers else 0,
           "solver_wall_seconds_exploratory": elapsed,
           "solver_user_cpu_seconds_exploratory": usage.ru_utime - usage0.ru_utime,
           "solver_system_cpu_seconds_exploratory": usage.ru_stime - usage0.ru_stime,
           "child_peak_rss_cumulative_bytes_darwin": usage.ru_maxrss,
           "binary_sha256": binary["binary_sha256"],
           "input_sha256": cell["derived_sha256"],
           "stdout_sha256": sha(stdout_path), "stderr_sha256": sha(stderr_path),
           "freeze_sha256": sha(HERE / "freeze.json"),
           "complete_n83_decomposition_work_log2": None,
           "complete_n131_solve_work_log2": None}
    (folder / "receipt.json").write_text(json.dumps(row, indent=2,
                                                   sort_keys=True) + "\n")
    print("Q1478", name, order, status, markers[-1] if markers else 0,
          flush=True)
    return row


def main() -> None:
    assert not (HERE / "drive_receipt.json").exists()
    frozen = json.loads((HERE / "freeze.json").read_text())
    protocol = json.loads((HERE / "protocol.json").read_text())
    build = json.loads((HERE / "build_receipt.json").read_text())
    for name, digest in frozen["files_sha256"].items():
        assert sha(HERE / name) == digest
    assert build["freeze_sha256"] == sha(HERE / "freeze.json")
    rows = []
    control = run_one("control", "q1478_leafpair_first", protocol, frozen, build)
    rows.append(control)
    if control["status"] != "MODEL_REQUIRES_REPLAY":
        raise RuntimeError(f"Q1478 control failed: {control['status']}")
    for name in ("selected", "holdout"):
        for order in protocol["orders"]:
            row = run_one(name, order, protocol, frozen, build)
            rows.append(row)
            if row["status"] not in ("CHECKPOINT_TERMINATED", "MODEL_REQUIRES_REPLAY"):
                break
    result = {"proposal_id": "Q1478", "candidate_id": None, "run_id": None,
              "rows": [{"input": row["input"], "order": row["order"],
                        "status": row["status"],
                        "receipt_sha256": sha(HERE / "runs" /
                                              f"{row['input']}_{row['order']}" / "receipt.json")}
                       for row in rows],
              "new_ordinary_attempts": sum(row["input"] != "control" for row in rows),
              "solver_wall_phase_sum_seconds_exploratory": sum(
                  row["solver_wall_seconds_exploratory"] for row in rows),
              "solver_user_cpu_sum_seconds_exploratory": sum(
                  row["solver_user_cpu_seconds_exploratory"] for row in rows),
              "freeze_sha256": sha(HERE / "freeze.json"),
              "complete_n83_decomposition_work_log2": None,
              "complete_n131_solve_work_log2": None,
              "degree131_challenge_gap_bits": None}
    (HERE / "drive_receipt.json").write_text(json.dumps(result, indent=2,
                                                        sort_keys=True) + "\n")


if __name__ == "__main__":
    main()

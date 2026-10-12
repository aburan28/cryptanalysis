#!/usr/bin/env python3
"""Measure exact common-root implication propagation on N83 points."""
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


def run_one(name: str, phase: int, protocol: dict, frozen: dict) -> dict:
    cell = frozen["inputs"][name]
    folder = HERE / "runs" / f"{name}_phase{phase}"
    assert not folder.exists()
    folder.mkdir(parents=True)
    archive = Path(cell["derived_path"])
    assert sha(archive) == cell["derived_sha256"]
    data = gzip.decompress(archive.read_bytes())
    assert hashlib.sha256(data).hexdigest() == cell["derived_raw_sha256"]
    build = json.loads((HERE / "build_receipt.json").read_text())
    assert build["freeze_sha256"] == sha(HERE / "freeze.json")
    binary = Path(build["binary_path"])
    assert sha(binary) == build["binary_sha256"]
    stdout_path, stderr_path = folder / "solver.stdout.txt", folder / "solver.stderr.txt"
    env = os.environ.copy()
    env.update(Q1469_ORDER_MODE=protocol["branch_order"],
               Q1472_PHASE_INDEX="0", Q1473_SELECTOR_PHASE="0",
               Q1481_LEAF_MASK=str(phase))
    cap = protocol["branch_checkpoint"]
    started = time.monotonic()
    usage0 = resource.getrusage(resource.RUSAGE_CHILDREN)
    checkpoint_seen = False
    wall_cap = False
    with tempfile.TemporaryDirectory(prefix="q1486_", dir="/Volumes/SSD990/llm/tmp") as tmp:
        system = Path(tmp) / "system.xcnf"
        system.write_bytes(data)
        with stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
            child = subprocess.Popen([str(binary), "-i", str(system)],
                                     stdout=stdout, stderr=stderr, env=env,
                                     preexec_fn=cpu_limit(
                                         protocol["cpu_soft_seconds_per_cell"],
                                         protocol["cpu_hard_seconds_per_cell"]))
            deadline = time.monotonic() + protocol["wall_seconds_per_cell"]
            marker = re.compile(rb"^Q1479_SUMMARY " + str(cap).encode() + rb" ", re.M)
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
    elapsed = time.monotonic() - started
    usage = resource.getrusage(resource.RUSAGE_CHILDREN)
    log = stderr_path.read_text(errors="replace")
    summaries = [tuple(map(int, v)) for v in re.findall(
        r"^Q1479_SUMMARY (\d+) (\d+) (\d+) (\d+)$", log, re.M)]
    ready = [tuple(map(int, v)) for v in re.findall(
        r"^Q1478_READY (\d+) (\d+) (\d+) (\d+) (\d+) (\d+)$", log, re.M)]
    work = [tuple(map(int, v)) for v in re.findall(
        r"^Q1473_WORK (\d+) (\d+) (\d+)$", log, re.M)]
    assert [v[0] for v in summaries] == [v[0] for v in ready] == [v[0] for v in work]
    assert [v[0] for v in ready] == [1 << i for i in range(len(ready))]
    found = [bits for _, bits in re.findall(r"^Q1479_PAIR1 (\d+) ([01]{166})$",
                                                log, re.M)]
    assert len(found) == len(set(found))
    checkpoint_seen = checkpoint_seen or cap in [v[0] for v in summaries]
    search_started = "Q1458_SEARCH_START" in log
    mask_count = len(frozen["mask_schedule"][str(phase)]["flip_ids"])
    marker_ok = (log.splitlines().count(
        f"Q1469_ORDER {protocol['branch_order']} 168") == 1 and
        log.splitlines().count("Q1472_PHASE 0 0") == 1 and
        log.splitlines().count("Q1473_SELECTOR_PHASE 0 2140 2141") == 1 and
        log.splitlines().count(f"Q1481_MASK {phase} {mask_count}") == 1)
    if checkpoint_seen and search_started and marker_ok:
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
    at_cap = next((v for v in summaries if v[0] == cap), None)
    ready_cap = next((v for v in ready if v[0] == cap), None)
    work_cap = next((v for v in work if v[0] == cap), None)
    if at_cap and ready_cap:
        assert at_cap[1] + at_cap[2] + at_cap[3] == ready_cap[4]
        assert at_cap[1] == len(found)
        assert at_cap[1] <= protocol["distinct_pair1_sample_cap_per_cell"]
    row = {"proposal_id": "Q1486", "candidate_id": None, "run_id": None,
           "curve_id": protocol["curve_id"], "workload_id": cell["workload_id"],
           "factor_base_actual_B": protocol["factor_base_actual_B"],
           "factor_base_folded_columns_K": protocol["factor_base_folded_columns_K"],
           "isogeny": "none", "input": name, "phase": phase,
           "flip_count": mask_count, "status": status, "return_code": code,
           "search_started": search_started, "marker_ok": marker_ok,
           "wall_cap": wall_cap, "branch_lower_bound": ready[-1][0] if ready else 0,
           "ready_at_cap": ready_cap, "work_at_cap": work_cap,
           "distinct_summary_at_cap": at_cap,
           "sampled_pair1_count": len(found),
           "solver_wall_seconds_exploratory": elapsed,
           "solver_user_cpu_seconds_exploratory": usage.ru_utime - usage0.ru_utime,
           "solver_system_cpu_seconds_exploratory": usage.ru_stime - usage0.ru_stime,
           "child_peak_rss_cumulative_bytes_darwin": usage.ru_maxrss,
           "stdout_sha256": sha(stdout_path), "stderr_sha256": sha(stderr_path),
           "binary_sha256": build["binary_sha256"],
           "input_sha256": cell["derived_sha256"],
           "freeze_sha256": sha(HERE / "freeze.json"),
           "complete_n83_decomposition_work_log2": None,
           "complete_n131_solve_work_log2": None}
    (folder / "receipt.json").write_text(json.dumps(row, indent=2,
                                                   sort_keys=True) + "\n")
    print("Q1486", name, phase, status, len(found), flush=True)
    return row


def main() -> None:
    assert not (HERE / "drive_receipt.json").exists()
    protocol = json.loads((HERE / "protocol.json").read_text())
    frozen = json.loads((HERE / "freeze.json").read_text())
    for name, digest in frozen["files_sha256"].items():
        assert sha(HERE / name) == digest
    rows = []
    for name in ("selected", "holdout"):
        for phase in protocol["polarity_phases"]:
            row = run_one(name, phase, protocol, frozen)
            rows.append(row)
            if row["status"] in ("PRODUCER_FAILURE", "CENSORED_BEFORE_SEARCH",
                                 "CPU_CAP_BEFORE_SEARCH"):
                break
    drive = {"proposal_id": "Q1486", "candidate_id": None, "run_id": None,
             "rows": [{"input": r["input"], "phase": r["phase"],
                       "status": r["status"],
                       "receipt_sha256": sha(HERE / "runs" /
                                             f"{r['input']}_phase{r['phase']}" /
                                             "receipt.json")} for r in rows],
             "new_ordinary_attempts": len(rows),
             "solver_wall_phase_sum_seconds_exploratory": sum(
                 r["solver_wall_seconds_exploratory"] for r in rows),
             "solver_user_cpu_sum_seconds_exploratory": sum(
                 r["solver_user_cpu_seconds_exploratory"] for r in rows),
             "freeze_sha256": sha(HERE / "freeze.json"),
             "complete_n83_decomposition_work_log2": None,
             "complete_n131_solve_work_log2": None,
             "degree131_challenge_gap_bits": None}
    (HERE / "drive_receipt.json").write_text(json.dumps(drive, indent=2,
                                                        sort_keys=True) + "\n")


if __name__ == "__main__":
    main()

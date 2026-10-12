#!/usr/bin/env python3
"""Continue matched phase-2 ordinary N83 orders through full S3 search cap."""
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
MODES = ("q1507_target_leaf_first", "selector_leaf_interleave")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def cpu_limit(soft, hard):
    def apply():
        resource.setrlimit(resource.RLIMIT_CPU, (soft, hard))
    return apply


def main():
    protocol, build, frozen = (read(path) for path in
                               (HERE / "protocol.json", HERE / "build_receipt.json",
                                Q1488 / "freeze.json"))
    binary = Path(build["binary_path"])
    assert sha(binary) == build["binary_sha256"]
    assert not (HERE / "continuation_result.json").exists()
    rows = []
    for label in ("selected", "holdout"):
        cell = frozen["inputs"][label]
        archive = Path(cell["derived_path"])
        assert sha(archive) == cell["derived_sha256"]
        raw = gzip.decompress(archive.read_bytes())
        assert hashlib.sha256(raw).hexdigest() == cell["derived_raw_sha256"]
        for mode in MODES:
            folder = HERE / "continuation" / f"{label}_{mode}"
            assert not folder.exists()
            folder.mkdir(parents=True)
            stdout, stderr = folder / "solver.stdout.txt", folder / "solver.stderr.txt"
            env = os.environ.copy()
            env.update(Q1469_ORDER_MODE=mode, Q1472_PHASE_INDEX="0",
                       Q1473_SELECTOR_PHASE="0", Q1481_LEAF_MASK="2")
            started = time.monotonic()
            wall_cap = False
            with tempfile.TemporaryDirectory(prefix="q1507_full_",
                                             dir="/Volumes/SSD990/llm/tmp") as tmp:
                system = Path(tmp) / "system.xcnf"
                system.write_bytes(raw)
                with stdout.open("wb") as out, stderr.open("wb") as err:
                    child = subprocess.Popen([str(binary), "-i", str(system)],
                                             stdout=out, stderr=err, env=env,
                                             preexec_fn=cpu_limit(
                                                 protocol["cpu_soft_seconds_per_cell"],
                                                 protocol["cpu_hard_seconds_per_cell"]))
                    deadline = time.monotonic() + protocol["wall_seconds_per_cell"]
                    sent_at = None
                    while True:
                        pid, status, usage = os.wait4(child.pid, os.WNOHANG)
                        if pid:
                            child.returncode = os.waitstatus_to_exitcode(status)
                            break
                        now = time.monotonic()
                        if now >= deadline and sent_at is None:
                            wall_cap = True
                            child.terminate()
                            sent_at = now
                        elif sent_at is not None and now - sent_at > 5:
                            child.kill()
                        time.sleep(0.05)
            elapsed = time.monotonic() - started
            log = stderr.read_text(errors="replace")
            work = [tuple(map(int, v)) for v in re.findall(
                r"^Q1473_WORK (\d+) (\d+) (\d+)$", log, re.M)]
            pair = re.findall(r"^Q1488_FIRST_PAIR (\d+) (\d+) (\d+) ([01]{166})$",
                              log, re.M)
            assert len(pair) <= 1
            if child.returncode == 42 and "Q1464_BRANCH_CAP 1048576" in log:
                outcome = "BRANCH_CAP_SEARCH_STARTED"
            elif wall_cap:
                outcome = "WALL_CAP_SEARCH_STARTED"
            elif child.returncode in (-signal.SIGXCPU, -signal.SIGKILL):
                outcome = "CPU_CAP_SEARCH_STARTED"
            elif child.returncode == 0 and stdout.stat().st_size:
                outcome = "MODEL_REQUIRES_REPLAY"
            else:
                outcome = "PRODUCER_FAILURE"
            row = {"proposal_id": "Q1507", "candidate_id": None,
                   "run_id": None, "curve_id": protocol["curve_id"],
                   "factor_base_actual_B": protocol["factor_base_actual_B"],
                   "factor_base_folded_columns_K": protocol["factor_base_folded_columns_K"],
                   "isogeny": "none", "point_decomposition_stage_code": "PDP4sat",
                   "input": label, "workload_id": cell["workload_id"],
                   "phase": 2, "mode": mode, "status": outcome,
                   "return_code": child.returncode, "wall_cap": wall_cap,
                   "search_started": "Q1458_SEARCH_START" in log,
                   "first_pair_bits": pair[0][3] if pair else None,
                   "first_pair_combined_calls": int(pair[0][1]) + int(pair[0][2]) if pair else None,
                   "last_work_checkpoint": work[-1] if work else None,
                   "child_peak_rss_bytes_darwin": usage.ru_maxrss,
                   "child_user_cpu_seconds": usage.ru_utime,
                   "child_system_cpu_seconds": usage.ru_stime,
                   "solver_wall_seconds_exploratory": elapsed,
                   "stdout_sha256": sha(stdout), "stderr_sha256": sha(stderr),
                   "binary_sha256": build["binary_sha256"],
                   "input_sha256": cell["derived_sha256"],
                   "complete_n83_decomposition_work_log2": None,
                   "complete_n131_solve_work_log2": None}
            (folder / "receipt.json").write_text(json.dumps(row, indent=2,
                                                            sort_keys=True) + "\n")
            rows.append({"input": label, "mode": mode, "status": outcome,
                         "receipt_sha256": sha(folder / "receipt.json")})
            print(label, mode, outcome, row["last_work_checkpoint"], flush=True)
    (HERE / "continuation_result.json").write_text(json.dumps({
        "proposal_id": "Q1507", "candidate_id": None, "run_id": None,
        "curve_id": protocol["curve_id"], "isogeny": "none",
        "point_decomposition_stage_code": "PDP4sat",
        "protocol_sha256": sha(HERE / "protocol.json"),
        "build_receipt_sha256": sha(HERE / "build_receipt.json"),
        "source_sha256": sha(Path(__file__)), "rows": rows,
        "complete_n83_decomposition_work_log2": None,
        "complete_n131_solve_work_log2": None}, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()

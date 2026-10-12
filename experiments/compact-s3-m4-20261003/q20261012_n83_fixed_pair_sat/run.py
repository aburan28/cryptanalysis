#!/usr/bin/env python3
"""Freeze and run N83 chained-S3 continuation with the first pair fixed."""
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
Q1497 = PARENT / "q20261012_n83_restart_hyperparams"
Q1498 = PARENT / "q20261012_n83_distinct_restart_holdout"
Q1499 = PARENT / "q20261012_n83_full_continuation_pilot"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def save(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def fixed_system(raw, bits, lo, hi):
    assert len(bits) == hi - lo + 1 and set(bits) <= {"0", "1"}
    header, rest = raw.split(b"\n", 1)
    match = re.fullmatch(rb"p cnf (\d+) (\d+)", header)
    assert match, header
    variables, clauses = map(int, match.groups())
    assert hi <= variables
    units = b"".join((str(var if bit == "1" else -var) + " 0\n").encode()
                     for var, bit in zip(range(lo, hi + 1), bits))
    assert raw.endswith(b"\n")
    return f"p cnf {variables} {clauses + len(bits)}\n".encode() + rest + units


def freeze():
    assert not (HERE / "freeze.json").exists()
    protocol = read(HERE / "protocol.json")
    prior_freeze = read(Q1497 / "freeze.json")
    build = read(Q1497 / "build_receipt.json")
    binary = Path(build["binary_path"])
    assert sha(binary) == build["binary_sha256"]
    inputs = {}
    for label in ("selected", "holdout"):
        first_dir = Q1497 if label == "selected" else Q1498
        first = first_dir / "runs" / f"{label}_phase{protocol['first_pair_phase']}" / "receipt.json"
        pair = read(first)
        assert pair["status"] == "FIRST_PAIR_TERMINATED"
        assert pair["exact_usable_first_pair"] is True
        assert pair["workload_id"] == protocol[f"{label}_workload_id"]
        cell = prior_freeze["inputs"][label]
        archive = Path(cell["derived_path"])
        assert sha(archive) == cell["derived_sha256"]
        raw = gzip.decompress(archive.read_bytes())
        assert hashlib.sha256(raw).hexdigest() == cell["derived_raw_sha256"]
        lo, hi = protocol["first_pair_variables_inclusive"]
        transformed = fixed_system(raw, pair["first_pair_bits"], lo, hi)
        baseline = Q1499 / "runs" / f"{label}_phase50" / "receipt.json"
        inputs[label] = {"workload_id": pair["workload_id"],
                         "archive_path": str(archive),
                         "archive_sha256": sha(archive),
                         "raw_sha256": hashlib.sha256(raw).hexdigest(),
                         "fixed_system_sha256": hashlib.sha256(transformed).hexdigest(),
                         "first_pair_bits": pair["first_pair_bits"],
                         "first_pair_receipt_sha256": sha(first),
                         "baseline_receipt_sha256": sha(baseline)}
    save(HERE / "freeze.json", {
        "proposal_id": "Q1503", "candidate_id": None, "run_id": None,
        "protocol_sha256": sha(HERE / "protocol.json"),
        "source_sha256": sha(Path(__file__)),
        "q1497_freeze_sha256": sha(Q1497 / "freeze.json"),
        "q1497_build_receipt_sha256": sha(Q1497 / "build_receipt.json"),
        "binary_path": str(binary), "binary_sha256": sha(binary),
        "inputs": inputs})
    print("Q1503 frozen", sha(HERE / "freeze.json")[:12])


def cpu_limit(soft, hard):
    def apply():
        resource.setrlimit(resource.RLIMIT_CPU, (soft, hard))
    return apply


def run():
    assert not (HERE / "result.json").exists()
    protocol, frozen = read(HERE / "protocol.json"), read(HERE / "freeze.json")
    assert sha(HERE / "protocol.json") == frozen["protocol_sha256"]
    assert sha(Path(__file__)) == frozen["source_sha256"]
    assert sha(Path(frozen["binary_path"])) == frozen["binary_sha256"]
    rows = []
    for label in ("selected", "holdout"):
        cell = frozen["inputs"][label]
        archive = Path(cell["archive_path"])
        assert sha(archive) == cell["archive_sha256"]
        raw = gzip.decompress(archive.read_bytes())
        assert hashlib.sha256(raw).hexdigest() == cell["raw_sha256"]
        lo, hi = protocol["first_pair_variables_inclusive"]
        system_raw = fixed_system(raw, cell["first_pair_bits"], lo, hi)
        assert hashlib.sha256(system_raw).hexdigest() == cell["fixed_system_sha256"]
        for phase in protocol["mask_phases"]:
            folder = HERE / "runs" / f"{label}_phase{phase}"
            assert not folder.exists()
            folder.mkdir(parents=True)
            env = os.environ.copy()
            env.update(Q1469_ORDER_MODE=protocol["branch_order"],
                       Q1472_PHASE_INDEX="0", Q1473_SELECTOR_PHASE="0",
                       Q1481_LEAF_MASK=str(phase))
            with tempfile.TemporaryDirectory(prefix="q1503_",
                                             dir="/Volumes/SSD990/llm/tmp") as temp:
                system = Path(temp) / "fixed.xcnf"
                system.write_bytes(system_raw)
                start = time.monotonic()
                usage0 = resource.getrusage(resource.RUSAGE_CHILDREN)
                try:
                    process = subprocess.run(
                        [frozen["binary_path"], "-i", str(system)],
                        env=env, capture_output=True,
                        timeout=protocol["wall_seconds_per_cell"],
                        preexec_fn=cpu_limit(protocol["cpu_soft_seconds_per_cell"],
                                             protocol["cpu_hard_seconds_per_cell"]))
                    stdout, stderr = process.stdout, process.stderr
                    code, wall_cap = process.returncode, False
                except subprocess.TimeoutExpired as error:
                    stdout, stderr = error.stdout or b"", error.stderr or b""
                    code, wall_cap = None, True
                wall = time.monotonic() - start
                usage = resource.getrusage(resource.RUSAGE_CHILDREN)
            out, err = folder / "solver.stdout.txt", folder / "solver.stderr.txt"
            out.write_bytes(stdout)
            err.write_bytes(stderr)
            log = stderr.decode("utf8", "replace")
            checkpoints = [(int(a), int(b), int(c)) for a, b, c in
                           re.findall(r"^Q1473_WORK (\d+) (\d+) (\d+)$", log, re.M)]
            captured = re.findall(r"^Q1488_FIRST_PAIR \d+ \d+ \d+ ([01]{166})$",
                                  log, re.M)
            assert all(bits == cell["first_pair_bits"] for bits in captured)
            search_started = "Q1458_SEARCH_START" in log
            if code == 42 and "Q1464_BRANCH_CAP" in log and search_started:
                status = "BRANCH_CAP_SEARCH_STARTED"
            elif wall_cap and search_started:
                status = "WALL_CAP_SEARCH_STARTED"
            elif code in (-signal.SIGXCPU, -signal.SIGKILL) and search_started:
                status = "CPU_CAP_SEARCH_STARTED"
            elif b"SATISFIABLE" in stdout:
                status = "MODEL_UNVERIFIED"
            elif search_started:
                status = "NONCAP_EXIT_SEARCH_STARTED"
            else:
                status = "EXIT_BEFORE_SEARCH"
            row = {"proposal_id": "Q1503", "candidate_id": None,
                   "run_id": None, "curve_id": protocol["curve_id"],
                   "factor_base_actual_B": protocol["factor_base_actual_B"],
                   "factor_base_folded_columns_K": protocol["factor_base_folded_columns_K"],
                   "isogeny": "none", "point_decomposition_stage_code": "PDP4sat",
                   "input": label, "workload_id": cell["workload_id"],
                   "phase": phase, "fixed_first_pair_receipt_sha256":
                   cell["first_pair_receipt_sha256"],
                   "fixed_system_sha256": cell["fixed_system_sha256"],
                   "binary_sha256": frozen["binary_sha256"],
                   "status": status, "return_code": code, "wall_cap": wall_cap,
                   "search_started": search_started,
                   "first_pair_marker_count": len(captured),
                   "last_checkpoint": checkpoints[-1] if checkpoints else None,
                   "stdout_sha256": sha(out), "stderr_sha256": sha(err),
                   "wall_seconds_exploratory": wall,
                   "child_user_cpu_seconds_exploratory":
                   usage.ru_utime - usage0.ru_utime,
                   "child_system_cpu_seconds_exploratory":
                   usage.ru_stime - usage0.ru_stime,
                   "child_peak_rss_cumulative_bytes_darwin": usage.ru_maxrss,
                   "complete_n83_decomposition_work_log2": None,
                   "complete_n131_solve_work_log2": None}
            save(folder / "receipt.json", row)
            rows.append(row)
            print(label, phase, status, row["last_checkpoint"], flush=True)
            save(HERE / "result.partial.json", {"proposal_id": "Q1503",
                 "freeze_sha256": sha(HERE / "freeze.json"), "rows": rows})
    save(HERE / "result.json", {"proposal_id": "Q1503", "candidate_id": None,
         "run_id": None, "curve_id": protocol["curve_id"], "isogeny": "none",
         "point_decomposition_stage_code": "PDP4sat",
         "freeze_sha256": sha(HERE / "freeze.json"), "rows": rows,
         "complete_n83_decomposition_work_log2": None,
         "complete_n131_solve_work_log2": None})


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in ("freeze", "run"):
        raise SystemExit("usage: run.py {freeze|run}")
    globals()[sys.argv[1]]()

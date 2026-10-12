#!/usr/bin/env python3
"""Measure one WDSat traversal against Q1509's eight restarted N83 pairs."""
import gzip
import hashlib
import json
import os
import re
import resource
import signal
import subprocess
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
Q1488 = PARENT / "q20261012_n83_first_pair_restart"
Q1508 = PARENT / "q20261012_n83_blocked_pair_handoff"
Q1509 = PARENT / "q20261012_n83_pair_depth_sweep"
PAIR = re.compile(rb"^Q1517_PAIR (\d+) (\d+) (\d+) (\d+) ([01]{166})$", re.M)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def save(path, data):
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def cpu_limit(soft, hard):
    def apply():
        resource.setrlimit(resource.RLIMIT_CPU, (soft, hard))
    return apply


def baseline_bits(label):
    out = []
    for number in range(8):
        parent = Q1508 if number < 2 else Q1509
        row = read(parent / "runs" / f"{label}_round{number}" / "receipt.json")
        assert row["sat"]["status"] == "FIRST_PAIR_TERMINATED"
        out.append(row["sat"]["first_pair_bits"])
    assert len(set(out)) == 8
    return out


def main():
    p = read(HERE / "protocol.json")
    frozen = read(Q1488 / "freeze.json")
    build = read(HERE / "build_receipt.json")
    binary = Path(build["binary_path"])
    assert sha(binary) == build["binary_sha256"]
    assert sha(Q1488 / "freeze.json") == p["q1488_freeze_sha256"]
    assert sha(Q1509 / "result.json") == p["q1509_result_sha256"]
    assert sha(Q1509 / "build_receipt.json") == p["q1509_build_receipt_sha256"]
    assert not (HERE / "result.json").exists()
    rows = []
    for label in ("selected", "holdout"):
        cell = frozen["inputs"][label]
        raw = gzip.decompress(Path(cell["derived_path"]).read_bytes())
        assert hashlib.sha256(raw).hexdigest() == cell["derived_raw_sha256"]
        folder = HERE / "runs" / label
        folder.mkdir(parents=True, exist_ok=False)
        system = folder / "system.xcnf"
        system.write_bytes(raw)
        (folder / "system.xcnf.gz").write_bytes(gzip.compress(raw, mtime=0))
        out, err = folder / "solver.stdout.txt", folder / "solver.stderr.txt"
        env = os.environ.copy()
        env.update(Q1469_ORDER_MODE=p["branch_order"], Q1472_PHASE_INDEX="0",
                   Q1473_SELECTOR_PHASE="0", Q1481_LEAF_MASK=str(p["phase"]))
        started, reason, usage = time.monotonic(), None, None
        with out.open("wb") as stdout, err.open("wb") as stderr:
            child = subprocess.Popen([str(binary), "-i", str(system)],
                                     stdout=stdout, stderr=stderr, env=env,
                                     preexec_fn=cpu_limit(
                                         p["cpu_soft_seconds_per_target"],
                                         p["cpu_hard_seconds_per_target"]))
            deadline = started + p["wall_seconds_per_target"]
            sent_at = None
            while True:
                pid, status, usage = os.wait4(child.pid, os.WNOHANG)
                if pid:
                    child.returncode = os.waitstatus_to_exitcode(status)
                    break
                now = time.monotonic()
                if sent_at is None and now >= deadline:
                    reason = "WALL_CAP"
                    child.terminate()
                    sent_at = now
                elif sent_at is not None and now - sent_at > 5:
                    child.kill()
                time.sleep(0.05)
        system.unlink()
        markers = [(int(a), int(b), int(c), int(d), e.decode())
                   for a, b, c, d, e in PAIR.findall(err.read_bytes())]
        status = ("EIGHT_PAIRS_TERMINATED" if child.returncode == 47 and
                  len(markers) == 8 else
                  "WALL_CAP_SEARCH_STARTED" if reason == "WALL_CAP" and
                  b"Q1458_SEARCH_START" in err.read_bytes() else
                  "CPU_CAP_SEARCH_STARTED" if child.returncode in
                  (-signal.SIGXCPU, -signal.SIGKILL) else
                  "BRANCH_CAP_SEARCH_STARTED" if child.returncode == 42 else
                  "PROCESS_FAILURE")
        row = {"input": label, "workload_id": cell["workload_id"],
               "status": status, "return_code": child.returncode,
               "termination_reason": reason,
               "first_pairs": [{"index": a, "branch": b, "cnf_calls": c,
                                "xor_calls": d, "bits": e} for a, b, c, d, e in markers],
               "distinct_pairs": len(set(x[4] for x in markers)),
               "sequence_equal_q1509": [x[4] for x in markers] == baseline_bits(label),
               "q1509_restarted_calls": sum(
                   read((Q1508 if i < 2 else Q1509) / "runs" /
                        f"{label}_round{i}" / "receipt.json")["sat"]
                   ["first_pair_combined_calls"] for i in range(8)),
               "search_started": b"Q1458_SEARCH_START" in err.read_bytes(),
               "order_marker_ok": f"Q1469_ORDER {p['branch_order']} 334".encode()
                   in err.read_bytes(),
               "wall_seconds_exploratory": time.monotonic() - started,
               "child_user_cpu_seconds": usage.ru_utime,
               "child_system_cpu_seconds": usage.ru_stime,
               "child_peak_rss_bytes_darwin": usage.ru_maxrss,
               "system_sha256": hashlib.sha256(raw).hexdigest(),
               "stdout_sha256": sha(out), "stderr_sha256": sha(err)}
        save(folder / "receipt.json", row)
        rows.append(row)
        save(HERE / "result.partial.json", {"proposal_id": "Q1517", "rows": rows})
        print(label, status, len(markers), markers[-1][2] + markers[-1][3]
              if markers else None, flush=True)
    save(HERE / "result.json", {"proposal_id": "Q1517", "candidate_id": None,
                                "run_id": None, "curve_id": p["curve_id"],
                                "isogeny": "none", "point_decomposition_stage_code": "PDP4sat",
                                "protocol_sha256": sha(HERE / "protocol.json"),
                                "run_source_sha256": sha(Path(__file__)),
                                "rows": rows, "complete_n131_solve_work_log2": None})


if __name__ == "__main__":
    main()

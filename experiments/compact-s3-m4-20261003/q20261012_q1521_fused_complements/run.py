#!/usr/bin/env python3
"""Frozen control and two ordinary four-complement fused scans."""
import hashlib
import json
import os
import resource
import signal
import subprocess
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
BASE = PARENT / "bases/n83_weight5_full_point_orbits.bin"
Q1512 = PARENT / "q20261012_n83_raw_x_prefilter"
Q1520 = PARENT / "q20261012_q1520_phase3_scan_completion"
BINARY = Path("/Volumes/SSD990/llm/tmp/q1521-native-fused")


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, obj):
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")


def cpu_limit(soft, hard):
    def apply():
        resource.setrlimit(resource.RLIMIT_CPU, (soft, hard))
    return apply


def run_cell(p, label):
    pair_limit = p["control_pair_limit"] if label == "control" else p["full_pair_limit"]
    batch = 1 if label == "control" else p["batch_pairs"]
    xy = HERE / ("control_xy.txt" if label == "control" else f"{label}_xy.txt")
    command = [str(BINARY), str(BASE), str(xy), str(pair_limit), str(batch),
               str(p["bloom_log2_bits"]), str(p["bloom_hashes"])]
    folder = HERE / "runs" / label
    folder.mkdir(parents=True, exist_ok=False)
    out, err = folder / "stdout.txt", folder / "stderr.txt"
    start = time.monotonic()
    reason = None
    soft = 15 if label == "control" else p["cpu_soft_seconds_fused"]
    hard = 17 if label == "control" else p["cpu_hard_seconds_fused"]
    deadline = start + (180 if label == "control" else p["wall_seconds_fused"])
    with out.open("wb") as stdout, err.open("wb") as stderr:
        child = subprocess.Popen(command, stdout=stdout, stderr=stderr,
                                 preexec_fn=cpu_limit(soft, hard))
        terminated = None
        while True:
            pid, status, usage = os.wait4(child.pid, os.WNOHANG)
            if pid:
                child.returncode = os.waitstatus_to_exitcode(status)
                break
            now = time.monotonic()
            if terminated is None and now >= deadline:
                reason = "WALL_CAP"
                child.terminate()
                terminated = now
            elif terminated is not None and now - terminated > 5:
                child.kill()
            time.sleep(0.05)
    lines = out.read_text(errors="replace").splitlines()
    native = [json.loads(line) for line in lines if line.startswith("{")]
    hits = [line for line in lines if line.startswith("hit ")]
    state = ("COMPLETE" if child.returncode == 0 and len(native) == 4 else
             "WALL_CAP" if reason else
             "CPU_CAP" if child.returncode in (-signal.SIGXCPU, -signal.SIGKILL) else
             "PROCESS_FAILURE")
    if state == "COMPLETE":
        assert [x["complement_index"] for x in native] == list(range(4))
        assert all(x["scanned"] == 2 * pair_limit for x in native)
        assert all(x["actual_B"] == p["factor_base_actual_B"] for x in native)
    row = {"label": label, "status": state, "return_code": child.returncode,
           "termination_reason": reason, "command": command,
           "native": native, "hit_lines": hits,
           "wall_seconds_exploratory": time.monotonic() - start,
           "child_user_cpu_seconds": usage.ru_utime,
           "child_system_cpu_seconds": usage.ru_stime,
           "child_peak_rss_bytes_darwin": usage.ru_maxrss,
           "stdout_sha256": sha(out), "stderr_sha256": sha(err)}
    save(folder / "receipt.json", row)
    return row


def main():
    p = read(HERE / "protocol.json")
    assert not (HERE / "result.json").exists()
    assert sha(BASE) == p["factor_base_point_file_sha256"]
    assert sha(Q1512 / "native_prefilter.cpp") == p["parent_native_source_sha256"]
    assert sha(Q1512 / "result.json") == p["q1512_result_sha256"]
    assert sha(Q1520 / "result.json") == p["q1520_result_sha256"]
    assert sha(HERE / "native_fused.cpp") == p["native_fused_source_sha256"]
    assert sha(BINARY) == p["native_fused_binary_sha256"]
    assert sha(HERE / "control_xy.txt") == p["control_xy_sha256"]
    for label in ("selected", "holdout"):
        assert sha(HERE / f"{label}_xy.txt") == p["inputs"][label]["xy_sha256"]
    partial = HERE / "result.partial.json"
    rows = read(partial)["rows"] if partial.exists() else []
    assert [r["label"] for r in rows] == p["panel_order"][:len(rows)]
    for label in p["panel_order"][len(rows):]:
        row = run_cell(p, label.replace("_fused", ""))
        rows.append(row)
        save(partial, {"proposal_id": "Q1521", "rows": rows})
        print(label, row["status"], [x["hits"] for x in row["native"]], flush=True)
    save(HERE / "result.json", {
        "proposal_id": "Q1521", "candidate_id": None, "run_id": None,
        "curve_id": p["curve_id"], "isogeny": "none",
        "point_decomposition_stage_code": "PDP4hybrid",
        "protocol_sha256": sha(HERE / "protocol.json"),
        "source_sha256": sha(Path(__file__)), "rows": rows,
        "complete_n131_solve_work_log2": None})


if __name__ == "__main__":
    main()

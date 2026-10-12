#!/usr/bin/env python3
"""Run the frozen Q1473 warm-table panel and preserve every native row."""

from __future__ import annotations

import hashlib
import json
import resource
import subprocess
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
ROOT = HERE.parents[2]
PROTOCOL = HERE / "protocol.json"
OUTPUT = HERE / "runs/primary"


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    protocol = json.loads(PROTOCOL.read_text())
    panel = json.loads((HERE / "panel.json").read_text())
    assert protocol["proposal_id"] == "Q1473"
    assert protocol["candidate_id"] is None
    assert protocol["isogeny"] == "none"
    assert protocol["panel_workload_id"] == panel["panel_workload_id"]
    for relative, digest in protocol["source_sha256"].items():
        assert sha(ROOT / relative) == digest, relative
    assert sha(HERE / "batch_oracle") == protocol["binary_sha256"]
    assert sha(HERE / "compile_receipt.json") == protocol[
        "compile_receipt_sha256"]
    assert sha(HERE / "sage_runtime_info.json") == protocol[
        "runtime_info_sha256"]
    assert not OUTPUT.exists(), "refuse to overwrite run"
    OUTPUT.mkdir(parents=True)
    command = [str(HERE / "batch_oracle"),
               str(PARENT / "q1420_root_theory/n53_field.txt"),
               str(PARENT / "q1468_n53_pair_oracle/inputs/base_points.txt"),
               str(HERE / "targets.txt"),
               str(protocol["native_wall_cap_seconds_per_phase"]),
               str(protocol["target_count"])]
    start = time.perf_counter_ns()
    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    process = subprocess.Popen(command, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, text=True,
                               bufsize=1)
    timed_out = False

    def terminate() -> None:
        nonlocal timed_out
        if process.poll() is None:
            timed_out = True
            process.kill()

    timer = threading.Timer(protocol["external_safeguard_seconds"], terminate)
    timer.start()
    rows = []
    stdout_path, stderr_path = OUTPUT / "stdout.ndjson", OUTPUT / "stderr.txt"
    try:
        with stdout_path.open("w") as stream:
            assert process.stdout is not None
            for line in process.stdout:
                stream.write(line)
                stream.flush()
                row = json.loads(line)
                if not rows:
                    assert row["mode"] == "setup"
                else:
                    assert row["mode"] == "query"
                    assert row["index"] == len(rows) - 1
                rows.append(row)
                if len(rows) > 1 and ((len(rows) - 1) % 16 == 0 or
                                      len(rows) - 1 == protocol["target_count"]):
                    found = sum(r.get("status") == "found" for r in rows[1:])
                    print(json.dumps({"completed": len(rows) - 1,
                                      "found": found}), flush=True)
        assert process.stderr is not None
        stderr_path.write_text(process.stderr.read())
        exit_code = process.wait()
    finally:
        timer.cancel()
        if process.poll() is None:
            process.kill()
            process.wait()
    end = time.perf_counter_ns()
    after = resource.getrusage(resource.RUSAGE_CHILDREN)
    counts = {status: sum(row.get("status") == status for row in rows[1:])
              for status in ("found", "absent", "censored")}
    receipt = {
        "proposal_id": "Q1473", "candidate_id": None, "run_id": None,
        "isogeny": "none", "point_decomposition_stage_code": "PDP4mitm",
        "curve_id": protocol["curve_id"],
        "factor_base_actual_B": protocol["factor_base_actual_B"],
        "folded_columns_K": protocol["folded_columns_K"],
        "factor_base_enumerated_set_sha256": protocol[
            "factor_base_enumerated_set_sha256"],
        "panel_workload_id": protocol["panel_workload_id"],
        "target_count": protocol["target_count"],
        "completed_queries": max(0, len(rows) - 1),
        "status_counts": counts,
        "setup_report": rows[0] if rows else None,
        "native_exit_code": exit_code,
        "external_timeout": timed_out,
        "complete": (not timed_out and exit_code == 0 and
                     len(rows) == protocol["target_count"] + 1),
        "process_wall_ns_exploratory": end - start,
        "child_user_cpu_seconds": after.ru_utime - before.ru_utime,
        "child_system_cpu_seconds": after.ru_stime - before.ru_stime,
        "peak_child_rss_global_raw": after.ru_maxrss,
        "peak_child_rss_units": "bytes on Darwin, KiB on Linux",
        "native_stdout_sha256": sha(stdout_path),
        "native_stderr_sha256": sha(stderr_path),
        "binary_sha256": sha(HERE / "batch_oracle"),
        "protocol_sha256": sha(PROTOCOL),
        "runner_source_sha256": sha(Path(__file__)),
        "runtime_info_sha256": sha(HERE / "sage_runtime_info.json"),
        "cpu_isolation_receipt": None,
        "controlled_wall_speedup": None,
        "complete_n131_log2_work": None,
        "challenge_run_admitted": False,
    }
    (OUTPUT / "receipt.json").write_text(json.dumps(
        receipt, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"complete": receipt["complete"],
                      "completed": receipt["completed_queries"],
                      "status_counts": counts}), flush=True)


if __name__ == "__main__":
    main()

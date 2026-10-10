#!/usr/bin/env python3
"""Bound and bind independent direct-mask/projected-point support replay."""
import hashlib
import json
import resource
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    protocol = json.loads((HERE / "audit_protocol.json").read_text())
    paths = {"audit": HERE / "audit.py", "audit_source": HERE / "verify_native.cpp",
             "audit_binary": HERE / "verify_native", "count_result": HERE / "result.json",
             "support_receipt": HERE / "support_receipt.json",
             "field_library": ROOT.parent / "koblitz-s5-invariant-20260924/lowpoly_w23_geometry.cpp",
             **{f"support_w{d}": HERE / f"support_w{d}.tsv" for d in range(15, 19)}}
    assert protocol["status"] == "FROZEN_BEFORE_INDEPENDENT_AUDIT"
    assert protocol["source_sha256"] == {name: sha(path) for name, path in paths.items()}
    assert not (HERE / "audit_result.json").exists()
    started = time.monotonic_ns()
    command = [str(paths["audit_binary"].resolve()), str(HERE.resolve())]
    try:
        process = subprocess.run(command, capture_output=True, text=True,
                                 timeout=protocol["wall_cap_seconds"], check=False)
        exit_code = process.returncode
        stdout, stderr = process.stdout, process.stderr
    except subprocess.TimeoutExpired as error:
        exit_code = None
        stdout = (error.stdout or b"").decode("utf-8", "replace")
        stderr = (error.stderr or b"").decode("utf-8", "replace")
    (HERE / "audit.stdout.txt").write_text(stdout)
    (HERE / "audit.stderr.txt").write_text(stderr)
    elapsed = time.monotonic_ns()-started
    peak_self = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    peak_child = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    if sys.platform != "darwin":
        peak_self *= 1024
        peak_child *= 1024
    peak = max(peak_self, peak_child)
    row = {"status": "PRODUCER_FAILURE", "exit_code": exit_code,
           "wall_ns": elapsed, "peak_rss_bytes": peak,
           "source_sha256": protocol["source_sha256"],
           "protocol_sha256": sha(HERE / "audit_protocol.json"),
           "stdout_sha256": sha(HERE / "audit.stdout.txt"),
           "stderr_sha256": sha(HERE / "audit.stderr.txt")}
    if exit_code is None or elapsed > protocol["wall_cap_seconds"]*10**9:
        row["status"] = "CENSORED_TIME"
    elif peak > protocol["rss_cap_bytes"]:
        row["status"] = "CENSORED_MEMORY"
    elif exit_code == 0:
        replay = json.loads((HERE / "native_audit_result.json").read_text())
        count = json.loads((HERE / "result.json").read_text())
        assert replay["status"] == "PASS_DIRECT_MASK_AND_PROJECTED_X_AUDIT"
        row["native_replay_sha256"] = sha(HERE / "native_audit_result.json")
        row["rationality_checks"] = replay["rationality_checks"]
        row["projected_base_rows"] = replay["widths"]
        row["status"] = "PASS_INDEPENDENT_PROJECTED_BASE_AUDIT" if all(
            a["actual_projected_factor_base_B"] == b["actual_factor_base_B"]
            for a, b in zip(replay["widths"], count["widths"])) else "PROJECTED_BASE_MISMATCH"
    (HERE / "audit_result.json").write_text(json.dumps(row, sort_keys=True,
                                                       indent=2) + "\n")
    print(json.dumps({"status": row["status"], "exit_code": exit_code,
                      "wall_ns": elapsed, "peak_rss_bytes": peak}))
    if row["status"] != "PASS_INDEPENDENT_PROJECTED_BASE_AUDIT":
        raise SystemExit(1)


if __name__ == "__main__":
    main()

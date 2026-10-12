#!/usr/bin/env python3
"""Run one frozen serial-root audit and preserve timeout/error rows."""

import argparse
import hashlib
import json
import resource
import subprocess
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
PROTOCOL = HERE / "serial_audit_protocol.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(name):
    protocol = json.loads(PROTOCOL.read_text())
    assert protocol["audit_binary_sha256"] == sha(HERE / "serial_audit")
    for leaf in ("serial_audit.cpp", "serial_audit_protocol.py",
                 "serial_audit_run.py"):
        assert protocol["source_sha256"][leaf] == sha(HERE / leaf)
    assert protocol["source_sha256"]["root_field.hpp"] == sha(
        PARENT / "q1420_root_theory/root_field.hpp")
    row = next(s for s in protocol["selections"] if s["case"] == name)
    receipt_path = HERE / "runs" / name / "receipt.json"
    assert row["receipt_sha256"] == sha(receipt_path)
    receipt = json.loads(receipt_path.read_text())
    snapshot = row["selected_snapshot"]
    assert snapshot == receipt["solver_report"][
        "joint_rejection_snapshots"][0]
    target_path = PARENT / "q1455_joint_tail/runs" / name / "targets.txt"
    assert row["targets_sha256"] == sha(target_path)
    assert row["selected_target_x_onb_hex"] == target_path.read_text(
        ).splitlines()[1 + snapshot["target_preimage_index"]]
    n = row["degree_n"]
    field_path = PARENT / f"q1420_root_theory/n{n}_field.txt"
    assert protocol["field_bridge_sha256"][str(n)] == sha(field_path)
    command = [str(HERE / "serial_audit"), str(field_path),
               str(row["normal_basis_weight_bound"]),
               row["selected_target_x_onb_hex"]]
    for fixed, ones in zip(snapshot["leaf_fixed_mask_onb_hex"],
                           snapshot["leaf_ones_onb_hex"]):
        command.extend((fixed, ones))
    output = HERE / "serial_audit_runs" / f"{name}.json"
    assert not output.exists(), "refuse overwrite"
    output.parent.mkdir(parents=True, exist_ok=True)
    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    start = time.perf_counter_ns()
    try:
        process = subprocess.run(command, capture_output=True, text=True,
                                 timeout=600)
        status = "complete" if process.returncode == 0 else "error"
        stdout, stderr = process.stdout, process.stderr
        exit_code = process.returncode
    except subprocess.TimeoutExpired as error:
        status = "timeout"
        stdout = (error.stdout or b"").decode(errors="replace")
        stderr = (error.stderr or b"").decode(errors="replace")
        exit_code = None
    after = resource.getrusage(resource.RUSAGE_CHILDREN)
    observed = json.loads(stdout) if status == "complete" else None
    if observed:
        assert observed["pair_candidates"] == snapshot[
            "pair_candidate_counts"]
    result = {
        "proposal_id": "Q1466", "candidate_id": None,
        "run_id": None, "isogeny": "none",
        "case": name, "degree_n": n, "curve_id": row["curve_id"],
        "workload_id": row["workload_id"],
        "status": status, "exit_code": exit_code,
        "report": observed, "stdout": stdout, "stderr": stderr,
        "wall_ns_exploratory": time.perf_counter_ns() - start,
        "child_user_cpu_seconds": after.ru_utime - before.ru_utime,
        "child_system_cpu_seconds": after.ru_stime - before.ru_stime,
        "peak_child_rss_raw": after.ru_maxrss,
        "peak_child_rss_units": "bytes on Darwin, KiB on Linux",
        "serial_audit_protocol_sha256": sha(PROTOCOL),
        "selected_solver_receipt_sha256": sha(receipt_path),
        "audit_binary_sha256": sha(HERE / "serial_audit"),
        "complete_n131_log2_work": None,
        "challenge_run_admitted": False,
    }
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"case": name, "status": status,
                      "x_only_chain_hits": (observed or {}).get(
                          "x_only_chain_hits"),
                      "wall_seconds_exploratory": result[
                          "wall_ns_exploratory"] / 1e9}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", choices=("n53_ordinary", "n83_ordinary"),
                        required=True)
    run(parser.parse_args().case)

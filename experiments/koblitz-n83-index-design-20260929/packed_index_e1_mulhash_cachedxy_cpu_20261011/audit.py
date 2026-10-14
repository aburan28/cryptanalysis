#!/usr/bin/env python3
"""Replay the frozen full partner-root audit for sparse26 one-multiply hash."""

import argparse
import hashlib
import json
from pathlib import Path
import resource
import subprocess
import time


HERE = Path(__file__).resolve().parent
INPUTS = HERE.parent / "adaptive_all_orientations_20261004" / "inputs"


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(binary):
    protocol = json.loads((HERE / "audit_protocol.json").read_text())
    assert digest(HERE / "audit.py") == protocol["runner_sha256"]
    for name, path in (
        ("source_sha256", HERE / "native_packed_index.rs"),
        ("binary_sha256", binary),
        ("stage_manifest_sha256", HERE / "stage_manifest.json"),
        ("bridge_sha256", INPUTS / "n83_onb_poly_bridge.json"),
        ("representatives_sha256", INPUTS / "n83_x_representatives.bin"),
    ):
        assert digest(path) == protocol[name], name
    raw_path = HERE / "audit_mulhash_cachedxy.json"
    receipt_path = HERE / "audit_record.json"
    if raw_path.exists() or receipt_path.exists():
        raise RuntimeError("audit receipt already exists")
    command = [str(binary), str(HERE / "stage_manifest.json"),
               str(INPUTS / "n83_onb_poly_bridge.json"),
               str(INPUTS / "n83_x_representatives.bin"),
               str(protocol["pair_state_cap"]),
               str(protocol["peak_rss_cap_mib"]),
               protocol["index_mode"], str(raw_path)]
    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    start = time.perf_counter_ns()
    try:
        completed = subprocess.run(command, capture_output=True, text=True, timeout=1800)
        code, stdout, stderr = completed.returncode, completed.stdout, completed.stderr
    except subprocess.TimeoutExpired as exc:
        code = None
        stdout = (exc.stdout or b"").decode(errors="replace")
        stderr = (exc.stderr or b"").decode(errors="replace")
    elapsed = time.perf_counter_ns() - start
    after = resource.getrusage(resource.RUSAGE_CHILDREN)
    (HERE / "audit.stdout.txt").write_text(stdout)
    (HERE / "audit.stderr.txt").write_text(stderr)
    receipt = {
        "kind": "n83_e1_mulhash_cachedxy_full_partner_audit_run",
        "workload_id": protocol["workload_id"],
        "command": command,
        "exit_code": code,
        "outer_elapsed_ns": elapsed,
        "child_user_cpu_ns": round((after.ru_utime - before.ru_utime) * 1e9),
        "child_system_cpu_ns": round((after.ru_stime - before.ru_stime) * 1e9),
        "audit_protocol_sha256": digest(HERE / "audit_protocol.json"),
        "raw_sha256": digest(raw_path) if raw_path.exists() else None,
        "status": "completed" if code == 0 else "timeout" if code is None else "failed",
    }
    if raw_path.exists():
        raw = json.loads(raw_path.read_text())
        receipt.update(native_status=raw["status"],
                       partner_audit_pairs=raw["partner_audit_pairs"],
                       partner_roots=raw["target_partner_roots"],
                       peak_rss_bytes=raw["peak_rss_bytes"])
        assert raw["native_source_sha256"] == protocol["source_sha256"]
        assert raw["workload_id"] == protocol["workload_id"]
        assert raw["index_mode"] == protocol["index_mode"]
    receipt_path.write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n")
    if code != 0:
        raise RuntimeError("audit producer failed; raw failure retained")
    assert receipt["partner_audit_pairs"] == protocol["expected_partner_audit_pairs"]
    assert receipt["partner_roots"] == protocol["expected_partner_roots"]
    print(json.dumps({key: receipt[key] for key in
                      ("status", "native_status", "partner_audit_pairs",
                       "partner_roots", "peak_rss_bytes")}, sort_keys=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True)
    run(parser.parse_args().binary.resolve(strict=True))

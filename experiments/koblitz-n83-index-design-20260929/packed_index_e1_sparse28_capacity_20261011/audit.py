#!/usr/bin/env python3
"""Check every sparse28 partner pair against S3 on the frozen 2M-state input."""

import argparse
import hashlib
import json
import resource
import subprocess
import time
from pathlib import Path


HERE = Path(__file__).resolve().parent
MODE = "packed_sparse28_compact16_cachedxy_audit"


def sha256(path):
    state = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            state.update(chunk)
    return state.hexdigest()


def save(path, value):
    Path(path).write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--inputs-root", type=Path, default=HERE.parent /
                        "adaptive_all_orientations_20261004" / "inputs")
    args = parser.parse_args()
    binary = args.binary.resolve(strict=True)
    inputs = args.inputs_root.resolve(strict=True)
    bridge = inputs / "n83_onb_poly_bridge.json"
    reps = inputs / "n83_x_representatives.bin"
    manifest = json.loads((HERE / "audit_stage_manifest.json").read_text())
    assert manifest["workload_id"] == "981ac530e67e"
    assert manifest["pair_state_cap"] == 2_000_000
    assert manifest["peak_rss_cap_mib"] == 1024
    protocol = {
        "kind": "n83_e1_sparse28_full_partner_audit_protocol",
        "proposal_id": "Q2026101132",
        "curve_id": manifest["curve_id"],
        "workload_id": manifest["workload_id"],
        "index_mode": MODE,
        "pair_state_cap": 2_000_000,
        "peak_rss_cap_mib": 1024,
        "expected_partner_audit_pairs": 4_000_000,
        "expected_partner_roots": 8_000_000,
        "source_sha256": sha256(HERE / "native_packed_index.rs"),
        "binary_sha256": sha256(binary),
        "runner_sha256": sha256(HERE / "audit.py"),
        "stage_manifest_sha256": sha256(HERE / "audit_stage_manifest.json"),
        "bridge_sha256": sha256(bridge),
        "representatives_sha256": sha256(reps),
    }
    assert protocol["source_sha256"] == json.loads((HERE / "protocol.json").read_text())["input_sha256"]["source"]
    assert protocol["binary_sha256"] == json.loads((HERE / "protocol.json").read_text())["input_sha256"]["binary"]
    if (HERE / "audit_protocol.json").exists():
        assert json.loads((HERE / "audit_protocol.json").read_text()) == protocol
    else:
        save(HERE / "audit_protocol.json", protocol)
    raw_path = HERE / "audit_sparse28.json"
    record_path = HERE / "audit.record.json"
    if raw_path.exists() or record_path.exists():
        raise RuntimeError("audit result already exists")
    command = [str(binary), str(HERE / "audit_stage_manifest.json"), str(bridge),
               str(reps), "2000000", "1024", MODE, str(raw_path)]
    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    start = time.perf_counter_ns()
    completed = subprocess.run(command, text=True, capture_output=True, timeout=900)
    elapsed = time.perf_counter_ns() - start
    after = resource.getrusage(resource.RUSAGE_CHILDREN)
    (HERE / "audit.stdout.txt").write_text(completed.stdout)
    (HERE / "audit.stderr.txt").write_text(completed.stderr)
    record = {"kind": "n83_e1_sparse28_full_partner_audit_run",
              "exit_code": completed.returncode, "outer_elapsed_ns": elapsed,
              "child_user_cpu_ns": round((after.ru_utime - before.ru_utime) * 1e9),
              "child_system_cpu_ns": round((after.ru_stime - before.ru_stime) * 1e9),
              "audit_protocol_sha256": sha256(HERE / "audit_protocol.json"),
              "raw_sha256": sha256(raw_path) if raw_path.exists() else None}
    save(record_path, record)
    if completed.returncode:
        raise RuntimeError("audit failed; raw failure retained")
    raw = json.loads(raw_path.read_text())
    assert raw["native_source_sha256"] == protocol["source_sha256"]
    assert raw["workload_id"] == protocol["workload_id"]
    assert raw["index_mode"] == MODE
    assert raw["partner_audit_pairs"] == protocol["expected_partner_audit_pairs"]
    assert raw["target_partner_roots"] == protocol["expected_partner_roots"]
    assert raw["peak_rss_bytes"] <= 1024 * 1024 * 1024
    print(json.dumps({"status": raw["status"], "pairs": raw["partner_audit_pairs"],
                      "roots": raw["target_partner_roots"]}))


if __name__ == "__main__":
    main()

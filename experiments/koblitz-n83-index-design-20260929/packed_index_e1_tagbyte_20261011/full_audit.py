#!/usr/bin/env python3
"""Audit exact full-capacity N83 sidecar output under a bounded local run."""

import argparse
import hashlib
import json
import resource
import subprocess
import time
from pathlib import Path

from benchmark_stage import PAIR_FIELDS, canonical, digest


HERE = Path(__file__).resolve().parent
BASE = HERE.parent / "packed_index_e1_sparse28_capacity_20261011"
INPUTS = HERE.parent / "adaptive_all_orientations_20261004" / "inputs"
MODE = "packed_sparse28_tagbyte_cachedxy"
TIMEOUT_SECONDS = 3600


def write_json(path, value):
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    binary = args.binary.resolve(strict=True)
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    stage = BASE / "stage_manifest.json"
    bridge = INPUTS / "n83_onb_poly_bridge.json"
    reps = INPUTS / "n83_x_representatives.bin"
    reference_path = BASE / "run_2_sparse28.json"
    parent = json.loads((BASE / "protocol.json").read_text())
    reference = json.loads(reference_path.read_text())
    manifest = json.loads(stage.read_text())
    if (manifest["target_count"] != 1 or
            manifest["pair_state_cap"] != 29_900_000 or
            manifest["peak_rss_cap_mib"] != 5500 or
            manifest["workload_id"] != "63dd0929cf33"):
        raise ValueError("unexpected full-capacity workload")
    for name, path in (("stage_manifest", stage), ("bridge", bridge),
                       ("representatives", reps)):
        if digest(path) != parent["input_sha256"][name]:
            raise ValueError("frozen input digest changed: " + name)
    protocol = {
        "kind": "n83_e1_tagbyte_full_capacity_local_audit_v1",
        "workload_id": manifest["workload_id"],
        "target_count": 1,
        "pair_state_cap": 29_900_000,
        "peak_rss_cap_mib": 5500,
        "timeout_seconds": TIMEOUT_SECONDS,
        "mode": MODE,
        "source_sha256": digest(HERE / "native_packed_index.rs"),
        "cargo_manifest_sha256": digest(HERE / "Cargo.toml"),
        "cargo_lock_sha256": digest(HERE / "Cargo.lock"),
        "runner_sha256": digest(HERE / "full_audit.py"),
        "binary_sha256": digest(binary),
        "stage_manifest_sha256": digest(stage),
        "bridge_sha256": digest(bridge),
        "representatives_sha256": digest(reps),
        "reference_sha256": digest(reference_path),
    }
    protocol_path = output / "protocol.json"
    if protocol_path.exists():
        if json.loads(protocol_path.read_text()) != protocol:
            raise ValueError("frozen audit protocol changed")
    else:
        write_json(protocol_path, protocol)
    raw_path = output / "raw.json"
    record_path = output / "record.json"
    if raw_path.exists() or record_path.exists():
        raise FileExistsError("full audit already has a result")
    command = [str(binary), str(stage), str(bridge), str(reps),
               "29900000", "5500", MODE, str(raw_path)]
    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    start = time.perf_counter_ns()
    try:
        completed = subprocess.run(command, capture_output=True, text=True,
                                   timeout=TIMEOUT_SECONDS)
        stdout = completed.stdout.encode()
        stderr = completed.stderr.encode()
        exit_code = completed.returncode
        state = "COMPLETED" if exit_code == 0 else "FAILED"
    except subprocess.TimeoutExpired as error:
        stdout = error.stdout or b""
        stderr = error.stderr or b""
        if isinstance(stdout, str):
            stdout = stdout.encode()
        if isinstance(stderr, str):
            stderr = stderr.encode()
        exit_code = None
        state = "TIMEOUT"
    elapsed = time.perf_counter_ns() - start
    after = resource.getrusage(resource.RUSAGE_CHILDREN)
    (output / "stdout.txt").write_bytes(stdout)
    (output / "stderr.txt").write_bytes(stderr)
    write_json(record_path, {
        "status": state,
        "exit_code": exit_code,
        "outer_elapsed_ns": elapsed,
        "child_user_cpu_ns": round((after.ru_utime - before.ru_utime) * 1e9),
        "child_system_cpu_ns": round((after.ru_stime - before.ru_stime) * 1e9),
        "protocol_sha256": digest(protocol_path),
        "raw_sha256": digest(raw_path) if raw_path.exists() else None,
    })
    if state != "COMPLETED":
        raise RuntimeError("full-capacity audit ended with " + state)
    result = json.loads(raw_path.read_text())
    differences = [name for name in PAIR_FIELDS
                   if result.get(name) != reference.get(name)]
    if differences:
        raise ValueError("full-capacity parity differs: " + ", ".join(differences))
    if (result["native_source_sha256"] != protocol["source_sha256"] or
            result["cargo_manifest_sha256"] != protocol["cargo_manifest_sha256"] or
            result["index_mode"] != MODE or
            result["peak_rss_bytes"] > 5500 * (1 << 20)):
        raise ValueError("source, mode, or memory receipt differs")
    timing = result["timing_ns"]
    phase_ns = sum(int(timing[name]) for name in
                   ("target_query_preparation", "target_partner_generation",
                    "target_partner_check"))
    if phase_ns > int(timing["target_pdp_and_native_check"]):
        raise ValueError("target-stage phase sum exceeds total")
    certificate = hashlib.sha256(canonical(
        {name: result[name] for name in PAIR_FIELDS})).hexdigest()
    summary = {
        "status": "PASS",
        "protocol_sha256": digest(protocol_path),
        "raw_sha256": digest(raw_path),
        "pair_certificate": certificate,
        "reference_record_probes": reference["root_table_hash_probes"]["target_lookup"],
        "candidate_record_probes": result["root_table_hash_probes"]["target_lookup"],
        "candidate_tag_byte_allocated_bytes": result["root_table_tag_byte_allocated_bytes"],
        "candidate_table_allocated_bytes": result["root_table_allocated_bytes"],
        "candidate_peak_rss_bytes": result["peak_rss_bytes"],
        "candidate_target_process_cpu_ns": int(timing["target_process_cpu"]),
        "candidate_target_stage_wall_ns": int(timing["target_pdp_and_native_check"]),
        "candidate_phase_residual_ns": int(timing["target_pdp_and_native_check"]) - phase_ns,
        "interpretation": "local full-capacity correctness and probe audit",
    }
    write_json(output / "summary.json", summary)
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main()

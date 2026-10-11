#!/usr/bin/env python3
"""Screen the sparse28 singleton sidecar tag on one frozen N83 stage input."""

import argparse
import hashlib
import json
import resource
import subprocess
import time
from pathlib import Path


HERE = Path(__file__).resolve().parent
BASE = HERE.parent / "packed_index_e1_sparse28_capacity_20261011"
INPUTS = HERE.parent / "adaptive_all_orientations_20261004" / "inputs"
MODES = (
    "packed_sparse28_compact16_cachedxy",
    "packed_sparse28_tagbyte_cachedxy",
    "packed_sparse28_tagbyte_cachedxy",
    "packed_sparse28_compact16_cachedxy",
)
SAME_FIELDS = (
    "curve_id", "workload_id", "factor_base_enumerated_set_sha256",
    "input_representatives_sha256", "target_count", "index_pair_states_examined",
    "index_satisfiable_s3_states", "index_distinct_root_keys",
    "root_table_slots_or_records", "target_states_scanned",
    "target_states_prepared", "target_state_orientations_prepared",
    "target_state_orientations_tested", "target_partner_roots",
    "target_table_hits", "target_root_windows", "lookup_sample",
    "relation", "status", "native_s3_generator_target_control",
    "verified_single_target_dlp", "operation_counts",
)


def digest(path):
    hasher = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    binary = args.binary.resolve(strict=True)
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    manifest = BASE / "audit_stage_manifest.json"
    bridge = INPUTS / "n83_onb_poly_bridge.json"
    reps = INPUTS / "n83_x_representatives.bin"
    stage = json.loads(manifest.read_text())
    assert stage["target_count"] == 1
    assert stage["pair_state_cap"] == 2_000_000
    assert stage["peak_rss_cap_mib"] == 1024
    assert digest(reps) == stage["representatives_file_sha256"]
    protocol = {
        "kind": "n83_e1_tagbyte_exploratory_screen_v1",
        "curve_id": stage["curve_id"],
        "workload_id": stage["workload_id"],
        "target_count": 1,
        "pair_state_cap": 2_000_000,
        "peak_rss_cap_mib": 1024,
        "per_arm_timeout_seconds": 900,
        "order": list(MODES),
        "source_sha256": digest(HERE / "native_packed_index.rs"),
        "cargo_manifest_sha256": digest(HERE / "Cargo.toml"),
        "cargo_lock_sha256": digest(HERE / "Cargo.lock"),
        "runner_sha256": digest(HERE / "screen.py"),
        "binary_sha256": digest(binary),
        "stage_manifest_sha256": digest(manifest),
        "bridge_sha256": digest(bridge),
        "representatives_sha256": digest(reps),
    }
    protocol_path = output / "protocol.json"
    if protocol_path.exists():
        if json.loads(protocol_path.read_text()) != protocol:
            raise ValueError("frozen screen protocol or input digest changed")
    else:
        write_json(protocol_path, protocol)
    results = []
    for index, mode in enumerate(MODES, 1):
        raw_path = output / f"run_{index}.json"
        record_path = output / f"run_{index}.record.json"
        if raw_path.exists() or record_path.exists():
            raise FileExistsError(f"run {index} already exists")
        command = [str(binary), str(manifest), str(bridge), str(reps),
                   "2000000", "1024", mode, str(raw_path)]
        before = resource.getrusage(resource.RUSAGE_CHILDREN)
        start = time.perf_counter_ns()
        try:
            completed = subprocess.run(command, capture_output=True, text=True,
                                       timeout=900)
        except subprocess.TimeoutExpired as error:
            outer_ns = time.perf_counter_ns() - start
            after = resource.getrusage(resource.RUSAGE_CHILDREN)
            stdout = error.stdout or b""
            stderr = error.stderr or b""
            (output / f"run_{index}.stdout.txt").write_bytes(
                stdout if isinstance(stdout, bytes) else stdout.encode())
            (output / f"run_{index}.stderr.txt").write_bytes(
                stderr if isinstance(stderr, bytes) else stderr.encode())
            write_json(record_path, {
                "mode": mode,
                "status": "TIMEOUT",
                "timeout_seconds": 900,
                "outer_wall_ns": outer_ns,
                "child_user_cpu_ns": round((after.ru_utime - before.ru_utime) * 1e9),
                "child_system_cpu_ns": round((after.ru_stime - before.ru_stime) * 1e9),
                "protocol_sha256": digest(protocol_path),
                "raw_sha256": digest(raw_path) if raw_path.exists() else None,
            })
            raise RuntimeError(f"run {index} reached its 900-second cap") from error
        outer_ns = time.perf_counter_ns() - start
        after = resource.getrusage(resource.RUSAGE_CHILDREN)
        (output / f"run_{index}.stdout.txt").write_text(completed.stdout)
        (output / f"run_{index}.stderr.txt").write_text(completed.stderr)
        record = {
            "mode": mode,
            "exit_code": completed.returncode,
            "outer_wall_ns": outer_ns,
            "child_user_cpu_ns": round((after.ru_utime - before.ru_utime) * 1e9),
            "child_system_cpu_ns": round((after.ru_stime - before.ru_stime) * 1e9),
            "protocol_sha256": digest(protocol_path),
            "raw_sha256": digest(raw_path) if raw_path.exists() else None,
        }
        write_json(record_path, record)
        if completed.returncode:
            raise RuntimeError(f"run {index} failed with exit code {completed.returncode}")
        raw = json.loads(raw_path.read_text())
        assert raw["native_source_sha256"] == protocol["source_sha256"]
        assert raw["cargo_manifest_sha256"] == protocol["cargo_manifest_sha256"]
        assert raw["index_mode"] == mode
        assert raw["workload_id"] == protocol["workload_id"]
        assert raw["status"] == "state_cap_no_relation"
        assert raw["peak_rss_bytes"] <= 1024 * (1 << 20)
        assert raw["native_s3_generator_target_control"]["status"] == "PASS"
        results.append(raw)
    reference = {name: results[0][name] for name in SAME_FIELDS}
    for index, result in enumerate(results[1:], 2):
        mismatch = [name for name in SAME_FIELDS if result[name] != reference[name]]
        if mismatch:
            raise ValueError(f"run {index} differs in {mismatch}")
    summary = {
        "kind": "n83_e1_tagbyte_exploratory_screen_result_v1",
        "protocol_sha256": digest(protocol_path),
        "parity_fields": list(SAME_FIELDS),
        "runs": [
            {
                "mode": mode,
                "target_stage_wall_ns": int(raw["timing_ns"]["target_pdp_and_native_check"]),
                "target_stage_cpu_ns": int(raw["timing_ns"]["target_process_cpu"]),
                "root_table_allocated_bytes": raw["root_table_allocated_bytes"],
                "root_table_tag_byte_allocated_bytes": raw["root_table_tag_byte_allocated_bytes"],
                "target_record_probes": raw["root_table_hash_probes"]["target_lookup"],
                "target_singleton_tag_rejections": raw["target_singleton_tag_rejections"],
                "peak_rss_bytes": raw["peak_rss_bytes"],
            }
            for mode, raw in zip(MODES, results)
        ],
        "interpretation": "exploratory Mac stage screen; not a Tier 1 wall-time claim",
    }
    write_json(output / "summary.json", summary)
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main()

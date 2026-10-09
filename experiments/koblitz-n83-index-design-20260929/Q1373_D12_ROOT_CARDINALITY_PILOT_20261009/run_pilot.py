#!/usr/bin/env python3
"""Run the frozen sampled N83 d12 root-cardinality pilot."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
INPUTS = HERE / "inputs"
RUN = HERE / "runs/q1373_d12_root_cardinality_1m_sample_20261009"
PROTOCOL = HERE / "protocol.json"
MANIFEST = HERE / "manifest.json"
FREEZE = HERE / "freeze_receipt.json"
RUNTIME = RUN / "sage_runtime_info.json"
NATIVE_RESULT = RUN / "native_result.json"

INDEX_ROOTS_PER_STATE = 2
RECORD_BYTES = 16
BUCKETS = 256
SORT_TEMP = 64 * 2**20
RESERVE = 5 * 2**30 // 4


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def disk_preflight(protocol: dict) -> dict:
    ssd_free = shutil.disk_usage("/Volumes/SSD990").free
    system_free = shutil.disk_usage("/private/tmp").free
    states = int(protocol["total_quotient_pair_states"])
    maximum_records = states * INDEX_ROOTS_PER_STATE
    raw_payload = maximum_records * RECORD_BYTES
    best = None
    for ssd_buckets in range(BUCKETS + 1):
        ssd_payload = (raw_payload * ssd_buckets + BUCKETS - 1) // BUCKETS
        system_payload = raw_payload - (raw_payload * ssd_buckets // BUCKETS)
        ssd_remaining = ssd_free - ssd_payload - SORT_TEMP
        system_remaining = system_free - system_payload - SORT_TEMP
        margins = (ssd_remaining - RESERVE, system_remaining - RESERVE)
        floor = min(margins)
        if best is None or floor > best["minimum_reserve_margin_bytes"]:
            best = {
                "ssd_bucket_count": ssd_buckets,
                "system_bucket_count": BUCKETS - ssd_buckets,
                "ssd_payload_bytes": ssd_payload,
                "system_payload_bytes": system_payload,
                "ssd_remaining_after_one_sort_temp_bytes": ssd_remaining,
                "system_remaining_after_one_sort_temp_bytes": system_remaining,
                "ssd_reserve_margin_bytes": margins[0],
                "system_reserve_margin_bytes": margins[1],
                "minimum_reserve_margin_bytes": floor,
            }
    best.update({
        "ssd_free_at_preflight_bytes": ssd_free,
        "system_volume_free_at_preflight_bytes": system_free,
        "full_d12_pair_states": states,
        "assumed_roots_per_state": INDEX_ROOTS_PER_STATE,
        "packed_record_bytes": RECORD_BYTES,
        "projected_full_index_records": maximum_records,
        "projected_full_index_payload_bytes": raw_payload,
        "bucket_count": BUCKETS,
        "one_bucket_sort_temporary_cap_bytes_per_volume": SORT_TEMP,
        "required_free_reserve_bytes_per_volume": RESERVE,
        "passes_average_bucket_reserve_gate": best["minimum_reserve_margin_bytes"] >= 0,
        "bucket_hash_balance_measured": False,
        "full_index_build_started": False,
        "sample_run_storage_upper_bound_bytes": 256 * 2**20,
    })
    return best


def main() -> int:
    if RUN.exists() and any(path.name != "sage_runtime_info.json" for path in RUN.iterdir()):
        raise FileExistsError("Q1373 run directory is not empty")
    RUN.mkdir(parents=True, exist_ok=True)
    protocol = json.loads(PROTOCOL.read_text())
    manifest = json.loads(MANIFEST.read_text())
    freeze = json.loads(FREEZE.read_text())
    if freeze.get("status") != "PASS":
        raise ValueError("Q1373 frozen-input receipt did not pass")
    if manifest["stage_protocol_sha256"] != sha(PROTOCOL):
        raise ValueError("Q1373 manifest protocol digest mismatch")
    expected = protocol["inputs_sha256"]
    for name, filename in (
        ("native_source", "native_s3_root_canonical.rs"),
        ("native_binary", "native_s3_root_canonical"),
        ("native_build_receipt", "build_receipt.json"),
        ("basis_bridge", "n83_onb_poly_bridge.json"),
        ("q1104_d12_stage", "d12_stage_result.json"),
        ("q1104_d12_replay", "d12_independent_sage_replay.json"),
        ("q1104_d12_keys", "d12_canonical_orbit_keys.bin"),
        ("d12_polynomial_representatives", "d12_x_representatives_poly.bin"),
    ):
        if sha(INPUTS / filename) != expected[name]:
            raise ValueError(f"frozen input digest mismatch: {name}")
    runtime = json.loads(RUNTIME.read_text())
    if runtime.get("status") != "verified":
        raise ValueError("checked Sage runtime receipt is not verified")
    if NATIVE_RESULT.exists():
        raise FileExistsError("Q1373 native result already exists")

    preflight = disk_preflight(protocol)
    write_json(RUN / "full_d12_disk_preflight.json", preflight)
    if int(preflight["ssd_free_at_preflight_bytes"]) < int(preflight["sample_run_storage_upper_bound_bytes"]):
        raise RuntimeError("insufficient SSD free space for the bounded sample artifacts")

    binary = INPUTS / "native_s3_root_canonical"
    command = [
        str(binary), str(MANIFEST), str(INPUTS / "n83_onb_poly_bridge.json"),
        str(INPUTS / "d12_x_representatives_poly.bin"),
        str(manifest["pair_state_cap"]), str(manifest["peak_rss_cap_mib"]),
        str(NATIVE_RESULT),
    ]
    started = {
        "kind": "q1373_d12_root_cardinality_sample_started",
        "proposal_id": "Q1373",
        "candidate_id": None,
        "workload_id": protocol["workload_id"],
        "run_id": None,
        "command": command,
        "protocol_sha256": sha(PROTOCOL),
        "manifest_sha256": sha(MANIFEST),
        "freeze_receipt_sha256": sha(FREEZE),
        "runtime_info_sha256": sha(RUNTIME),
        "disk_preflight_sha256": sha(RUN / "full_d12_disk_preflight.json"),
        "started_epoch_ns": time.time_ns(),
        "sample_states": manifest["pair_state_cap"],
        "full_d12_index_build_started": False,
    }
    write_json(RUN / "started.json", started)

    begin = time.monotonic_ns()
    try:
        completed = subprocess.run(
            command, capture_output=True, text=True,
            timeout=int(protocol["native_wall_cap_seconds"]), check=False,
        )
        stdout, stderr, return_code = completed.stdout, completed.stderr, completed.returncode
        launch_status = "completed" if return_code == 0 else "process_error"
    except subprocess.TimeoutExpired as error:
        stdout = error.stdout.decode(errors="replace") if isinstance(error.stdout, bytes) else (error.stdout or "")
        stderr = error.stderr.decode(errors="replace") if isinstance(error.stderr, bytes) else (error.stderr or "")
        return_code, launch_status = None, "timeout"
    elapsed_ns = time.monotonic_ns() - begin
    (RUN / "stdout.txt").write_text(stdout)
    (RUN / "stderr.txt").write_text(stderr)
    native = json.loads(NATIVE_RESULT.read_text()) if NATIVE_RESULT.exists() else None

    roots_per_state = None
    descriptor_records = None
    duplicate_descriptors = None
    if native:
        examined = int(native["index_pair_states_examined"])
        satisfiable = int(native["index_satisfiable_s3_states"])
        unique_keys = int(native["index_distinct_root_keys"])
        descriptor_records = satisfiable * INDEX_ROOTS_PER_STATE
        duplicate_descriptors = descriptor_records - unique_keys
        roots_per_state = (
            descriptor_records / examined if examined else None
        )

    record = {
        "kind": "q1373_n83_d12_sampled_root_cardinality_run_record",
        "proposal_id": "Q1373",
        "candidate_id": None,
        "workload_id": protocol["workload_id"],
        "run_id": None,
        "curve_id": protocol["curve_id"],
        "status": launch_status,
        "native_status": native.get("status") if native else None,
        "sample_kind": protocol["sampling"],
        "sample_states": native.get("index_pair_states_examined") if native else None,
        "full_pair_states": protocol["total_quotient_pair_states"],
        "index_satisfiable_states": native.get("index_satisfiable_s3_states") if native else None,
        "projected_root_descriptor_records_for_sample": descriptor_records,
        "root_descriptor_records_per_sample_state": roots_per_state,
        "distinct_root_keys_in_native_single_value_table": native.get("index_distinct_root_keys") if native else None,
        "duplicate_root_descriptors_not_retained_by_native_table": duplicate_descriptors,
        "sample_unique_key_fraction": (
            native["index_distinct_root_keys"] / native["index_satisfiable_s3_states"]
            if native and native.get("index_satisfiable_s3_states") else None
        ),
        "target_sample_states_scanned": native.get("target_states_scanned") if native else None,
        "target_sample_table_hits": native.get("target_table_hits") if native else None,
        "sample_relation_returned": bool(native and native.get("relation")),
        "target_query_claim_boundary": "sampled state scan only; not a complete ordinary target query",
        "native_process_wall_ns": elapsed_ns,
        "native_timing_ns": native.get("timing_ns") if native else None,
        "peak_rss_bytes": native.get("peak_rss_bytes") if native else None,
        "full_d12_storage_preflight": preflight,
        "full_d12_index_build_started": False,
        "native_result_sha256": sha(NATIVE_RESULT) if NATIVE_RESULT.exists() else None,
        "protocol_sha256": sha(PROTOCOL),
        "manifest_sha256": sha(MANIFEST),
        "runtime_info_sha256": sha(RUNTIME),
        "claim_boundary": "bounded root-cardinality pilot and sampled target lookup on exact Q1104 d12 base",
    }
    write_json(RUN / "run_record.json", record)
    print(json.dumps({
        "status": launch_status,
        "native_status": record["native_status"],
        "sample_states": record["sample_states"],
        "index_satisfiable_states": record["index_satisfiable_states"],
        "projected_root_descriptor_records_for_sample": descriptor_records,
        "distinct_root_keys_in_native_single_value_table": record["distinct_root_keys_in_native_single_value_table"],
        "full_d12_passes_average_bucket_reserve_gate": preflight["passes_average_bucket_reserve_gate"],
        "elapsed_ns": elapsed_ns,
    }, sort_keys=True))
    return 0 if launch_status == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())

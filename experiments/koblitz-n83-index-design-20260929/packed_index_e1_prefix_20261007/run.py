#!/usr/bin/env python3
"""Freeze and run paired hash/packed N83 root-index stage measurements."""

from __future__ import annotations

import hashlib
import json
import math
import os
import platform
import statistics
import subprocess
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "adaptive_all_orientations_20261004"
INPUTS = PARENT / "inputs"
CRYPTO = Path("/Volumes/SSD990/crypto")
TARGET_DIR = Path("/tmp/n83-packed-index-e1-target")
MODES = ("hash", "packed", "packed", "hash", "hash", "packed")
PROPOSAL_ID = "Q2026100701"
STATE_CAP = 2_000_000
MEMORY_CAP_MIB = 1024


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def canonical(obj: object) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def save(path: Path, obj: object) -> None:
    path.write_text(json.dumps(obj, sort_keys=True, indent=2) + "\n")


def rust_source_tree_digest() -> str:
    h = hashlib.sha256()
    for path in sorted((CRYPTO / "src").rglob("*.rs")):
        h.update(str(path.relative_to(CRYPTO)).encode())
        h.update(b"\0")
        h.update(bytes.fromhex(digest(path)))
    return h.hexdigest()


def prepare() -> tuple[dict, dict]:
    parent_path = PARENT / "all83_ordinary_manifest.json"
    parent = json.loads(parent_path.read_text())
    reps = INPUTS / "n83_x_representatives.bin"
    bridge = INPUTS / "n83_onb_poly_bridge.json"
    assert digest(reps) == parent["representatives_file_sha256"]
    assert digest(bridge) == parent["bridge_sha256"]
    assert parent["curve_id"] == json.loads(bridge.read_text())["curve_id"]
    assert parent["candidate_id"] is None and parent["run_id"] is None
    assert parent["target_count"] == 1 and parent["field_degree"] == 83
    assert parent["pair_state_cap"] == STATE_CAP
    assert parent["peak_rss_cap_mib"] == MEMORY_CAP_MIB

    total = parent["representative_count_K"] ** 2 * 83
    origin = 0x7E5218AC20261003 % total
    step = 0x9E3779B97F4A7C15 % total or 1
    while math.gcd(step, total) != 1:
        step += 1
    workload = {
        "curve_id": parent["curve_id"],
        "subgroup_order": str(parent["subgroup_order"]),
        "target_count": 1,
        "target_poly_xy": parent["target_poly_xy"],
        "target_input_law": "one frozen public subgroup point",
        "factor_base_enumerated_set_sha256": parent["factor_base_enumerated_set_sha256"],
        "representatives_file_sha256": digest(reps),
        "index_state_law": {
            "kind": "coprime_stride_without_replacement",
            "total": total, "count": STATE_CAP,
            "origin": origin, "step": step,
        },
        "target_orientations_per_state": 1,
        "cache_state": "target-independent base and index ready at target clock start",
    }
    workload_id = hashlib.sha256(canonical(workload)).hexdigest()[:12]
    save(HERE / "workload.json", workload)

    source = HERE / "native_packed_index.rs"
    cargo_manifest = HERE / "Cargo.toml"
    cargo_lock = HERE / "Cargo.lock"
    protocol = {
        "kind": "paired_n83_packed_root_index_stage_protocol",
        "proposal_id": PROPOSAL_ID,
        "candidate_id": None,
        "run_id": None,
        "curve_id": parent["curve_id"],
        "workload_id": workload_id,
        "claim_boundary": "bounded S3 root-index and one-target query stage only; no complete relation-rank solve, target DLP, rho comparison, or IC speedup claim",
        "comparison_variable": "root lookup backend: open-addressed first-witness hash versus sorted 18-byte exact records with a 20-bit prefix directory",
        "run_order": list(MODES),
        "limits": {"pair_state_cap": STATE_CAP,
                   "peak_rss_cap_mib": MEMORY_CAP_MIB,
                   "target_orientations_per_state": 1,
                   "index_s3_window_size": 4096,
                   "target_s3_window_schedule": [4096]},
        "inputs_sha256": {
            "parent_manifest": digest(parent_path),
            "bridge": digest(bridge),
            "representatives": digest(reps),
            "native_source": digest(source),
            "runner": digest(HERE / "run.py"),
            "cargo_manifest": digest(cargo_manifest),
            "cargo_lock": digest(cargo_lock),
            "crypto_rust_source_tree": rust_source_tree_digest(),
        },
        "accounting": {
            "index_build": "target-independent S3 roots, insertion, packed sort, and prefix-directory construction",
            "target_query": "target-dependent S3 probes and relation checks",
            "correctness": "first-witness lookup samples, equal state and root counts, and equal target outcomes",
            "cpu_speedup_status": "exploratory without host-isolation receipt",
        },
    }
    save(HERE / "protocol.json", protocol)
    manifest = {
        "kind": "paired_n83_packed_root_index_stage_input",
        "stage_id": "n83_packed_index_e1_20261007",
        "stage_protocol_sha256": digest(HERE / "protocol.json"),
        "proposal_id": PROPOSAL_ID,
        "parent_factor_base_proposal_id": parent["parent_factor_base_proposal_id"],
        "candidate_id": None,
        "run_id": None,
        "curve_id": parent["curve_id"],
        "workload_id": workload_id,
        "field_degree": 83,
        "polynomial_low_terms": parent["polynomial_low_terms"],
        "subgroup_order": parent["subgroup_order"],
        "target_count": 1,
        "target_poly_xy": parent["target_poly_xy"],
        "representative_count_K": parent["representative_count_K"],
        "representatives_file_sha256": digest(reps),
        "factor_base_enumerated_set_sha256": parent["factor_base_enumerated_set_sha256"],
        "actual_usable_points_B": parent["actual_usable_points_B"],
        "pair_state_cap": STATE_CAP,
        "peak_rss_cap_mib": MEMORY_CAP_MIB,
        "orientations_per_state": 1,
        "index_s3_window_size": 4096,
        "target_s3_window_schedule": [4096],
    }
    save(HERE / "stage_manifest.json", manifest)
    return protocol, manifest


def build(protocol: dict) -> Path:
    env = os.environ.copy()
    env.update({
        "NATIVE_S3_SOURCE_SHA256": protocol["inputs_sha256"]["native_source"],
        "NATIVE_S3_BUILD_MANIFEST_SHA256": protocol["inputs_sha256"]["cargo_manifest"],
        "CARGO_TARGET_DIR": str(TARGET_DIR),
    })
    command = ["cargo", "build", "--release", "--locked", "--manifest-path",
               str(HERE / "Cargo.toml")]
    result = subprocess.run(command, env=env, text=True, capture_output=True)
    (HERE / "build.stdout.txt").write_text(result.stdout)
    (HERE / "build.stderr.txt").write_text(result.stderr)
    if result.returncode:
        raise RuntimeError(f"cargo build failed with exit code {result.returncode}")
    return TARGET_DIR / "release" / "native_packed_index"


def host_record(binary: Path, protocol: dict) -> dict:
    cpu = subprocess.run(["sysctl", "-n", "machdep.cpu.brand_string"],
                         text=True, capture_output=True)
    return {
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": cpu.stdout.strip() if cpu.returncode == 0 else platform.processor(),
        "python": sys.version.split()[0],
        "rustc": subprocess.check_output(["rustc", "--version"], text=True).strip(),
        "cargo": subprocess.check_output(["cargo", "--version"], text=True).strip(),
        "binary_sha256": digest(binary),
        "protocol_sha256": digest(HERE / "protocol.json"),
        "stage_manifest_sha256": digest(HERE / "stage_manifest.json"),
        "workload_sha256": digest(HERE / "workload.json"),
        "source_sha256": protocol["inputs_sha256"]["native_source"],
        "host_isolation_receipt": None,
    }


def run_one(binary: Path, mode: str, number: int, host: dict) -> dict:
    stem = f"run_{number}_{mode}"
    raw = HERE / f"{stem}.json"
    command = [str(binary), str(HERE / "stage_manifest.json"),
               str(INPUTS / "n83_onb_poly_bridge.json"),
               str(INPUTS / "n83_x_representatives.bin"),
               str(STATE_CAP), str(MEMORY_CAP_MIB), mode, str(raw)]
    try:
        completed = subprocess.run(command, text=True, capture_output=True,
                                   timeout=180)
        status = "completed" if completed.returncode == 0 else "failed"
        code = completed.returncode
        out, err = completed.stdout, completed.stderr
    except subprocess.TimeoutExpired as exc:
        status, code = "timeout", None
        out = exc.stdout.decode(errors="replace") if exc.stdout else ""
        err = exc.stderr.decode(errors="replace") if exc.stderr else ""
    (HERE / f"{stem}.stdout.txt").write_text(out)
    (HERE / f"{stem}.stderr.txt").write_text(err)
    result = {
        "kind": "n83_packed_index_stage_run_record",
        "proposal_id": PROPOSAL_ID,
        "candidate_id": None,
        "run_id": None,
        "mode": mode,
        "sequence_number": number,
        "execution_status": status,
        "exit_code": code,
        "raw_result_sha256": digest(raw) if raw.exists() else None,
        "host": host,
    }
    save(HERE / f"{stem}.record.json", result)
    return result


def summarize(records: list[dict], protocol: dict, manifest: dict) -> dict:
    raw = [json.loads((HERE / f"run_{i}_{mode}.json").read_text())
           for i, mode in enumerate(MODES, 1)]
    expected = raw[0]
    invariants = ["curve_id", "workload_id", "factor_base_enumerated_set_sha256",
                  "index_pair_states_examined", "index_satisfiable_s3_states",
                  "index_distinct_root_keys", "target_states_scanned",
                  "target_state_orientations_tested", "status", "relation",
                  "lookup_sample", "operation_counts",
                  "native_s3_generator_target_control", "target_table_hits",
                  "target_partner_roots", "verified_single_target_dlp"]
    mismatches = {field: [item[field] for item in raw]
                  for field in invariants if any(item[field] != expected[field]
                                                 for item in raw[1:])}
    rows = []
    for record, item in zip(records, raw):
        rows.append({
            "sequence_number": record["sequence_number"],
            "mode": record["mode"],
            "status": item["status"],
            "index_build_ns": int(item["timing_ns"]["index_build"]),
            "target_stage_ns": int(item["timing_ns"]["target_pdp_and_native_check"]),
            "rss_after_index_bytes": item["rss_after_index_bytes"],
            "peak_rss_bytes": item["peak_rss_bytes"],
            "table_allocated_bytes": item["root_table_allocated_bytes"],
            "table_slots_or_records": item["root_table_slots_or_records"],
            "target_lookup_comparisons_or_probes": item["root_table_hash_probes"]["target_lookup"],
            "verified_relation": item["relation"] is not None,
        })
    medians = {mode: {
        field: statistics.median(row[field] for row in rows if row["mode"] == mode)
        for field in ("index_build_ns", "target_stage_ns", "rss_after_index_bytes",
                      "peak_rss_bytes", "table_allocated_bytes")
    } for mode in ("hash", "packed")}
    ranges = {mode: {
        field: [min(row[field] for row in rows if row["mode"] == mode),
                max(row[field] for row in rows if row["mode"] == mode)]
        for field in ("index_build_ns", "target_stage_ns", "peak_rss_bytes")
    } for mode in ("hash", "packed")}
    return {
        "kind": "n83_packed_root_index_stage_comparison",
        "proposal_id": PROPOSAL_ID,
        "candidate_id": None, "run_id": None,
        "curve_id": manifest["curve_id"],
        "workload_id": manifest["workload_id"],
        "status": "validated_stage_comparison" if not mismatches else "mismatch",
        "invariant_mismatches": mismatches,
        "protocol_sha256": digest(HERE / "protocol.json"),
        "source_sha256": protocol["inputs_sha256"]["native_source"],
        "paired_rows": rows,
        "medians": medians,
        "ranges": ranges,
        "index_satisfiable_states": expected["index_satisfiable_s3_states"],
        "distinct_root_keys": expected["index_distinct_root_keys"],
        "actual_usable_points_B": expected["actual_usable_points_B"],
        "folded_columns_K": expected["folded_columns_K"],
        "complete_target_dlp": False,
        "rho_online_ms": None,
        "ic_online_ms": None,
        "online_speedup": None,
        "cpu_timing_claim": "exploratory stage costs only; no host isolation receipt",
    }


def main() -> None:
    protocol, manifest = prepare()
    binary = build(protocol)
    host = host_record(binary, protocol)
    save(HERE / "build_receipt.json", host)
    records = []
    for i, mode in enumerate(MODES, 1):
        print(f"run {i}/{len(MODES)} {mode}", flush=True)
        records.append(run_one(binary, mode, i, host))
    if any(record["execution_status"] != "completed" for record in records):
        raise RuntimeError("one or more stage executions failed; raw rows were preserved")
    summary = summarize(records, protocol, manifest)
    save(HERE / "summary.json", summary)
    if summary["invariant_mismatches"]:
        raise RuntimeError("hash and packed results differed; inspect summary.json")
    print(json.dumps({"status": summary["status"],
                      "medians": summary["medians"]}, sort_keys=True))


if __name__ == "__main__":
    main()

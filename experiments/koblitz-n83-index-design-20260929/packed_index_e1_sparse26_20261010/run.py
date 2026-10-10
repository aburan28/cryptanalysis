#!/usr/bin/env python3
"""Pair dense 25-bit and sparse 26-bit N83 root directories."""

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
CRYPTO_REPO = Path(os.environ.get("CRYPTO_REPO", "/Volumes/SSD990/crypto"))
CRYPTO_COMMIT = "904f0f844f3c1e69e8d22ae5e60ecd56e6648611"
CRYPTO = HERE / "crypto_source_snapshot"
CRYPTO_SOURCE_TREE_SHA256 = "f1f03c5a7c34b741c40a6b273c8211dd819e9e36a2db619d33e63938ae1c5268"
CRYPTO_RUST_SOURCE_SHA256 = "271f28243601d3e378c0ede7703722d611dec1d68c014fedec146c2a1f613314"
TARGET_DIR = Path(os.environ.get(
    "N83_E1_TARGET_DIR", "/tmp/n83-packed-index-e1-sparse26-target"))
MODES = ("packed_bucket25_fastcanon_tag", "packed_sparse26_fastcanon_tag",
         "packed_sparse26_fastcanon_tag", "packed_bucket25_fastcanon_tag",
         "packed_bucket25_fastcanon_tag", "packed_sparse26_fastcanon_tag")
PROPOSAL_ID = "Q2026101003"
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


def source_tree_digest() -> str:
    h = hashlib.sha256()
    for path in sorted(path for path in CRYPTO.rglob("*") if path.is_file()):
        h.update(str(path.relative_to(CRYPTO)).encode())
        h.update(b"\0")
        h.update(bytes.fromhex(digest(path)))
    return h.hexdigest()


def ensure_crypto_snapshot() -> None:
    if not (CRYPTO / "Cargo.toml").exists():
        CRYPTO.mkdir(exist_ok=True)
        TARGET_DIR.mkdir(parents=True, exist_ok=True)
        archive = TARGET_DIR / "crypto_source_snapshot.tar"
        try:
            subprocess.run(["git", "-C", str(CRYPTO_REPO), "archive",
                            f"--output={archive}", CRYPTO_COMMIT,
                            "Cargo.toml", "src"], check=True)
            subprocess.run(["tar", "-xf", str(archive), "-C", str(CRYPTO)],
                           check=True)
        finally:
            archive.unlink(missing_ok=True)
    if source_tree_digest() != CRYPTO_SOURCE_TREE_SHA256:
        raise RuntimeError("frozen crypto source tree differs from its receipt")
    if rust_source_tree_digest() != CRYPTO_RUST_SOURCE_SHA256:
        raise RuntimeError("frozen crypto Rust source differs from its receipt")


def rust_source_tree_digest() -> str:
    h = hashlib.sha256()
    for path in sorted((CRYPTO / "src").rglob("*.rs")):
        h.update(str(path.relative_to(CRYPTO)).encode())
        h.update(b"\0")
        h.update(bytes.fromhex(digest(path)))
    return h.hexdigest()


def prepare() -> tuple[dict, dict]:
    ensure_crypto_snapshot()
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
        "kind": "paired_n83_packed_root_sparse_directory_stage_protocol",
        "proposal_id": PROPOSAL_ID,
        "candidate_id": None,
        "run_id": None,
        "curve_id": parent["curve_id"],
        "workload_id": workload_id,
        "claim_boundary": "bounded S3 root-index and one-target query stage with paired exact dense 25-bit versus sparse 26-bit bucket lookup and phase measurements",
        "comparison_variable": "dense 25-bit counting-bucket directory versus sparse 26-bit bitmap-rank directory; both use zero-gap canonicalization, exact singleton tags, binary search, and the same 18-byte records",
        "run_order": list(MODES),
        "limits": {"pair_state_cap": STATE_CAP,
                   "peak_rss_cap_mib": MEMORY_CAP_MIB,
                   "target_orientations_per_state": 1,
                   "index_s3_window_size": 4096,
                   "target_s3_window_schedule": [4096]},
        "inputs_sha256": {
            "e1_bucket_summary": digest(HERE.parent / "packed_index_e1_bucket_20261008" / "summary.json"),
            "e1_linear_summary": digest(HERE.parent / "packed_index_e1_linear_20261009" / "summary.json"),
            "e1_canonical_summary": digest(HERE.parent / "packed_index_e1_canonical_20261009" / "summary.json"),
            "e1_bucket24_summary": digest(HERE.parent / "packed_index_e1_bucket24_20261010" / "summary.json"),
            "e1_bucket25_summary": digest(HERE.parent / "packed_index_e1_bucket25_20261010" / "summary.json"),
            "crypto_commit": CRYPTO_COMMIT,
            "crypto_source_tree": source_tree_digest(),
            "crypto_manifest": digest(CRYPTO / "Cargo.toml"),
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
            "index_build": "target-independent S3 roots, zero-gap canonical roots, bucket sorting, and singleton tags in the selected directory layout",
            "target_query": "target-dependent query preparation, batched S3 roots, canonicalized partner lookups, exact tag filtering, and relation checks",
            "correctness": "exact full-key comparisons after tag matches, first-witness lookup samples, equal state and root counts, and equal target outcomes",
            "cpu_speedup_status": "exploratory without host-isolation receipt",
        },
    }
    save(HERE / "protocol.json", protocol)
    manifest = {
        "kind": "paired_n83_packed_root_sparse_directory_stage_input",
        "stage_id": "n83_packed_root_sparse26_e1_20261010",
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
    TARGET_DIR.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.update({
        "NATIVE_S3_SOURCE_SHA256": protocol["inputs_sha256"]["native_source"],
        "NATIVE_S3_BUILD_MANIFEST_SHA256": protocol["inputs_sha256"]["cargo_manifest"],
        "CARGO_TARGET_DIR": str(TARGET_DIR),
        "TMPDIR": str(TARGET_DIR),
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
        "kind": "n83_packed_root_sparse_directory_stage_run_record",
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
    for phase in ("setup", "index_build", "target_pdp_and_native_check"):
        reference = {key: value for key, value in expected["operation_counts"][phase].items()
                     if key != "canonical_rotation_steps"}
        if any({key: value for key, value in item["operation_counts"][phase].items()
                if key != "canonical_rotation_steps"} != reference for item in raw[1:]):
            mismatches[f"{phase}_noncanonical_operations"] = [
                item["operation_counts"][phase] for item in raw]
    rows = []
    for record, item in zip(records, raw):
        rows.append({
            "sequence_number": record["sequence_number"],
            "mode": record["mode"],
            "status": item["status"],
            "index_build_ns": int(item["timing_ns"]["index_build"]),
            "target_stage_ns": int(item["timing_ns"]["target_pdp_and_native_check"]),
            "target_query_preparation_ns": int(item["timing_ns"]["target_query_preparation"]),
            "target_s3_batch_ns": int(item["timing_ns"]["target_s3_batch"]),
            "target_partner_check_ns": int(item["timing_ns"]["target_partner_check"]),
            "target_cycle_canonical_ns": int(item["timing_ns"]["target_cycle_canonical"]),
            "target_exact_lookup_ns": int(item["timing_ns"]["target_exact_lookup"]),
            "rss_after_index_bytes": item["rss_after_index_bytes"],
            "peak_rss_bytes": item["peak_rss_bytes"],
            "table_allocated_bytes": item["root_table_allocated_bytes"],
            "table_slots_or_records": item["root_table_slots_or_records"],
            "directory_entries": item["root_table_directory_entries"],
            "directory_offset_bytes": item["root_table_directory_offset_bytes"],
            "target_lookup_comparisons_or_probes": item["root_table_hash_probes"]["target_lookup"],
            "tagged_singleton_buckets": item["root_table_tagged_singleton_buckets"],
            "target_singleton_tag_rejections": item["target_singleton_tag_rejections"],
            "index_canonical_rotations": item["operation_counts"]["index_build"]["canonical_rotation_steps"],
            "target_canonical_rotations": item["operation_counts"]["target_pdp_and_native_check"]["canonical_rotation_steps"],
            "verified_relation": item["relation"] is not None,
        })
    medians = {mode: {
        field: statistics.median(row[field] for row in rows if row["mode"] == mode)
        for field in ("index_build_ns", "target_stage_ns", "target_query_preparation_ns",
                      "target_s3_batch_ns", "target_partner_check_ns",
                      "target_cycle_canonical_ns", "target_exact_lookup_ns",
                      "index_canonical_rotations", "target_canonical_rotations",
                      "tagged_singleton_buckets", "target_singleton_tag_rejections",
                      "rss_after_index_bytes", "peak_rss_bytes", "table_allocated_bytes",
                      "target_lookup_comparisons_or_probes")
    } for mode in ("packed_bucket25_fastcanon_tag", "packed_sparse26_fastcanon_tag")}
    ranges = {mode: {
        field: [min(row[field] for row in rows if row["mode"] == mode),
                max(row[field] for row in rows if row["mode"] == mode)]
        for field in ("index_build_ns", "target_stage_ns", "peak_rss_bytes")
    } for mode in ("packed_bucket25_fastcanon_tag", "packed_sparse26_fastcanon_tag")}
    return {
        "kind": "n83_packed_root_sparse_directory_stage_comparison",
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
        raise RuntimeError("packed bucket modes differed; inspect summary.json")
    print(json.dumps({"status": summary["status"],
                      "medians": summary["medians"]}, sort_keys=True))


if __name__ == "__main__":
    main()

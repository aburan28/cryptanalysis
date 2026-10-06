#!/usr/bin/env python3
"""Run one resumable-by-range n83 public-target quotient search chunk."""

import argparse
import hashlib
import json
import math
import os
import platform
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
CODEGEN = HERE.parents[1] / "ecc2k130" / "runner" / "codegen"
GENERATED = HERE.parents[1] / "ecc2k130" / "runner" / "generated" / "eccF83.h"
REFERENCE = HERE.parent / "ecc2k130-quotient-pair-probe-20260926" / "runs" / "n83_perf_prefix.json"
RHO = HERE.parent / "ecc2k130-quotient-pair-probe-20260926" / "runs" / "n83_public_target_rho_solved.json"
BASE_RECEIPT = HERE / "runs" / "n83_knownlog_orbit_base.json"
SCHEDULE = HERE / "runs" / "n53_n83_unique_schedule_perf.json"
SOURCE = HERE / "native_n83_bloom.cpp"
PAIRS_SOURCE = HERE / "native_n83_pairs.cpp"
BINARY = Path("/private/tmp/ecc2k83-native-bloom-chunk")
BATCH = 1024
sys.path.insert(0, str(CODEGEN))

import curves
import field
from bench_n83_full_base import CompactOrbitBase
from bench_n83_knownlog import load_keys_logs
from bench_native_n83_table import verify_hit
from orbit_key import OrbitKey
from run_n23 import frozen, sha


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--table-log2", type=int, default=33)
    parser.add_argument("--query-count-log2", type=int, default=38)
    parser.add_argument("--query-start", type=int, default=0)
    parser.add_argument("--table-start", type=int, default=0)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--bits-per-key", type=int, default=24)
    parser.add_argument("--hashes", type=int)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    M = 1 << args.table_log2
    Q = 1 << args.query_count_log2
    hashes = (args.hashes if args.hashes is not None else
              round(args.bits_per_key * math.log(2)))
    assert 1 <= args.workers <= 64
    assert 8 <= args.bits_per_key <= 64 and 1 <= hashes <= 32
    assert args.query_start >= 0
    assert args.table_start >= 0
    out = args.out or HERE / "runs" / (
        f"n83_bloom_chunk_M{args.table_log2}_Q{args.query_count_log2}_"
        f"tstart{args.table_start}_qstart{args.query_start}_"
        f"b{args.bits_per_key}_h{hashes}.json")
    started_path = out.with_suffix(".started.json")
    assert not out.exists(), f"refusing to overwrite completed chunk: {out}"

    reference = json.loads(REFERENCE.read_text())
    base_receipt = json.loads(BASE_RECEIPT.read_text())
    scheduled = json.loads(SCHEDULE.read_text())["runs"][1]
    rho = json.loads(RHO.read_text())
    identity = reference["curve_identity_record"]
    curve_id = "EC1N83Ckb1h" + hashlib.sha256(frozen(identity)).hexdigest()[:12]
    assert reference["curve_id"] == base_receipt["curve_id"] == scheduled["curve_id"] == rho["curve_id"] == curve_id
    record = base_receipt["factor_base"]
    assert record["actual_usable_points_B_before_folding"] == 4000102
    assert record["signed_frobenius_columns"] == 24097
    key_path = HERE / record["key_and_log_file"]
    assert sha(key_path) == record["key_and_log_file_sha256"]
    target = tuple(reference["workload"]["target"])
    assert list(target) == rho["public_target"]
    pair_domain = record["actual_usable_points_B_before_folding"] * (
        record["actual_usable_points_B_before_folding"] + 1) // 2
    cross_domain = scheduled["cross_orbit_zero_pair_class_domain"]
    assert args.table_start + M <= cross_domain
    assert Q > 0 and args.query_start + Q <= pair_domain
    onb = field.Onb(83)
    curve = curves.Curve(onb)
    generator = tuple(identity["curve"]["generator"])
    order = identity["curve"]["subgroup_order"]
    assert curve.onCurve(target) and curve.mul(generator, order) is None
    compiler_command = [
        "clang++", "-O3", "-std=c++17", "-march=armv8.2-a+crypto",
        str(SOURCE), "-o", str(BINARY),
    ]
    subprocess.run(compiler_command, check=True)
    command = [
        str(BINARY), str(key_path),
        format(onb.toCoords(target[0]), "x"),
        format(onb.toCoords(target[1]), "x"),
        str(M), str(Q), str(BATCH),
        str(scheduled["table_schedule"]["step"]),
        str(scheduled["table_schedule"]["offset"]),
        str(scheduled["query_schedule"]["step"]),
        str(scheduled["query_schedule"]["offset"]),
        str(args.bits_per_key), str(hashes),
        str(args.query_start), str(args.workers),
        str(args.table_start),
    ]
    started = {
        "kind": "n83_public_target_bloom_chunk_started",
        "curve_id": curve_id,
        "query_start": args.query_start,
        "query_count": Q,
        "table_start": args.table_start,
        "table_descriptors": M,
        "workers": args.workers,
        "bits_per_key": args.bits_per_key,
        "hashes": hashes,
        "started_at_utc": utc_now(),
        "wrapper_pid": os.getpid(),
        "compiled_binary_sha256": sha(BINARY),
        "native_source_sha256": sha(SOURCE),
        "base_file_sha256": sha(key_path),
        "schedule_receipt_sha256": sha(SCHEDULE),
        "destination": str(out),
    }
    with started_path.open("x") as handle:
        handle.write(json.dumps(started, indent=2) + "\n")
    print(json.dumps(started), flush=True)
    wall_started = time.perf_counter_ns()
    try:
        raw = subprocess.run(command, check=True, capture_output=True,
                             text=True)
    except BaseException as exc:
        failed = dict(started)
        failed.update({
            "kind": "n83_public_target_bloom_chunk_failed",
            "failed_at_utc": utc_now(),
            "terminal_status": type(exc).__name__,
            "returncode": (exc.returncode if isinstance(
                exc, subprocess.CalledProcessError) else 130),
            "stderr": (exc.stderr[-4000:] if isinstance(
                exc, subprocess.CalledProcessError) and exc.stderr else
                str(exc)),
            "native_phase_counts": None,
            "verified_public_target_quotient_table_dlp": False,
            "cumulative_work_known": False,
        })
        out.write_text(json.dumps(failed, indent=2) + "\n")
        started_path.unlink(missing_ok=True)
        raise
    elapsed_ns = time.perf_counter_ns() - wall_started
    native = json.loads(raw.stdout)
    assert native["actual_B"] == record["actual_usable_points_B_before_folding"]
    assert native["table_descriptors"] == M
    assert native["table_start"] == args.table_start
    assert native["query_start"] == args.query_start
    assert native["query_pairs"] == Q
    assert native["query_workers"] == args.workers
    assert native["bloom_positive_queries"] == (native[
        "false_positive_queries"] + native["exact_hit_queries"])

    verified = []
    verification_ns = 0
    if native["exact_hit_queries"]:
        keys, logs = load_keys_logs(key_path)
        orbit = OrbitKey(onb)
        base = CompactOrbitBase(orbit, keys)
        eigen = record["frobenius_eigenvalue_mod_r"]
        for hit in native["hits"]:
            begun = time.perf_counter_ns()
            certificate = verify_hit(
                curve, orbit, base, logs, target, generator, order,
                eigen, hit, scheduled)
            verification_ns += time.perf_counter_ns() - begun
            assert str(certificate["recovered_scalar"]) == rho[
                "recovered_scalar"]
            verified.append(certificate)
    batch_inversions = (2 * math.ceil(M / BATCH) +
                        2 * math.ceil(Q / BATCH))
    # Build and exact replay each take one table pass. Query pairs take
    # two batch additions. Each batch inverse is 8 mul + 82 sqr calls.
    field_calls_model = 26 * M + 27 * Q + 90 * batch_inversions
    report = {
        "kind": "n83_public_target_bloom_exact_replay_chunk",
        "scope": "one frozen target, one disjoint query range; include failed attempts in cumulative work; no full-domain claim from one chunk",
        "proposal_id": "Q1049", "candidate_id": None, "run_id": None,
        "curve_id": curve_id, "curve_identity_record": identity,
        "isogeny": "none", "public_target": list(target),
        "factor_base": record,
        "query_start": args.query_start,
        "query_count": Q,
        "table_start": args.table_start,
        "table_descriptors": M,
        "query_workers": args.workers,
        "bits_per_key": args.bits_per_key,
        "hashes": hashes,
        "native_result": native,
        "verified_public_target_relations": verified,
        "verified_public_target_quotient_table_dlp": bool(verified),
        "rho_scalar_agreement_if_hit": bool(verified) if native[
            "exact_hit_queries"] else None,
        "target_online_seconds": (native["query_seconds"] +
                                  native["exact_replay_seconds"] +
                                  verification_ns / 1e9),
        "target_independent_filter_build_seconds": (native[
            "allocation_seconds"] + native["build_seconds"]),
        "wrapper_subprocess_wall_seconds": elapsed_ns / 1e9,
        "native_field_add_mul_sqr_call_model": str(field_calls_model),
        "native_field_add_mul_sqr_call_model_log2": math.log2(
            field_calls_model),
        "field_call_model_boundary": "two table passes: 13 add/mul/sqr calls per regular pair, two query additions: 27 calls per regular pair, 90 calls per batch inversion; exceptional pairs ignored; excludes keying, Bloom hashing, memory, and verification",
        "started_at_utc": started["started_at_utc"],
        "finished_at_utc": utc_now(),
        "compiler_command": compiler_command,
        "compiled_binary_sha256": sha(BINARY),
        "native_source_sha256": sha(SOURCE),
        "native_pairs_source_sha256": sha(PAIRS_SOURCE),
        "generated_field_sha256": sha(GENERATED),
        "wrapper_source_sha256": sha(Path(__file__)),
        "base_receipt_sha256": sha(BASE_RECEIPT),
        "key_and_log_file_sha256": sha(key_path),
        "schedule_receipt_sha256": sha(SCHEDULE),
        "rho_reference_receipt_sha256": sha(RHO),
        "reference_sha256": sha(REFERENCE),
        "runtime": {"python": sys.version, "platform": platform.platform()},
    }
    out.write_text(json.dumps(report, indent=2) + "\n")
    started_path.unlink(missing_ok=True)
    print(json.dumps({
        "curve_id": curve_id,
        "query_start": args.query_start,
        "query_count": Q,
        "table_start": args.table_start,
        "table_descriptors": M,
        "workers": args.workers,
        "exact_hit_queries": native["exact_hit_queries"],
        "verified_dlp": bool(verified),
        "online_seconds": report["target_online_seconds"],
        "out": str(out),
    }), flush=True)


if __name__ == "__main__":
    main()

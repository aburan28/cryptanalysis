#!/usr/bin/env python3
"""Run one Q1062 full-filter, disk-spooled n=83 query rectangle.

Kept separate from the frozen Q1060 runner so in-flight Q1060 receipts
retain their exact wrapper source digest.
"""

import argparse
import hashlib
import json
import math
import os
import platform
import resource
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
BASE_RECEIPT = HERE / "runs" / "n83_knownlog_orbit_base_k48194.json"
SCHEDULE = HERE / "runs" / "n53_n83_unique_schedule_perf.json"
SPILL_SOURCE = HERE / "native_n83_orbit_query_spill.cpp"
CORE = HERE / "native_n83_bloom_core.hpp"
PAIRS = HERE / "native_n83_pairs.cpp"
SPILL_BINARY = Path("/private/tmp/ecc2k83-native-full-spill-k48194-chunk")
RUNTIME_INFO = HERE / "runs" / "n83_signed_x_runtime_info.json"
TABLE_BATCH = 1024
L = 166
K = 48194
sys.path.insert(0, str(CODEGEN))

import curves
import field
from bench_n83_full_base import CompactOrbitBase
from bench_n83_knownlog import load_keys_logs
from bench_native_n83_table import verify_hit
from orbit_key import OrbitKey
from pair_schedule import affine_rank, cross_orbit_pair
from run_n23 import frozen, sha
from verify_query_orbit_reuse import lift_within


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--table-log2", type=int, default=31)
    parser.add_argument("--query-reps-log2", type=int, default=30)
    parser.add_argument("--table-start", type=int, default=0)
    parser.add_argument("--query-start", type=int, default=0)
    parser.add_argument("--workers", type=int, default=14)
    parser.add_argument("--rep-batch", type=int, default=8)
    parser.add_argument("--bits-per-key", type=int, default=20)
    parser.add_argument("--hashes", type=int, default=10)
    parser.add_argument("--proposal-id", choices=("Q1062",),
                        default="Q1062")
    parser.add_argument("--fast-keyer", action="store_true")
    parser.add_argument("--spill-dir", type=Path)
    parser.add_argument("--runtime-info", type=Path, default=RUNTIME_INFO)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    M = 1 << args.table_log2
    R = 1 << args.query_reps_log2
    assert 0 <= args.table_start and 0 <= args.query_start
    assert 1 <= args.workers <= 64
    assert 1 <= args.rep_batch <= 48
    assert 8 <= args.bits_per_key <= 64
    assert 1 <= args.hashes <= 32
    assert args.bits_per_key == 20
    assert args.hashes == 10, "Q1062 requires ten Bloom hashes"
    assert args.fast_keyer, "Q1062 requires the frozen fast keyer"
    assert args.spill_dir is not None, "Q1062 requires SSD candidate spill"
    assert args.spill_dir.is_dir(), "candidate spill directory is missing"
    native_source = SPILL_SOURCE
    binary = SPILL_BINARY
    prefix = "n83_full_spill_"
    out = args.out or HERE / "runs" / (
        f"{prefix}k48194_chunk_M{args.table_log2}_R{args.query_reps_log2}_"
        f"tstart{args.table_start}_qstart{args.query_start}_"
        f"b{args.bits_per_key}_h{args.hashes}_rb{args.rep_batch}.json")
    started_path = out.with_suffix(".started.json")
    assert not out.exists(), f"refusing to overwrite terminal receipt: {out}"
    runtime_info = json.loads(args.runtime_info.read_text())
    assert runtime_info["status"] == "verified"

    reference = json.loads(REFERENCE.read_text())
    rho = json.loads(RHO.read_text())
    base_receipt = json.loads(BASE_RECEIPT.read_text())
    scheduled = json.loads(SCHEDULE.read_text())["runs"][1]
    identity = reference["curve_identity_record"]
    curve_id = "EC1N83Ckb1h" + hashlib.sha256(frozen(identity)).hexdigest()[:12]
    assert curve_id == reference["curve_id"] == rho[
        "curve_id"] == base_receipt["curve_id"] == scheduled["curve_id"]
    record = base_receipt["factor_base"]
    assert record["actual_usable_points_B_before_folding"] == K * L
    assert record["signed_frobenius_columns"] == K
    key_path = HERE / record["key_and_log_file"]
    assert sha(key_path) == record["key_and_log_file_sha256"]
    d_cross = math.comb(K, 2) * L
    assert args.table_start + M <= d_cross
    assert args.query_start + R <= d_cross
    table_step = scheduled["table_schedule"]["step"]
    table_offset = scheduled["table_schedule"]["offset"]
    query_step = table_step
    query_offset = (table_offset + 123456789) % d_cross
    assert math.gcd(query_step, d_cross) == 1
    target = tuple(reference["workload"]["target"])
    assert list(target) == rho["public_target"]
    onb = field.Onb(83)
    curve = curves.Curve(onb)
    generator = tuple(identity["curve"]["generator"])
    order = identity["curve"]["subgroup_order"]
    assert curve.onCurve(target) and curve.mul(generator, order) is None
    compiler_command = [
        "clang++", "-O3", "-std=c++17", "-march=armv8.2-a+crypto",
        f"-DECC2K83_ORBITS={K}",
    ]
    if args.fast_keyer:
        compiler_command.append("-DECC2K83_FAST_KEYER=1")
    compiler_command.extend([str(native_source), "-o", str(binary)])
    subprocess.run(compiler_command, check=True)
    command = [
        str(binary), str(key_path),
        format(onb.toCoords(target[0]), "x"),
        format(onb.toCoords(target[1]), "x"),
        str(M), str(R), str(TABLE_BATCH),
        str(table_step), str(table_offset),
        str(query_step), str(query_offset),
        str(args.bits_per_key), str(args.hashes),
        str(args.table_start), str(args.query_start),
        str(args.workers), str(args.rep_batch),
    ]
    started = {
        "kind": "n83_public_target_signed_x_query_k48194_chunk_started",
        "proposal_id": args.proposal_id, "candidate_id": None,
        "curve_id": curve_id,
        "curve_identity_record": identity,
        "isogeny": "none",
        "public_target": list(target),
        "factor_base_enumerated_set_sha256": record[
            "enumerated_set_sha256"],
        "actual_usable_points_B_before_folding": record[
            "actual_usable_points_B_before_folding"],
        "signed_frobenius_columns": record[
            "signed_frobenius_columns"],
        "table_start": args.table_start,
        "table_descriptors": M,
        "query_start": args.query_start,
        "query_representatives": R,
        "lifted_query_pairs": R * L,
        "query_workers": args.workers,
        "representative_batch": args.rep_batch,
        "bits_per_key": args.bits_per_key,
        "hashes": args.hashes,
        "fast_keyer_enabled": args.fast_keyer,
        "candidate_spill_enabled": args.spill_dir is not None,
        "candidate_spill_directory": (str(args.spill_dir) if args.spill_dir
                                      is not None else None),
        "started_at_utc": utc_now(),
        "wrapper_pid": os.getpid(),
        "compiled_binary_sha256": sha(binary),
        "native_source_sha256": sha(native_source),
        "bloom_core_sha256": sha(CORE),
        "native_pairs_sha256": sha(PAIRS),
        "key_file_sha256": sha(key_path),
        "schedule_receipt_sha256": sha(SCHEDULE),
        "sage_runtime_info_sha256": sha(args.runtime_info),
        "destination": str(out),
    }
    with started_path.open("x") as handle:
        handle.write(json.dumps(started, indent=2) + "\n")
    print(json.dumps(started), flush=True)
    before_cpu = resource.getrusage(resource.RUSAGE_CHILDREN)
    begun = time.perf_counter_ns()
    try:
        native_env = os.environ.copy()
        if args.spill_dir is not None:
            native_env["ECC2K83_CANDIDATE_TMPDIR"] = str(args.spill_dir)
        raw = subprocess.run(command, check=True, capture_output=True,
                             text=True, env=native_env)
    except BaseException as exc:
        after_cpu = resource.getrusage(resource.RUSAGE_CHILDREN)
        failed = dict(started)
        failed.update({
            "kind": "n83_public_target_signed_x_query_k48194_chunk_failed",
            "failed_at_utc": utc_now(),
            "terminal_status": type(exc).__name__,
            "returncode": (exc.returncode if isinstance(
                exc, subprocess.CalledProcessError) else 130),
            "stderr": (exc.stderr[-4000:] if isinstance(
                exc, subprocess.CalledProcessError) and exc.stderr else
                str(exc)),
            "native_phase_counts": None,
            "native_child_cpu_user_seconds": max(
                0.0, after_cpu.ru_utime - before_cpu.ru_utime),
            "native_child_cpu_system_seconds": max(
                0.0, after_cpu.ru_stime - before_cpu.ru_stime),
            "verified_public_target_quotient_table_dlp": False,
            "cumulative_work_known": False,
        })
        out.write_text(json.dumps(failed, indent=2) + "\n")
        started_path.unlink(missing_ok=True)
        raise
    elapsed = (time.perf_counter_ns() - begun) / 1e9
    after_cpu = resource.getrusage(resource.RUSAGE_CHILDREN)
    native_user = after_cpu.ru_utime - before_cpu.ru_utime
    native_system = after_cpu.ru_stime - before_cpu.ru_stime
    assert native_user >= 0 and native_system >= 0
    native = json.loads(raw.stdout)
    assert native["actual_B"] == record[
        "actual_usable_points_B_before_folding"]
    assert native["table_start"] == args.table_start
    assert native["table_descriptors"] == M
    assert native["query_start"] == args.query_start
    assert native["query_representatives"] == R
    assert native["lifted_query_pairs"] == R * L
    assert native["query_workers"] == args.workers
    assert native["representative_batch"] == args.rep_batch
    assert native["bloom_bits_per_key"] == args.bits_per_key
    assert native["bloom_hashes"] == args.hashes
    assert native["bloom_positive_queries"] == (
        native["false_positive_queries"] + native["exact_hit_queries"])
    assert native["candidate_store_mode"] == "unlinked_file"
    assert native["candidate_spill_bytes"] == (
        24 * native["bloom_positive_queries"])
    assert sha(native_source) == started["native_source_sha256"]
    assert sha(CORE) == started["bloom_core_sha256"]
    assert sha(PAIRS) == started["native_pairs_sha256"]

    verified = []
    verification_ns = 0
    if native["exact_hit_queries"]:
        keys, logs = load_keys_logs(key_path)
        orbit = OrbitKey(onb)
        base = CompactOrbitBase(orbit, keys)
        synthetic_schedule = dict(scheduled)
        synthetic_schedule["cross_orbit_zero_pair_class_domain"] = d_cross
        synthetic_schedule["unordered_query_pair_domain"] = (
            K * L * (K * L + 1) // 2)
        synthetic_schedule["query_schedule"] = {"step": 1,
                                                 "offset": 0}
        eigen = record["frobenius_eigenvalue_mod_r"]
        for hit in native["hits"]:
            rank = affine_rank(hit["query_representative_position"],
                               d_cross, query_step, query_offset)
            oi, oj, relative = cross_orbit_pair(rank, len(keys), L)
            k = hit["frobenius_shift"]
            negative = hit["negative_query_pair"]
            first = oi * L + lift_within(0, k, negative, 83)
            second = oj * L + lift_within(relative, k, negative, 83)
            unordered_rank = second * (second + 1) // 2 + first
            adapted = {
                "table_position": hit["table_position"],
                "query_position": unordered_rank,
                "x_key_hex": hit["x_key_hex"],
            }
            start_check = time.perf_counter_ns()
            certificate = verify_hit(
                curve, orbit, base, logs, target, generator, order,
                eigen, adapted, synthetic_schedule)
            verification_ns += time.perf_counter_ns() - start_check
            assert str(certificate["recovered_scalar"]) == rho[
                "recovered_scalar"]
            certificate["orbit_query_witness"] = hit
            verified.append(certificate)
    inversions = (2 * math.ceil(M / TABLE_BATCH) +
                  2 * math.ceil(R / args.rep_batch))
    field_calls = 26 * M + 13 * R + 13 * R * 83 + 90 * inversions
    report = {
        "kind": "n83_public_target_signed_x_query_k48194_exact_replay_chunk",
        "scope": "one frozen target and one table/query rectangle; exact hits independently verified; full campaign work requires all chunks",
        "proposal_id": args.proposal_id, "candidate_id": None,
        "run_id": None,
        "curve_id": curve_id,
        "curve_identity_record": identity,
        "isogeny": "none",
        "public_target": list(target),
        "factor_base": record,
        "table_start": args.table_start,
        "table_descriptors": M,
        "query_start": args.query_start,
        "query_representatives": R,
        "lifted_query_pairs": R * L,
        "query_workers": args.workers,
        "representative_batch": args.rep_batch,
        "bits_per_key": args.bits_per_key,
        "hashes": args.hashes,
        "fast_keyer_enabled": args.fast_keyer,
        "candidate_spill_enabled": args.spill_dir is not None,
        "candidate_spill_directory": (str(args.spill_dir) if args.spill_dir
                                      is not None else None),
        "table_schedule": scheduled["table_schedule"],
        "query_representative_schedule": {
            "domain": d_cross, "step": query_step,
            "offset": query_offset},
        "native_result": native,
        "verified_public_target_relations": verified,
        "verified_public_target_quotient_table_dlp": bool(verified),
        "rho_scalar_agreement_if_hit": bool(verified) if native[
            "exact_hit_queries"] else None,
        "target_online_seconds": (native["query_seconds"] +
                                  native["exact_replay_seconds"] +
                                  verification_ns / 1e9),
        "target_independent_filter_build_seconds": (
            native["allocation_seconds"] + native["build_seconds"]),
        "wrapper_subprocess_wall_seconds": elapsed,
        "native_child_cpu_user_seconds": native_user,
        "native_child_cpu_system_seconds": native_system,
        "native_child_cpu_total_seconds": native_user + native_system,
        "native_child_cpu_time_boundary": (
            "RUSAGE_CHILDREN delta immediately around the native search "
            "subprocess; includes target-independent filter build and "
            "target-dependent query and replay; excludes native compilation "
            "and Python scalar verification"),
        "native_field_add_mul_sqr_call_model": str(field_calls),
        "native_field_add_mul_sqr_call_model_log2": math.log2(
            field_calls),
        "field_call_model_boundary": "two full-point table passes and one full-point representative-query pass: 13 calls per pair; 83 paired-sign x-only complements per query representative: 6 adds, 5 muls, 2 sqrs per signed pair; 90 calls per batch inversion; exceptional pairs ignored; excludes keying, Bloom, memory, verification",
        "started_at_utc": started["started_at_utc"],
        "finished_at_utc": utc_now(),
        "compiler_command": compiler_command,
        "compiled_binary_sha256": sha(binary),
        "native_source_sha256": sha(native_source),
        "bloom_core_sha256": sha(CORE),
        "native_pairs_sha256": sha(PAIRS),
        "generated_field_sha256": sha(GENERATED),
        "wrapper_source_sha256": sha(Path(__file__)),
        "base_receipt_sha256": sha(BASE_RECEIPT),
        "key_file_sha256": sha(key_path),
        "schedule_receipt_sha256": sha(SCHEDULE),
        "sage_runtime_info_sha256": sha(args.runtime_info),
        "rho_reference_receipt_sha256": sha(RHO),
        "reference_sha256": sha(REFERENCE),
        "runtime": {"python": sys.version,
                    "platform": platform.platform()},
    }
    out.write_text(json.dumps(report, indent=2) + "\n")
    started_path.unlink(missing_ok=True)
    print(json.dumps({
        "curve_id": curve_id,
        "table_start": args.table_start,
        "query_start": args.query_start,
        "table_descriptors": M,
        "query_representatives": R,
        "exact_hit_queries": native["exact_hit_queries"],
        "verified_dlp": bool(verified),
        "online_seconds": report["target_online_seconds"],
        "out": str(out),
    }), flush=True)


if __name__ == "__main__":
    main()

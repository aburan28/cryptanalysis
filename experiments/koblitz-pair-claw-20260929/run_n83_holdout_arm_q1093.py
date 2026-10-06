#!/usr/bin/env python3
"""Run one Q1093 n=83 signed-x rectangle on a fresh holdout target."""

import argparse
import hashlib
import json
import math
import os
import platform
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
CODEGEN = HERE.parents[1] / "ecc2k130" / "runner" / "codegen"
GENERATED = HERE.parents[1] / "ecc2k130" / "runner" / "generated" / "eccF83.h"
REFERENCE = HERE.parent / "ecc2k130-quotient-pair-probe-20260926" / "runs" / "n83_perf_prefix.json"
HOLDOUT = HERE / "n83_holdout_target_20261001.json"
BASE_RECEIPT = HERE / "runs" / "n83_knownlog_orbit_base_k48194.json"
SCHEDULE = HERE / "runs" / "n53_n83_unique_schedule_perf.json"
SOURCE = HERE / "native_n83_orbit_query_spill_portable.cpp"
CORE = HERE / "native_n83_bloom_core_portable.hpp"
PAIRS = HERE / "native_n83_pairs_portable.cpp"
TABLE_BATCH = 1024
L = 166
K = 48194
sys.path.insert(0, str(CODEGEN))

import curves
import field
import bench_n83_zero_run_stage as zero_stage
from bench_n83_full_base import CompactOrbitBase
from bench_n83_knownlog import load_keys_logs
from bench_native_n83_table import verify_hit
from orbit_key import OrbitKey
from pair_schedule import affine_rank, cross_orbit_pair
from run_n23 import frozen, sha
from n83_identity_contract import validate_reference
from verify_query_orbit_reuse import lift_within

SCREEN = HERE / "n83_full_spill_screen.json"


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def compiler_flags(backend):
    arch = platform.machine().lower()
    if backend == "arm_pmull":
        assert arch in ("arm64", "aarch64"), "ARM PMULL requires an ARM host"
        return ["-march=armv8.2-a+crypto"]
    if backend == "x86_pclmul":
        assert arch in ("x86_64", "amd64"), "PCLMUL requires an x86 host"
        if sys.platform == "linux":
            flags = Path("/proc/cpuinfo").read_text().lower()
            assert "pclmulqdq" in flags or "pclmul" in flags, (
                "CPU has no PCLMUL flag; use --cpu-backend generic")
        return ["-mpclmul", "-msse2"]
    assert backend == "generic"
    return ["-mno-pclmul"] if arch in ("x86_64", "amd64") else []


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--table-log2", type=int, default=32)
    parser.add_argument("--query-reps-log2", type=int, default=31)
    parser.add_argument("--table-start", type=int, default=0)
    parser.add_argument("--query-start", type=int, default=0)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--rep-batch", type=int, default=8)
    parser.add_argument("--bits-per-key", type=int, default=20)
    parser.add_argument("--hashes", type=int, default=14)
    parser.add_argument("--cpu-backend", required=True,
                        choices=("arm_pmull", "x86_pclmul", "generic"))
    parser.add_argument("--cxx", default="c++")
    parser.add_argument("--spill-dir", type=Path, required=True)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--source-dir", type=Path, required=True,
                        help="empty directory retained with generated native sources")
    parser.add_argument("--frozen-plan", type=Path,
                        help="required for full-size rectangles")
    parser.add_argument("--runtime-info", type=Path,
                        help="optional checked Sage receipt if Sage was used")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    M = 1 << args.table_log2
    R = 1 << args.query_reps_log2
    assert 0 <= args.table_start and 0 <= args.query_start
    assert 1 <= args.workers <= 64
    assert 1 <= args.rep_batch <= 48
    assert 8 <= args.bits_per_key <= 64
    assert 1 <= args.hashes <= 32
    assert args.bits_per_key in (16, 20)
    assert args.hashes == 10
    assert args.spill_dir.is_dir(), "candidate spill directory is missing"
    assert args.source_dir.is_dir(), "generated-source directory is missing"
    assert not any((args.source_dir / name).exists() for name in
                   ("alt_pairs.cpp", "alt_core.hpp", "alt_main.cpp",
                    "eccF83.h")), "generated-source destination is not empty"
    assert shutil.disk_usage(args.spill_dir).free >= 1 << 30, (
        "candidate spill volume needs at least 1 GiB free")
    compiler_backend_flags = compiler_flags(args.cpu_backend)
    binary = args.binary.resolve()
    prefix = "n83_holdout_q1093_"
    out = args.out or HERE / "runs" / (
        f"{prefix}k48194_chunk_M{args.table_log2}_R{args.query_reps_log2}_"
        f"tstart{args.table_start}_qstart{args.query_start}_"
        f"b{args.bits_per_key}_h{args.hashes}_rb{args.rep_batch}.json")
    started_path = out.with_suffix(".started.json")
    assert not out.exists(), f"refusing to overwrite terminal receipt: {out}"
    if args.runtime_info:
        runtime_info = json.loads(args.runtime_info.read_text())
        assert runtime_info["status"] == "verified"

    reference = json.loads(REFERENCE.read_text())
    holdout = json.loads(HOLDOUT.read_text())
    base_receipt = json.loads(BASE_RECEIPT.read_text())
    scheduled = json.loads(SCHEDULE.read_text())["runs"][1]
    identity = reference["curve_identity_record"]
    curve_id = "EC1N83Ckb1h" + hashlib.sha256(frozen(identity)).hexdigest()[:12]
    assert curve_id == reference["curve_id"] == holdout[
        "curve_id"] == base_receipt["curve_id"] == scheduled["curve_id"]
    record = base_receipt["factor_base"]
    screen = json.loads(SCREEN.read_text())
    validate_reference(screen)
    assert screen["curve_id"] == curve_id
    assert screen["curve_identity_record"] == identity
    assert screen["factor_base"] == record
    assert screen["isogeny"] == "none"
    assert holdout["curve_identity_record"] == identity
    assert holdout["isogeny"] == "none"
    assert holdout["factor_base_enumerated_set_sha256"] == record[
        "enumerated_set_sha256"]
    assert holdout["actual_usable_points_B_before_folding"] == K * L
    assert holdout["signed_frobenius_columns"] == K
    assert holdout["fixture_scalar_retained"] is False
    workload_bytes = frozen(holdout["workload"])
    assert holdout["workload_id"] == hashlib.sha256(
        workload_bytes).hexdigest()[:12]
    assert holdout["workload_record_sha256"] == hashlib.sha256(
        workload_bytes).hexdigest()
    assert holdout["workload"]["targets"] == [holdout["public_target"]]
    assert holdout["public_target"] != screen["public_target"]
    assert record["actual_usable_points_B_before_folding"] == K * L
    assert record["signed_frobenius_columns"] == K
    key_path = HERE / record["key_and_log_file"]
    assert sha(key_path) == record["key_and_log_file_sha256"]
    d_cross = math.comb(K, 2) * L
    assert args.table_start + M <= d_cross
    assert args.query_start + R <= d_cross
    if M >= 1 << 31 or R >= 1 << 27:
        assert args.frozen_plan is not None, (
            "full-size holdout work requires a frozen Q1093 plan")
        plan = json.loads(args.frozen_plan.read_text())
        assert plan["proposal_id"] == "Q1093"
        assert plan["status"] == "ready_for_dispatch"
        assert plan["curve_id"] == curve_id
        assert plan["isogeny"] == "none"
        assert plan["candidate_id"].startswith(
            f"IC1N83Ckb1fb{K * L}PDP4qtableRCdirectLAnoneTDdirectISO0h")
        assert plan["run_id"] == (
            plan["candidate_id"] + "W" + holdout["workload_id"] + "R1")
        candidate_path = HERE / plan["candidate_manifest"]
        assert sha(candidate_path) == plan["candidate_manifest_sha256"]
        candidate = json.loads(candidate_path.read_text())
        assert candidate["candidate_id"] == plan["candidate_id"]
        assert candidate["implementation"]["wrapper_source_sha256"] == sha(
            Path(__file__))
        assert plan["factor_base_enumerated_set_sha256"] == record[
            "enumerated_set_sha256"]
        assert plan["actual_usable_points_B_before_folding"] == record[
            "actual_usable_points_B_before_folding"]
        assert plan["signed_frobenius_columns"] == K
        assert plan["public_target"] == holdout["public_target"]
        assert plan["workload_id"] == holdout["workload_id"]
        assert plan["holdout_target_sha256"] == sha(HOLDOUT)
        assert plan["table_descriptors"] == M
        assert plan["table_start"] == args.table_start
        assert plan["query_representatives"] == R
        assert args.query_start in plan["query_starts"]
        assert plan["cpu_backend"] == args.cpu_backend
        assert plan["workers"] == args.workers
        assert plan["representative_batch"] == args.rep_batch
        assert plan["bits_per_key"] == args.bits_per_key
        assert plan["hashes"] == args.hashes
        assert plan["runner_source_sha256"] == sha(Path(__file__))
        assert plan["source_generator_sha256"] == sha(
            HERE / "bench_n83_zero_run_stage.py")
        assert plan["portable_native_source_sha256"] == sha(SOURCE)
        assert plan["portable_core_source_sha256"] == sha(CORE)
        assert plan["portable_pairs_source_sha256"] == sha(PAIRS)
        assert plan["generated_field_sha256"] == sha(GENERATED)
        assert shutil.disk_usage(args.spill_dir).free >= plan[
            "minimum_spill_free_bytes"]
    else:
        assert args.frozen_plan is None
    candidate_id = plan["candidate_id"] if args.frozen_plan else None
    run_id = plan["run_id"] if args.frozen_plan else None
    table_step = scheduled["table_schedule"]["step"]
    table_offset = scheduled["table_schedule"]["offset"]
    query_step = table_step
    query_offset = (table_offset + 123456789) % d_cross
    assert math.gcd(query_step, d_cross) == 1
    target = tuple(holdout["public_target"])
    onb = field.Onb(83)
    curve = curves.Curve(onb)
    generator = tuple(identity["curve"]["generator"])
    order = identity["curve"]["subgroup_order"]
    assert curve.onCurve(target) and curve.mul(generator, order) is None
    assert all(sha(path) == digest for path, digest in zero_stage.FROZEN.items())
    generated_paths = zero_stage.generated_sources(args.source_dir)
    native_pairs, native_core, native_source = generated_paths
    generated_header = args.source_dir / "eccF83.h"
    assert not generated_header.exists()
    shutil.copyfile(GENERATED, generated_header)
    assert sha(generated_header) == sha(GENERATED)
    if args.frozen_plan:
        assert plan["zero_run_native_source_sha256"] == sha(native_source)
        assert plan["zero_run_core_source_sha256"] == sha(native_core)
        assert plan["zero_run_pairs_source_sha256"] == sha(native_pairs)
    compiler_command = [
        args.cxx, "-O3", "-std=c++17", *compiler_backend_flags,
        f"-DECC2K83_ORBITS={K}", "-DECC2K83_FAST_KEYER=1",
    ]
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
        "kind": "n83_holdout_signed_x_query_k48194_chunk_started",
        "proposal_id": "Q1093", "candidate_id": candidate_id,
        "run_id": run_id,
        "workload_id": holdout["workload_id"],
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
        "fast_keyer_enabled": True,
        "keyer_variant": "exact_longest_zero_run",
        "candidate_spill_enabled": True,
        "candidate_spill_directory": str(args.spill_dir),
        "cpu_backend": args.cpu_backend,
        "started_at_utc": utc_now(),
        "wrapper_pid": os.getpid(),
        "compiled_binary_sha256": sha(binary),
        "native_source_sha256": sha(native_source),
        "bloom_core_sha256": sha(native_core),
        "native_pairs_sha256": sha(native_pairs),
        "zero_run_source_generator_sha256": sha(
            HERE / "bench_n83_zero_run_stage.py"),
        "frozen_portable_source_sha256": {
            path.name: digest for path, digest in zero_stage.FROZEN.items()},
        "generated_field_sha256": sha(generated_header),
        "key_file_sha256": sha(key_path),
        "schedule_receipt_sha256": sha(SCHEDULE),
        "sage_runtime_info_sha256": (
            sha(args.runtime_info) if args.runtime_info else None),
        "destination": str(out),
    }
    with started_path.open("x") as handle:
        handle.write(json.dumps(started, indent=2) + "\n")
    print(json.dumps(started), flush=True)
    begun = time.perf_counter_ns()
    try:
        native_env = os.environ.copy()
        native_env["ECC2K83_CANDIDATE_TMPDIR"] = str(args.spill_dir)
        raw = subprocess.run(command, check=True, capture_output=True,
                             text=True, env=native_env)
    except BaseException as exc:
        failed = dict(started)
        failed.update({
            "kind": "n83_holdout_signed_x_query_k48194_chunk_failed",
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
    elapsed = (time.perf_counter_ns() - begun) / 1e9
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
    assert sha(native_core) == started["bloom_core_sha256"]
    assert sha(native_pairs) == started["native_pairs_sha256"]
    assert sha(generated_header) == started["generated_field_sha256"]
    assert sha(HERE / "bench_n83_zero_run_stage.py") == started[
        "zero_run_source_generator_sha256"]

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
            assert curve.mul(generator, int(certificate[
                "recovered_scalar"])) == target
            certificate["orbit_query_witness"] = hit
            verified.append(certificate)
    inversions = (2 * math.ceil(M / TABLE_BATCH) +
                  2 * math.ceil(R / args.rep_batch))
    field_calls = 26 * M + 13 * R + 13 * R * 83 + 90 * inversions
    report = {
        "kind": "n83_holdout_signed_x_query_k48194_exact_replay_chunk",
        "scope": "one frozen target and one table/query rectangle; exact hits independently verified; full campaign work requires all chunks",
        "proposal_id": "Q1093", "candidate_id": candidate_id,
        "run_id": run_id,
        "workload_id": holdout["workload_id"],
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
        "fast_keyer_enabled": True,
        "keyer_variant": "exact_longest_zero_run",
        "candidate_spill_enabled": True,
        "candidate_spill_directory": str(args.spill_dir),
        "cpu_backend": args.cpu_backend,
        "table_schedule": scheduled["table_schedule"],
        "query_representative_schedule": {
            "domain": d_cross, "step": query_step,
            "offset": query_offset},
        "native_result": native,
        "verified_public_target_relations": verified,
        "verified_public_target_quotient_table_dlp": bool(verified),
        "rho_scalar_agreement_if_hit": None,
        "target_online_seconds": (native["query_seconds"] +
                                  native["exact_replay_seconds"] +
                                  verification_ns / 1e9),
        "target_independent_filter_build_seconds": (
            native["allocation_seconds"] + native["build_seconds"]),
        "wrapper_subprocess_wall_seconds": elapsed,
        "native_field_add_mul_sqr_call_model": str(field_calls),
        "native_field_add_mul_sqr_call_model_log2": math.log2(
            field_calls),
        "field_call_model_boundary": "two full-point table passes and one full-point representative-query pass: 13 calls per pair; 83 paired-sign x-only complements per query representative: 6 adds, 5 muls, 2 sqrs per signed pair; 90 calls per batch inversion; exceptional pairs ignored; excludes keying, Bloom, memory, verification",
        "started_at_utc": started["started_at_utc"],
        "finished_at_utc": utc_now(),
        "compiler_command": compiler_command,
        "compiled_binary_sha256": sha(binary),
        "native_source_sha256": sha(native_source),
        "bloom_core_sha256": sha(native_core),
        "native_pairs_sha256": sha(native_pairs),
        "generated_field_sha256": sha(generated_header),
        "zero_run_source_generator_sha256": started[
            "zero_run_source_generator_sha256"],
        "frozen_portable_source_sha256": started[
            "frozen_portable_source_sha256"],
        "wrapper_source_sha256": sha(Path(__file__)),
        "base_receipt_sha256": sha(BASE_RECEIPT),
        "key_file_sha256": sha(key_path),
        "schedule_receipt_sha256": sha(SCHEDULE),
        "sage_runtime_info_sha256": (
            sha(args.runtime_info) if args.runtime_info else None),
        "holdout_target_sha256": sha(HOLDOUT),
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
    try:
        main()
    except BaseException as exc:
        if "--out" in sys.argv:
            output = Path(sys.argv[sys.argv.index("--out") + 1])
            marker = output.with_suffix(".started.json")
            if marker.exists() and not output.exists():
                failed = json.loads(marker.read_text())
                failed.update({
                    "kind": "n83_holdout_signed_x_query_k48194_chunk_failed",
                    "failed_at_utc": utc_now(),
                    "terminal_status": type(exc).__name__,
                    "stderr": str(exc)[-4000:],
                    "native_phase_counts": None,
                    "verified_public_target_quotient_table_dlp": False,
                    "cumulative_work_known": False,
                    "wrapper_source_sha256": sha(Path(__file__)),
                })
                output.write_text(json.dumps(failed, indent=2) + "\n")
                marker.unlink()
        raise

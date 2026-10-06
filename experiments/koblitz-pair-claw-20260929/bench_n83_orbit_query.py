#!/usr/bin/env python3
"""Measure n=83 signed-Frobenius query-orbit reuse and verify exact hits."""

import hashlib
import json
import math
import platform
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CODEGEN = HERE.parents[1] / "ecc2k130" / "runner" / "codegen"
REFERENCE = HERE.parent / "ecc2k130-quotient-pair-probe-20260926" / "runs" / "n83_perf_prefix.json"
RHO = HERE.parent / "ecc2k130-quotient-pair-probe-20260926" / "runs" / "n83_public_target_rho_solved.json"
BASE_RECEIPT = HERE / "runs" / "n83_knownlog_orbit_base.json"
SCHEDULE = HERE / "runs" / "n53_n83_unique_schedule_perf.json"
SOURCE = HERE / "native_n83_orbit_query.cpp"
CORE = HERE / "native_n83_bloom_core.hpp"
PAIRS = HERE / "native_n83_pairs.cpp"
DIRECT_SOURCE = HERE / "native_n83_bloom.cpp"
OUTPUT = HERE / "runs" / "n83_native_query_orbit_bounded.json"
BINARY = Path("/private/tmp/ecc2k83-native-orbit-query")
DIRECT_BINARY = Path("/private/tmp/ecc2k83-native-bloom-chunk")
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


def main():
    reference = json.loads(REFERENCE.read_text())
    rho = json.loads(RHO.read_text())
    base_receipt = json.loads(BASE_RECEIPT.read_text())
    scheduled = json.loads(SCHEDULE.read_text())["runs"][1]
    identity = reference["curve_identity_record"]
    curve_id = "EC1N83Ckb1h" + hashlib.sha256(frozen(identity)).hexdigest()[:12]
    assert curve_id == reference["curve_id"] == rho["curve_id"] == base_receipt["curve_id"]
    record = base_receipt["factor_base"]
    key_path = HERE / record["key_and_log_file"]
    assert sha(key_path) == record["key_and_log_file_sha256"]
    onb = field.Onb(83)
    curve = curves.Curve(onb)
    orbit = OrbitKey(onb)
    keys, logs = load_keys_logs(key_path)
    base = CompactOrbitBase(orbit, keys)
    assert len(base) == record["actual_usable_points_B_before_folding"]
    target = tuple(reference["workload"]["target"])
    assert list(target) == rho["public_target"]
    generator = tuple(identity["curve"]["generator"])
    order = identity["curve"]["subgroup_order"]
    eigen = record["frobenius_eigenvalue_mod_r"]
    assert curve.mul(generator, order) is None
    d_cross = scheduled["cross_orbit_zero_pair_class_domain"]
    table_step = scheduled["table_schedule"]["step"]
    table_offset = scheduled["table_schedule"]["offset"]
    query_step = table_step
    query_offset = (table_offset + 123456789) % d_cross
    assert math.gcd(query_step, d_cross) == 1
    synthetic_schedule = dict(scheduled)
    synthetic_schedule["query_schedule"] = {"step": 1, "offset": 0}
    compiler_command = [
        "clang++", "-O3", "-std=c++17", "-march=armv8.2-a+crypto",
        str(SOURCE), "-o", str(BINARY),
    ]
    subprocess.run(compiler_command, check=True)

    def decode_and_verify(hit, fixture_target):
        rank = affine_rank(hit["query_representative_position"], d_cross,
                           query_step, query_offset)
        oi, oj, relative = cross_orbit_pair(rank, len(keys), 166)
        k = hit["frobenius_shift"]
        negative = hit["negative_query_pair"]
        first = oi * 166 + lift_within(0, k, negative, 83)
        second = oj * 166 + lift_within(relative, k, negative, 83)
        unordered_rank = second * (second + 1) // 2 + first
        adapted = {
            "table_position": hit["table_position"],
            "query_position": unordered_rank,
            "x_key_hex": hit["x_key_hex"],
        }
        certificate = verify_hit(
            curve, orbit, base, logs, fixture_target, generator, order,
            eigen, adapted, synthetic_schedule)
        certificate["orbit_query_witness"] = {
            "representative_position": hit[
                "query_representative_position"],
            "frobenius_shift": k,
            "negative_query_pair": negative,
            "lifted_query_pair_indices": [first, second],
        }
        return certificate

    def execute(fixture_target, table_entries, query_reps, rep_batch,
                table_start=0, query_start=0):
        command = [
            str(BINARY), str(key_path),
            format(onb.toCoords(fixture_target[0]), "x"),
            format(onb.toCoords(fixture_target[1]), "x"),
            str(table_entries), str(query_reps), "1024",
            str(table_step), str(table_offset),
            str(query_step), str(query_offset),
            "20", "14", str(table_start), str(query_start),
            "8", str(rep_batch),
        ]
        row = json.loads(subprocess.run(
            command, check=True, capture_output=True, text=True).stdout)
        assert row["actual_B"] == len(base)
        assert row["table_descriptors"] == table_entries
        assert row["query_representatives"] == query_reps
        assert row["lifted_query_pairs"] == 166 * query_reps
        assert row["bloom_positive_queries"] == row[
            "false_positive_queries"] + row["exact_hit_queries"]
        assert row["table_start"] == table_start
        assert row["query_start"] == query_start
        return row

    public_rows = []
    verified_public = []
    for table_entries, query_reps, rep_batch in (
            (1 << 20, 1 << 14, 8),
            (1 << 24, 1 << 18, 8),
            (1 << 24, 1 << 18, 16)):
        row = execute(target, table_entries, query_reps, rep_batch)
        row["query_ns_per_lifted_pair"] = (
            row["query_seconds"] * 1e9 / row["lifted_query_pairs"])
        for hit in row["hits"]:
            certificate = decode_and_verify(hit, target)
            assert str(certificate["recovered_scalar"]) == rho[
                "recovered_scalar"]
            verified_public.append(certificate)
        public_rows.append(row)

    direct_query_pairs = public_rows[-1]["lifted_query_pairs"]
    direct_command = [
        str(DIRECT_BINARY), str(key_path),
        format(onb.toCoords(target[0]), "x"),
        format(onb.toCoords(target[1]), "x"),
        str(1 << 24), str(direct_query_pairs), "1024",
        str(table_step), str(table_offset),
        str(scheduled["query_schedule"]["step"]),
        str(scheduled["query_schedule"]["offset"]),
        "20", "14", "0", "8", "0",
    ]
    direct = json.loads(subprocess.run(
        direct_command, check=True, capture_output=True,
        text=True).stdout)
    assert direct["actual_B"] == len(base)
    assert direct["table_descriptors"] == 1 << 24
    assert direct["query_pairs"] == direct_query_pairs
    direct["query_ns_per_pair"] = (direct["query_seconds"] * 1e9 /
                                   direct_query_pairs)
    direct_public_certificates = []
    for hit in direct["hits"]:
        certificate = verify_hit(curve, orbit, base, logs, target,
                                 generator, order, eigen, hit, scheduled)
        assert str(certificate["recovered_scalar"]) == rho[
            "recovered_scalar"]
        direct_public_certificates.append(certificate)

    planted_table_start = 1024
    planted_query_start = 256
    table_rank = affine_rank(planted_table_start, d_cross,
                             table_step, table_offset)
    ti, tj, trel = cross_orbit_pair(table_rank, len(keys), 166)
    query_rank = affine_rank(planted_query_start, d_cross,
                             query_step, query_offset)
    qi, qj, qrel = cross_orbit_pair(query_rank, len(keys), 166)
    planted_k = 7
    planted_negative = True
    query_first = qi * 166 + lift_within(0, planted_k,
                                         planted_negative, 83)
    query_second = qj * 166 + lift_within(qrel, planted_k,
                                          planted_negative, 83)
    planted_target = None
    planted_indices = [ti * 166, tj * 166 + trel,
                       query_first, query_second]
    for index in planted_indices:
        planted_target = curve.add(planted_target, base[index])
    assert planted_target is not None and curve.onCurve(planted_target)
    planted = execute(planted_target, 4096, 256, 8,
                      planted_table_start, planted_query_start)
    assert planted["exact_hit_queries"] >= 1
    planted_hit = next(hit for hit in planted["hits"]
                       if hit["table_position"] == planted_table_start and
                       hit["query_representative_position"] == planted_query_start and
                       hit["frobenius_shift"] == planted_k and
                       hit["negative_query_pair"] == planted_negative)
    planted_certificate = decode_and_verify(planted_hit, planted_target)
    assert planted_certificate["independent_scalar_replay"] is True
    report = {
        "kind": "n83_native_signed_frobenius_query_orbit_bounded_stage",
        "scope": "bounded public-target stage plus planted exact-hit control; no complete n83 quotient solve",
        "concurrent_full_shard_running_during_timing": True,
        "proposal_id": "Q1050", "candidate_id": None, "run_id": None,
        "curve_id": curve_id,
        "curve_identity_record": identity,
        "isogeny": "none",
        "public_target": list(target),
        "factor_base": record,
        "table_schedule": scheduled["table_schedule"],
        "query_representative_schedule": {
            "domain": d_cross, "step": query_step,
            "offset": query_offset},
        "public_target_runs": public_rows,
        "direct_comparator_same_M_and_lifted_query_count": direct,
        "direct_comparator_verified_relations":
            direct_public_certificates,
        "direct_comparator_query_schedule":
            scheduled["query_schedule"],
        "direct_comparator_has_different_query_pairs": True,
        "verified_public_target_relations": verified_public,
        "verified_public_target_quotient_table_dlp": bool(verified_public),
        "planted_control": {
            "fixture_target": list(planted_target),
            "fixture_from_base_indices": planted_indices,
            "query_frobenius_shift": planted_k,
            "query_negative": planted_negative,
            "table_start": planted_table_start,
            "query_start": planted_query_start,
            "native_stage": planted,
            "verified_relation": planted_certificate,
            "natural_relation_yield": False,
        },
        "complete_one_target_work_log2": None,
        "compiler_command": compiler_command,
        "compiled_binary_sha256": sha(BINARY),
        "native_source_sha256": sha(SOURCE),
        "bloom_core_sha256": sha(CORE),
        "native_pairs_sha256": sha(PAIRS),
        "direct_source_sha256": sha(DIRECT_SOURCE),
        "direct_binary_sha256": sha(DIRECT_BINARY),
        "wrapper_source_sha256": sha(Path(__file__)),
        "base_receipt_sha256": sha(BASE_RECEIPT),
        "key_file_sha256": sha(key_path),
        "schedule_receipt_sha256": sha(SCHEDULE),
        "rho_reference_receipt_sha256": sha(RHO),
        "runtime": {"python": sys.version,
                    "platform": platform.platform()},
    }
    OUTPUT.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({
        "curve_id": curve_id,
        "public_exact_hits": [row["exact_hit_queries"]
                              for row in public_rows],
        "query_ns_per_lifted_pair": [row[
            "query_ns_per_lifted_pair"] for row in public_rows],
        "planted_scalar_replay": True,
    }))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Check a planted witness in the second table of a two-shard search."""

import hashlib
import json
import math
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CODEGEN = HERE.parents[1] / "ecc2k130" / "runner" / "codegen"
BASE_RECEIPT = HERE / "runs" / "n83_knownlog_orbit_base_k48194.json"
SCHEDULE = HERE / "runs" / "n53_n83_unique_schedule_perf.json"
SOURCE = HERE / "native_n83_orbit_query_two_shard.cpp"
CORE = HERE / "native_n83_bloom_core.hpp"
PAIRS = HERE / "native_n83_pairs.cpp"
BINARY = Path("/private/tmp/ecc2k83-native-orbit-two-shard-planted")
OUTPUT = HERE / "runs" / "n83_two_shard_second_table_planted.json"
K = 48194
L = 166
sys.path.insert(0, str(CODEGEN))

import curves
import field
from bench_n83_full_base import CompactOrbitBase
from bench_n83_knownlog import load_keys_logs
from bench_native_n83_table import verify_hit
from orbit_key import OrbitKey
from pair_schedule import affine_rank, cross_orbit_pair
from run_n23 import sha
from verify_query_orbit_reuse import lift_within


def main():
    base_receipt = json.loads(BASE_RECEIPT.read_text())
    record = base_receipt["factor_base"]
    assert base_receipt["proposal_id"] == "Q1051"
    assert record["actual_usable_points_B_before_folding"] == K * L
    assert record["signed_frobenius_columns"] == K
    key_path = HERE / record["key_and_log_file"]
    assert sha(key_path) == record["key_and_log_file_sha256"]
    keys, logs = load_keys_logs(key_path)
    assert len(keys) == len(logs) == K
    identity = base_receipt["curve_identity_record"]
    curve_id = "EC1N83Ckb1h" + hashlib.sha256(json.dumps(
        identity, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False).encode()).hexdigest()[:12]
    assert curve_id == base_receipt["curve_id"]
    onb = field.Onb(83)
    curve = curves.Curve(onb)
    orbit = OrbitKey(onb)
    base = CompactOrbitBase(orbit, keys)
    generator = tuple(identity["curve"]["generator"])
    order = identity["curve"]["subgroup_order"]
    eigen = record["frobenius_eigenvalue_mod_r"]
    assert curve.mul(generator, order) is None
    scheduled = json.loads(SCHEDULE.read_text())["runs"][1]
    domain = math.comb(K, 2) * L
    table_step = scheduled["table_schedule"]["step"]
    table_offset = scheduled["table_schedule"]["offset"]
    query_step = table_step
    query_offset = (table_offset + 123456789) % domain
    assert math.gcd(table_step, domain) == 1
    first_table_start = 0
    table_start = 4096
    query_start = 256
    shift = 7
    negative = True
    ti, tj, trel = cross_orbit_pair(affine_rank(
        table_start, domain, table_step, table_offset), K, L)
    qi, qj, qrel = cross_orbit_pair(affine_rank(
        query_start, domain, query_step, query_offset), K, L)
    qfirst = qi * L + lift_within(0, shift, negative, 83)
    qsecond = qj * L + lift_within(qrel, shift, negative, 83)
    indices = [ti * L, tj * L + trel, qfirst, qsecond]
    target = None
    for index in indices:
        target = curve.add(target, base[index])
    assert target is not None and curve.onCurve(target)
    compiler = [
        "clang++", "-O3", "-std=c++17", "-march=armv8.2-a+crypto",
        f"-DECC2K83_ORBITS={K}", str(SOURCE), "-o", str(BINARY),
    ]
    subprocess.run(compiler, check=True)
    command = [
        str(BINARY), str(key_path),
        format(onb.toCoords(target[0]), "x"),
        format(onb.toCoords(target[1]), "x"),
        "4096", "256", "1024", str(table_step), str(table_offset),
        str(query_step), str(query_offset), "20", "14",
        str(first_table_start), str(query_start), "8", "8",
        str(table_start),
    ]
    native = json.loads(subprocess.run(
        command, check=True, capture_output=True, text=True).stdout)
    assert native["actual_B"] == K * L
    assert native["exact_hit_queries"] >= 1
    hit = next(item for item in native["hits"]
               if item["shard"] == 1 and
               item["table_position"] == table_start and
               item["query_representative_position"] == query_start and
               item["frobenius_shift"] == shift and
               item["negative_query_pair"] == negative)
    query_rank = qsecond * (qsecond + 1) // 2 + qfirst
    adapted = {
        "table_position": hit["table_position"],
        "query_position": query_rank,
        "x_key_hex": hit["x_key_hex"],
    }
    synthetic = dict(scheduled)
    synthetic["cross_orbit_zero_pair_class_domain"] = domain
    synthetic["unordered_query_pair_domain"] = len(base) * (
        len(base) + 1) // 2
    synthetic["query_schedule"] = {"step": 1, "offset": 0}
    certificate = verify_hit(curve, orbit, base, logs, target,
                             generator, order, eigen, adapted, synthetic)
    assert certificate["independent_scalar_replay"] is True
    assert curve.mul(generator, certificate["recovered_scalar"]) == target
    report = {
        "kind": "n83_k48194_two_shard_second_table_planted_quotient_hit",
        "scope": "planted correctness control; not natural relation yield or a public-target DLP",
        "proposal_id": "Q1052", "candidate_id": None,
        "curve_id": curve_id,
        "curve_identity_record": identity,
        "isogeny": "none",
        "factor_base_enumerated_set_sha256": record[
            "enumerated_set_sha256"],
        "actual_usable_points_B_before_folding": len(base),
        "signed_frobenius_columns": K,
        "fixture_target": list(target),
        "fixture_from_base_indices": indices,
        "first_table_start": first_table_start,
        "second_table_start": table_start,
        "query_start": query_start,
        "frobenius_shift": shift,
        "negative_query_pair": negative,
        "native_result": native,
        "verified_relation": certificate,
        "natural_relation_yield": False,
        "compiler_command": compiler,
        "compiled_binary_sha256": sha(BINARY),
        "native_source_sha256": sha(SOURCE),
        "bloom_core_sha256": sha(CORE),
        "native_pairs_sha256": sha(PAIRS),
        "base_receipt_sha256": sha(BASE_RECEIPT),
        "key_file_sha256": sha(key_path),
        "schedule_receipt_sha256": sha(SCHEDULE),
        "source_sha256": sha(Path(__file__)),
    }
    OUTPUT.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"curve_id": curve_id, "actual_B": len(base),
                      "exact_hit_queries": native["exact_hit_queries"],
                      "scalar_replay": certificate[
                          "independent_scalar_replay"]}))


if __name__ == "__main__":
    main()

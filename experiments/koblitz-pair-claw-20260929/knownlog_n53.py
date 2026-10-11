#!/usr/bin/env python3
"""Complete n=53 one-target DLP using known-log orbit seeds and quotient pairs."""

import hashlib
import json
import math
import platform
import random
import resource
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
CODEGEN = HERE.parents[1] / "ecc2k130" / "runner" / "codegen"
REFERENCE = (HERE.parent / "ecc2k130-quotient-pair-probe-20260926" /
             "runs" / "n53_perf_prefix.json")
sys.path.insert(0, str(CODEGEN))

import curves
import field
from bench_n83_full_base import CompactOrbitBase
from orbit_key import OrbitKey
from probe_n53_table import witness
from run_n23 import CountingCurve, frozen, sha

N = 53
COLUMNS = 227
ORBIT_SIZE = 2 * N
BASE_SEED = 531042
TABLE_SEED = 530930
QUERY_SEED = 530931
TABLE_SAMPLES = 500000
QUERY_SAMPLES = 1500000
PROPOSAL_ID = "Q1042"


def point_key_digest(keys):
    return hashlib.sha256(b"".join(key.to_bytes(14, "little")
                                   for key in keys)).hexdigest()


def log_digest(logs):
    return hashlib.sha256(b"".join(log.to_bytes(6, "little")
                                   for log in logs)).hexdigest()


def build_knownlog_base(curve, orbit, generator, order, eigen):
    rng = random.Random(BASE_SEED)
    entries = {}
    seed_scalars = []
    while len(entries) < COLUMNS:
        alpha = rng.randrange(1, order)
        seed_scalars.append(alpha)
        point = curve.mul(generator, alpha)
        key, exponent, sign = orbit.canonical(point)
        if key in entries:
            continue
        entries[key] = sign * pow(eigen, exponent, order) * alpha % order
    keys = sorted(entries)
    logs = [entries[key] for key in keys]
    return keys, logs, seed_scalars


def main():
    reference = json.loads(REFERENCE.read_text())
    identity = reference["curve_identity_record"]
    curve_id = "EC1N53Ckb1h" + hashlib.sha256(frozen(identity)).hexdigest()[:12]
    assert reference["curve_id"] == curve_id
    order = identity["curve"]["subgroup_order"]
    assert curves.isPrimeBig(order)
    setup_start = time.perf_counter_ns()
    onb = field.Onb(N)
    curve = CountingCurve(onb)
    orbit = OrbitKey(onb)
    generator = tuple(identity["curve"]["generator"])
    target = tuple(reference["workload"]["target"])
    assert curve.mul(generator, order) is None
    assert curve.mul(target, order) is None
    eigen = curves.frobeniusEigenvalue(curve, generator, order)
    assert eigen != 1 and pow(eigen, N, order) == 1
    dependency_hashes = {name: sha(CODEGEN / name)
                         for name in ("curves.py", "field.py", "indexcalc.py")}
    source_hashes = {name: sha(HERE / name) for name in (
        "knownlog_n53.py", "orbit_key.py", "bench_n83_full_base.py",
        "probe_n53_table.py", "run_n23.py")}

    keys, logs, seed_scalars = build_knownlog_base(curve, orbit,
                                                    generator, order, eigen)
    base = CompactOrbitBase(orbit, keys)
    assert len(base) == COLUMNS * ORBIT_SIZE == 24062
    assert all(curve.mul(generator, log) == orbit.point_from_key(key)
               for key, log in zip(keys, logs))
    setup_ns = time.perf_counter_ns() - setup_start
    setup_calls = curve.calls.copy()
    eigen_powers = [pow(eigen, j, order) for j in range(N)]

    def log_at(index):
        orbit_index, within = divmod(index, ORBIT_SIZE)
        sign = 1 if within < N else -1
        return sign * eigen_powers[within % N] * logs[orbit_index] % order

    factor_base = {
        "construction": "first 227 distinct subgroup-point signed-Frobenius orbits from deterministic nonzero scalar multiples of G; all logs known by construction",
        "seed_scalar_rng": "random.Random(531042).randrange(1,r)",
        "seed_scalars_in_draw_order": seed_scalars,
        "selected_point_orbits": COLUMNS,
        "signed_frobenius_orbit_size": ORBIT_SIZE,
        "actual_usable_points_B_before_folding": len(base),
        "signed_frobenius_columns": COLUMNS,
        "enumerated_set_encoding": "sorted canonical signed-Frobenius point keys, 14-byte little-endian each; expand by both signs and 53 Frobenius powers",
        "enumerated_set_sha256": point_key_digest(keys),
        "canonical_orbit_keys": [str(key) for key in keys],
        "canonical_log_encoding": "sorted representative logs, 6-byte little-endian residues modulo r",
        "canonical_log_sha256": log_digest(logs),
        "canonical_logs": logs,
        "frobenius_eigenvalue_mod_r": eigen,
    }
    candidate_record = {
        "schema_version": 1,
        "field": identity["field"],
        "curve": dict(identity["curve"], curve_id=curve_id),
        "isogeny": "none",
        "endomorphism": {"endomorphism_order_conductor": None,
                          "frobenius_order_conductor": None,
                          "volcano_levels": "not_applicable_for_degree_two_in_characteristic_two"},
        "factor_base": factor_base,
        "point_decomposition": {
            "m": 4, "summation_chain": "group-law two-pair table and target-complement match modulo signed Frobenius",
            "solver_family": "quotient_pair_table", "stage_code": "PDP4qtable",
            "table_samples": TABLE_SAMPLES,
            "query_sample_cap": QUERY_SAMPLES,
            "canonicalization": "minimum synchronous Frobenius-cycle rotation over both signs",
            "point_encoding": "type-II ONB symmetric bit vector",
            "implementation_sha256": source_hashes["knownlog_n53.py"]},
        "relation_collection": {"policy": "none; factor-base logs known by construction",
                                "stage_code": "RCdirect",
                                "implementation_sha256": source_hashes["knownlog_n53.py"]},
        "relation_linear_algebra": "none",
        "target_descent": {"policy": "one ordinary four-point quotient pair match, then sum the known base logs",
                           "stage_code": "TDdirect",
                           "implementation_sha256": source_hashes["knownlog_n53.py"]},
        "implementation": {"source_sha256": source_hashes,
                           "dependency_sha256": dependency_hashes,
                           "python_implementation": platform.python_implementation()},
    }
    candidate_hash = hashlib.sha256(frozen(candidate_record)).hexdigest()
    candidate_id = ("IC1N53Ckb1fb24062PDP4qtableRCdirectLAnoneTDdirect"
                    f"ISO0h{candidate_hash[:12]}")
    candidate = dict(candidate_record, candidate_id=candidate_id,
                     candidate_record_sha256=candidate_hash)

    table_rng = random.Random(TABLE_SEED)
    table = {}
    table_start = time.perf_counter_ns()
    for _ in range(TABLE_SAMPLES):
        first = table_rng.randrange(len(base))
        second = table_rng.randrange(len(base))
        pair = curve.add(base[first], base[second])
        if pair is None:
            continue
        key, exponent, sign = orbit.canonical(pair)
        table.setdefault(key, (first, second, exponent, sign))
    table_ns = time.perf_counter_ns() - table_start
    table_calls = curve.calls.copy()
    membership_start = time.perf_counter_ns()
    base_set = set(base)
    membership_ns = time.perf_counter_ns() - membership_start
    query_rng = random.Random(QUERY_SEED)
    query_start = time.perf_counter_ns()
    relation = None
    proper_rejections = 0
    for query_number in range(1, QUERY_SAMPLES + 1):
        first = query_rng.randrange(len(base))
        second = query_rng.randrange(len(base))
        pair = curve.add(base[first], base[second])
        if pair is None:
            continue
        complement = curve.add(target, curve.neg(pair))
        key, exponent, sign = orbit.canonical(complement)
        earlier = table.get(key)
        if earlier is None:
            continue
        relation = witness(curve, base, base_set, target, orbit,
                           earlier, (first, second, exponent, sign))
        if relation is not None:
            break
        proper_rejections += 1
    query_ns = time.perf_counter_ns() - query_start
    query_calls = curve.calls.copy()
    assert relation is not None, "target relation budget exhausted"
    recovery_start = time.perf_counter_ns()
    zero = relation["zero_meta"]
    one = relation["one_meta"]
    shift = relation["frobenius_shift_of_zero_pair"]
    sign = relation["sign_of_zero_pair"]
    recovered = (sign * eigen_powers[shift] *
                 (log_at(zero[0]) + log_at(zero[1])) +
                 log_at(one[0]) + log_at(one[1])) % order
    assert curve.mul(generator, recovered) == target
    recovery_ns = time.perf_counter_ns() - recovery_start
    recovery_calls = curve.calls.copy()
    fixture_start = time.perf_counter_ns()
    assert recovered == reference["target_fixture_scalar"]
    fixture_validation_ns = time.perf_counter_ns() - fixture_start

    workload = {"curve_id": curve_id, "target": list(target),
                "target_count": 1,
                "target_input_law": "fixed public subgroup point",
                "table_sample_seed": TABLE_SEED,
                "query_sample_seed": QUERY_SEED,
                "table_samples": TABLE_SAMPLES,
                "query_sample_cap": QUERY_SAMPLES,
                "fixture_scalar_validation_only": reference["target_fixture_scalar"]}
    workload_id = hashlib.sha256(frozen(workload)).hexdigest()[:12]
    phases = {"target_query": 0, "target_pdp": query_ns,
              "target_relation_check": 0, "target_descent": 0,
              "target_recovery_check": recovery_ns}
    report = {
        "kind": "n53_knownlog_quotient_pair_complete_one_target_dlp",
        "scope": "complete one-target known-log orbit-base pipeline; no n83 solve or rho speedup claim",
        "proposal_id": PROPOSAL_ID,
        "candidate_id": candidate_id,
        "run_id": f"{candidate_id}W{workload_id}R1",
        "workload_id": workload_id, "workload": workload,
        "curve_id": curve_id, "curve_identity_record": identity,
        "isogeny": "none", "factor_base": factor_base,
        "target_independent_base_setup_wall_ns": setup_ns,
        "target_independent_table_build_wall_ns": table_ns,
        "target_independent_membership_index_wall_ns": membership_ns,
        "table_samples": TABLE_SAMPLES,
        "table_distinct_keys": len(table),
        "target_query_samples_to_relation": query_number,
        "target_proper_rejections": proper_rejections,
        "relation": relation,
        "verified_relation_count": 1,
        "verified_single_target_dlp": True,
        "recovered_scalar": recovered,
        "fixture_scalar_validation_only": reference["target_fixture_scalar"],
        "fixture_scalar_validation_wall_ns_outside_online": fixture_validation_ns,
        "online_phase_wall_ns": phases,
        "online_one_target_wall_ns": sum(phases.values()),
        "cold_total_wall_ns": setup_ns + table_ns + membership_ns + sum(phases.values()),
        "online_interval": "first target-dependent complement-pair query through independent scalar replay; base and table setup excluded",
        "rho_online_wall_ns": None, "online_speedup": None,
        "logical_pair_samples_cold": TABLE_SAMPLES + query_number,
        "logical_pair_samples_cold_log2": math.log2(TABLE_SAMPLES + query_number),
        "common_operation_total": None,
        "group_api_calls_base_setup": dict(setup_calls),
        "group_api_calls_table_build": dict(table_calls - setup_calls),
        "group_api_calls_target_query": dict(query_calls - table_calls),
        "group_api_calls_target_recovery": dict(recovery_calls - query_calls),
        "operation_accounting": "group API categories are nested; logical pair samples omit base generation and scalar replay; no field-operation equivalent is asserted",
        "peak_parent_rss_bytes": (resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
                                  if platform.system() == "Darwin" else
                                  resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024),
        "runtime": {"python": sys.version, "platform": platform.platform()},
        "source_sha256": source_hashes["knownlog_n53.py"],
        "dependency_sha256": dependency_hashes,
        "candidate_record_sha256": candidate_hash,
        "reference_sha256": sha(REFERENCE),
    }
    candidate_path = HERE / "candidates" / f"{candidate_id}.json"
    run_path = HERE / "runs" / "n53_knownlog_one_target.json"
    candidate_path.write_text(json.dumps(candidate, indent=2) + "\n")
    run_path.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"candidate_id": candidate_id,
                      "actual_B": len(base), "columns": COLUMNS,
                      "table_samples": TABLE_SAMPLES,
                      "query_samples": query_number,
                      "online_wall_s": report["online_one_target_wall_ns"] / 1e9,
                      "recovered_scalar": recovered,
                      "receipt": str(run_path)}))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Count field API calls in a deterministic replay of the verified n=53 DLP.

This is an instrumented stage diagnostic. It does not replace the immutable
candidate manifest or the original uninstrumented online wall measurement.
"""

import argparse
import json
import math
import random
import time
from collections import Counter
from pathlib import Path

from bench_n83_full_base import CompactOrbitBase
from bench_steps import CountingOnb
from knownlog_n53 import (BASE_SEED, COLUMNS, N, ORBIT_SIZE, QUERY_SAMPLES,
                          QUERY_SEED, TABLE_SAMPLES, TABLE_SEED,
                          build_knownlog_base)
from orbit_key import OrbitKey
from probe_n53_table import witness
from run_n23 import CountingCurve, sha

HERE = Path(__file__).resolve().parent
REFERENCE = HERE / "runs" / "n53_knownlog_one_target.json"
OUTPUT = HERE / "runs" / "n53_knownlog_field_api_replay_q1076.json"
METHODS = ("add", "mul", "sqr", "inv", "frob")


def delta(after, before):
    result = {name: after[name] - before[name] for name in METHODS}
    assert all(value >= 0 for value in result.values())
    # Onb.sqr calls Onb.frob once. Keep direct Frobenius separate so the
    # primitive-operation total never double counts a square.
    result["direct_frob"] = result["frob"] - result["sqr"]
    assert result["direct_frob"] >= 0
    return result


def weighted_calls(phase):
    return (phase["add"] + phase["mul"] + phase["sqr"] +
            phase["direct_frob"] + 90 * phase["inv"])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime-info", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=OUTPUT)
    args = parser.parse_args()
    assert not args.out.exists(), "refusing to overwrite a metering receipt"
    runtime = json.loads(args.runtime_info.read_text())
    assert runtime["status"] == "verified"
    original = json.loads(REFERENCE.read_text())
    assert original["verified_single_target_dlp"]
    assert original["curve_id"] == "EC1N53Ckb1hf77aab617904"
    assert original["isogeny"] == "none"
    assert original["factor_base"]["selected_point_orbits"] == COLUMNS
    assert original["factor_base"]["actual_usable_points_B_before_folding"] == COLUMNS * ORBIT_SIZE
    assert original["workload"]["table_sample_seed"] == TABLE_SEED
    assert original["workload"]["query_sample_seed"] == QUERY_SEED
    assert original["workload"]["table_samples"] == TABLE_SAMPLES
    assert original["workload"]["query_sample_cap"] == QUERY_SAMPLES
    assert BASE_SEED == 531042 and N == 53

    identity = original["curve_identity_record"]
    order = identity["curve"]["subgroup_order"]
    generator = tuple(identity["curve"]["generator"])
    target = tuple(original["workload"]["target"])
    onb = CountingOnb(N)
    curve = CountingCurve(onb)
    orbit = OrbitKey(onb)
    counts = Counter(onb.calls)
    started = time.perf_counter_ns()
    assert curve.mul(generator, order) is None
    assert curve.mul(target, order) is None
    import curves
    eigen = curves.frobeniusEigenvalue(curve, generator, order)
    assert eigen != 1 and pow(eigen, N, order) == 1
    keys, logs, seeds = build_knownlog_base(curve, orbit, generator, order,
                                            eigen)
    base = CompactOrbitBase(orbit, keys)
    assert len(base) == COLUMNS * ORBIT_SIZE
    assert seeds == original["factor_base"]["seed_scalars_in_draw_order"]
    assert [str(key) for key in keys] == original["factor_base"]["canonical_orbit_keys"]
    assert logs == original["factor_base"]["canonical_logs"]
    assert all(curve.mul(generator, log) == orbit.point_from_key(key)
               for key, log in zip(keys, logs))
    setup_ns = time.perf_counter_ns() - started
    setup_calls = delta(onb.calls, counts)
    counts = Counter(onb.calls)

    table_rng = random.Random(TABLE_SEED)
    table = {}
    started = time.perf_counter_ns()
    for _ in range(TABLE_SAMPLES):
        first = table_rng.randrange(len(base))
        second = table_rng.randrange(len(base))
        pair = curve.add(base[first], base[second])
        if pair is None:
            continue
        key, exponent, sign = orbit.canonical(pair)
        table.setdefault(key, (first, second, exponent, sign))
    table_ns = time.perf_counter_ns() - started
    assert len(table) == original["table_distinct_keys"]
    table_calls = delta(onb.calls, counts)
    counts = Counter(onb.calls)

    started = time.perf_counter_ns()
    base_set = set(base)
    membership_ns = time.perf_counter_ns() - started
    membership_calls = delta(onb.calls, counts)
    counts = Counter(onb.calls)

    query_rng = random.Random(QUERY_SEED)
    relation = None
    proper_rejections = 0
    started = time.perf_counter_ns()
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
        relation = witness(curve, base, base_set, target, orbit, earlier,
                           (first, second, exponent, sign))
        if relation is not None:
            break
        proper_rejections += 1
    query_ns = time.perf_counter_ns() - started
    assert relation == original["relation"]
    assert query_number == original["target_query_samples_to_relation"]
    assert proper_rejections == original["target_proper_rejections"]
    query_calls = delta(onb.calls, counts)
    counts = Counter(onb.calls)

    eigen_powers = [pow(eigen, j, order) for j in range(N)]
    def log_at(index):
        orbit_index, within = divmod(index, ORBIT_SIZE)
        sign = 1 if within < N else -1
        return sign * eigen_powers[within % N] * logs[orbit_index] % order

    started = time.perf_counter_ns()
    zero = relation["zero_meta"]
    one = relation["one_meta"]
    recovered = (relation["sign_of_zero_pair"] *
                 eigen_powers[relation["frobenius_shift_of_zero_pair"]] *
                 (log_at(zero[0]) + log_at(zero[1])) +
                 log_at(one[0]) + log_at(one[1])) % order
    assert recovered == original["recovered_scalar"]
    assert curve.mul(generator, recovered) == target
    recovery_ns = time.perf_counter_ns() - started
    recovery_calls = delta(onb.calls, counts)
    phases = {
        "base_setup": setup_calls,
        "table_build": table_calls,
        "membership_index": membership_calls,
        "target_query_and_relation_check": query_calls,
        "target_scalar_replay": recovery_calls,
    }
    cold_weighted = sum(weighted_calls(phase) for phase in phases.values())
    online_weighted = weighted_calls(query_calls) + weighted_calls(recovery_calls)
    report = {
        "kind": "n53_knownlog_field_api_deterministic_replay",
        "scope": "instrumented replay of the archived complete n=53 control; field API counts and a separately labeled inversion-weight model, not an uninstrumented wall comparison",
        "proposal_id": "Q1076", "candidate_id": None, "run_id": None,
        "reference_candidate_id": original["candidate_id"],
        "reference_run_id": original["run_id"],
        "workload_id": original["workload_id"],
        "curve_id": original["curve_id"], "isogeny": "none",
        "factor_base_enumerated_set_sha256": original["factor_base"]["enumerated_set_sha256"],
        "actual_usable_points_B_before_folding": len(base),
        "signed_frobenius_columns": COLUMNS,
        "target_query_samples_to_relation": query_number,
        "verified_single_target_dlp_replayed": True,
        "recovered_scalar": recovered,
        "phase_field_api_calls": phases,
        "phase_metered_wall_ns": {
            "base_setup": setup_ns, "table_build": table_ns,
            "membership_index": membership_ns,
            "target_query_and_relation_check": query_ns,
            "target_scalar_replay": recovery_ns,
        },
        "cold_field_api_90_inv_weight_model": cold_weighted,
        "cold_field_api_90_inv_weight_model_log2": math.log2(cold_weighted),
        "online_field_api_90_inv_weight_model": online_weighted,
        "online_field_api_90_inv_weight_model_log2": math.log2(online_weighted),
        "operation_boundary": "counts Onb.add, mul, sqr, direct frob, and inv calls; sqr's nested frob is removed; each inv is assigned 90 calls only for the labeled model; excludes Python control, keying, hashing, memory traffic, and scalar integer arithmetic",
        "inversion_weight_status": "assumed for comparison with the n=83 native field-call convention; the n=53 Python Euclidean inversion implementation is not calibrated to 90 primitives",
        "original_receipt_sha256": sha(REFERENCE),
        "sage_runtime_info_sha256": sha(args.runtime_info),
        "source_sha256": sha(Path(__file__)),
    }
    args.out.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({
        "curve_id": report["curve_id"],
        "query_samples": query_number,
        "cold_model_log2": report["cold_field_api_90_inv_weight_model_log2"],
        "online_model_log2": report["online_field_api_90_inv_weight_model_log2"],
        "recovered_scalar": recovered,
        "receipt": str(args.out),
    }), flush=True)


if __name__ == "__main__":
    main()

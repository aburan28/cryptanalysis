#!/usr/bin/env python3
"""Paired direct/quotient pair-step timings on named n=53 and n=83 curves."""

import hashlib
import json
import platform
import statistics
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
CODEGEN = HERE.parents[1] / "ecc2k130" / "runner" / "codegen"
REFS = HERE.parent / "ecc2k130-quotient-pair-probe-20260926" / "runs"
sys.path.insert(0, str(CODEGEN))

import curves
import field
from bench_steps import sample_base
from orbit_key import OrbitKey
from quotient_walk import step as quotient_step
from run_n23 import frozen, point_digest, sha, step as direct_step

STEPS = 2048
REPETITIONS = 3


def benchmark(n):
    reference_path = REFS / f"n{n}_perf_prefix.json"
    reference = json.loads(reference_path.read_text())
    identity = reference["curve_identity_record"]
    assert reference["curve_id"] == (f"EC1N{n}Ckb1h" +
                                     hashlib.sha256(frozen(identity)).hexdigest()[:12])
    order = identity["curve"]["subgroup_order"]
    cofactor = identity["curve"]["cofactor"]
    onb = field.Onb(n)
    curve = curves.Curve(onb)
    orbit = OrbitKey(onb)
    generator = tuple(identity["curve"]["generator"])
    target = tuple(reference["workload"]["target"])
    assert curve.mul(generator, order) is None
    assert curve.mul(target, order) is None
    base, considered = sample_base(curve, onb, n, order, cofactor)

    direct_times = []
    quotient_times = []
    final_direct = []
    final_quotient = []
    for repeat in range(REPETITIONS):
        start_point = curve.mul(generator, repeat + 1)
        state = start_point
        started = time.perf_counter_ns()
        for _ in range(STEPS):
            state, _ = direct_step(curve, base, target, state)
        direct_times.append(time.perf_counter_ns() - started)
        final_direct.append(list(state))

        state_key = orbit.canonical(start_point)[0]
        started = time.perf_counter_ns()
        for _ in range(STEPS):
            state_key, _ = quotient_step(curve, base, target, orbit, state_key)
        quotient_times.append(time.perf_counter_ns() - started)
        final_quotient.append(state_key)

    direct_median = statistics.median(direct_times) / STEPS
    quotient_median = statistics.median(quotient_times) / STEPS
    return {
        "curve_id": reference["curve_id"],
        "curve_identity_record": identity,
        "reference_sha256": sha(reference_path),
        "candidate_id": None, "isogeny": "none",
        "public_target": list(target),
        "stage_base_policy": f"first 128 rational nonzero ONB x supports of weight at most two, projected by [{cofactor}], with both signs",
        "stage_base_B_before_folding": len(base),
        "stage_base_set_sha256": point_digest(base),
        "stage_base_coordinates_considered": considered,
        "full_factor_base_enumerated": False,
        "steps_per_repetition": STEPS, "repetitions": REPETITIONS,
        "direct_timed_ns_each": direct_times,
        "quotient_timed_ns_each": quotient_times,
        "direct_median_ns_per_step": direct_median,
        "quotient_median_ns_per_step": quotient_median,
        "quotient_to_direct_step_wall_ratio": quotient_median / direct_median,
        "orbit_size_if_full": 2 * n,
        "conditional_random_claw_step_saving_factor": (2 * n) ** 0.5,
        "end_direct_states": final_direct,
        "end_quotient_keys": [str(key) for key in final_quotient],
        "relation_yield": None, "verified_dlp": False,
        "complete_work_log2": None,
    }


def main():
    report = {
        "kind": "paired_direct_vs_signed_frobenius_quotient_pair_step_benchmark",
        "scope": "measured stage throughput on 256-point bases; sqrt-orbit claw gain remains conditional",
        "runs": [benchmark(n) for n in (53, 83)],
        "source_sha256": sha(Path(__file__)),
        "orbit_key_sha256": sha(HERE / "orbit_key.py"),
        "quotient_walk_sha256": sha(HERE / "quotient_walk.py"),
        "direct_walk_sha256": sha(HERE / "run_n23.py"),
        "dependency_sha256": {name: sha(CODEGEN / name)
                              for name in ("curves.py", "field.py", "indexcalc.py")},
        "runtime": {"python": sys.version, "platform": platform.platform()},
    }
    path = HERE / "runs" / "n53_n83_quotient_step_perf.json"
    path.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"runs": [{"curve_id": row["curve_id"],
                                  "direct_ns": row["direct_median_ns_per_step"],
                                  "quotient_ns": row["quotient_median_ns_per_step"],
                                  "ratio": row["quotient_to_direct_step_wall_ratio"]}
                                 for row in report["runs"]]}))


if __name__ == "__main__":
    main()

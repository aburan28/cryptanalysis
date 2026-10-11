#!/usr/bin/env python3
"""Measured n=53/n=83 pair-claw step cost on fixed public curves.

This is a stage benchmark. Its small sampled bases cannot support a claim
about relation yield, full factor-base construction, or a DLP at either n.
"""

import hashlib
import json
import platform
import statistics
import sys
import time
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
CODEGEN = HERE.parents[1] / "ecc2k130" / "runner" / "codegen"
REFS = HERE.parent / "ecc2k130-quotient-pair-probe-20260926" / "runs"
sys.path.insert(0, str(CODEGEN))

import curves
import field
import indexcalc
from run_n23 import POINT_HASH_BYTES, frozen, point_digest, sha, step

BASE_POSITIVE_POINTS = 128
TIMED_STEPS = 2048
REPETITIONS = 3


class CountingOnb(field.Onb):
    def __init__(self, n):
        super().__init__(n)
        self.calls = Counter()

    def add(self, a, b):
        self.calls["add"] += 1
        return super().add(a, b)

    def mul(self, a, b):
        self.calls["mul"] += 1
        return super().mul(a, b)

    def inv(self, a):
        self.calls["inv"] += 1
        return super().inv(a)

    def sqr(self, a):
        self.calls["sqr"] += 1
        return super().sqr(a)

    def frob(self, a, k):
        self.calls["frob"] += 1
        return super().frob(a, k)


def sample_base(curve, onb, n, order, cofactor):
    points = set()
    coordinates_considered = 0
    for support in indexcalc.combinationsUpTo(n, 2):
        if not support:
            continue
        coordinates_considered += 1
        x = onb.fromCoords(sum(1 << bit for bit in support))
        lifted = curve.pointFromX(x)
        if lifted is None:
            continue
        projected = curve.mul(lifted, cofactor)
        if projected is None:
            continue
        assert curve.mul(projected, order) is None
        points.add(projected)
        points.add(curve.neg(projected))
        if len(points) == BASE_POSITIVE_POINTS * 2:
            break
    assert len(points) == BASE_POSITIVE_POINTS * 2
    return sorted(points), coordinates_considered


def benchmark(n):
    reference_path = REFS / f"n{n}_perf_prefix.json"
    reference = json.loads(reference_path.read_text())
    identity = reference["curve_identity_record"]
    assert identity["field"]["n"] == n
    assert reference["curve_id"] == (f"EC1N{n}Ckb1h" +
                                     hashlib.sha256(frozen(identity)).hexdigest()[:12])
    cofactor = identity["curve"]["cofactor"]
    assert identity["curve"]["order"] == cofactor * identity["curve"]["subgroup_order"]
    order = int(reference["subgroup_order"])
    assert order == identity["curve"]["subgroup_order"]
    onb = field.Onb(n)
    curve = curves.Curve(onb)
    generator = tuple(identity["curve"]["generator"])
    target = tuple(reference["workload"]["target"])
    assert curve.onCurve(generator) and curve.onCurve(target)
    assert curve.mul(generator, order) is None
    assert curve.mul(target, order) is None
    base, considered = sample_base(curve, onb, n, order, cofactor)
    assert all(curve.onCurve(point) for point in base)
    assert max(max(point).bit_length() for point in base + [target]) <= 8 * POINT_HASH_BYTES

    times = []
    endings = []
    for repeat in range(REPETITIONS):
        state = curve.mul(generator, repeat + 1)
        before = time.perf_counter_ns()
        for _ in range(TIMED_STEPS):
            state, _ = step(curve, base, target, state)
        times.append(time.perf_counter_ns() - before)
        endings.append(list(state))

    counted_onb = CountingOnb(n)
    counted_curve = curves.Curve(counted_onb)
    state = generator
    for _ in range(TIMED_STEPS):
        state, _ = step(counted_curve, base, target, state)
    assert curve.onCurve(state)
    counts_per_step = {key: count / TIMED_STEPS
                       for key, count in counted_onb.calls.items()}
    return {
        "curve_id": reference["curve_id"],
        "curve_identity_record": identity,
        "reference_sha256": sha(reference_path),
        "public_target": list(target),
        "candidate_id": None,
        "isogeny": "none",
        "stage_base_policy": f"first 128 rational nonzero ONB x supports of weight at most two, projected by [{cofactor}], with both signs",
        "stage_base_B_before_folding": len(base),
        "stage_base_set_sha256": point_digest(base),
        "stage_base_coordinates_considered": considered,
        "full_factor_base_enumerated": False,
        "timed_steps_per_repetition": TIMED_STEPS,
        "repetitions": REPETITIONS,
        "timed_ns_each": times,
        "median_ns_per_step": statistics.median(times) / TIMED_STEPS,
        "field_api_calls_per_step": counts_per_step,
        "field_api_accounting": "logical API calls; square invokes Frobenius, so nested categories are not summed; wall time uses the uninstrumented field",
        "end_states": endings,
        "relation_yield": None,
        "verified_dlp": False,
        "complete_work_log2": None,
    }


def main():
    report = {
        "kind": "pair_claw_stage_step_benchmark_n53_n83",
        "scope": "measured point-to-pair step throughput only; not a relation or full-solve measurement",
        "point_encoding_bytes_per_coordinate": POINT_HASH_BYTES,
        "runs": [benchmark(n) for n in (53, 83)],
        "source_sha256": sha(Path(__file__)),
        "walk_source_sha256": sha(HERE / "run_n23.py"),
        "dependency_sha256": {name: sha(CODEGEN / name)
                              for name in ("curves.py", "field.py", "indexcalc.py")},
        "runtime": {"python": sys.version, "platform": platform.platform()},
    }
    path = HERE / "runs" / "n53_n83_step_perf.json"
    path.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"runs": [{"curve_id": run["curve_id"],
                                  "stage_B": run["stage_base_B_before_folding"],
                                  "median_ns_per_step": run["median_ns_per_step"],
                                  "field_api_calls_per_step": run["field_api_calls_per_step"]}
                                 for run in report["runs"]]}))


if __name__ == "__main__":
    main()

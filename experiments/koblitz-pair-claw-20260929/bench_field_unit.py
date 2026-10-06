#!/usr/bin/env python3
"""Calibrate local field API costs for the n53/n83 ONB implementation."""

import json
import platform
import random
import statistics
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
CODEGEN = HERE.parents[1] / "ecc2k130" / "runner" / "codegen"
sys.path.insert(0, str(CODEGEN))
import field
from run_n23 import sha

SAMPLES = 8192
REPETITIONS = 5


def timed(field_object, name, left, right):
    operation = getattr(field_object, name)
    times = []
    checksums = []
    for _ in range(REPETITIONS):
        checksum = 0
        start = time.perf_counter_ns()
        if right is None:
            for a in left:
                checksum ^= operation(a)
        else:
            for a, b in zip(left, right):
                checksum ^= operation(a, b)
        times.append(time.perf_counter_ns() - start)
        checksums.append(checksum)
    assert len(set(checksums)) == 1
    return {"total_ns_each": times,
            "median_ns_per_call": statistics.median(times) / SAMPLES,
            "checksum": checksums[0]}


def benchmark(n):
    f = field.Onb(n)
    rng = random.Random(1044 + n)
    left = [f.randomElement(rng) or f.one() for _ in range(SAMPLES)]
    right = [f.randomElement(rng) or f.one() for _ in range(SAMPLES)]
    # Initialize the squaring lookup table before timing all operations.
    for a in left[:40]:
        f.sqr(a)
    for a in left[:16]:
        assert f.mul(a, f.inv(a)) == f.one()
    measures = {name: timed(f, name, left, right if name in ("add", "mul")
                            else None)
                for name in ("add", "mul", "sqr", "inv")}
    mul_time = measures["mul"]["median_ns_per_call"]
    return {"degree": n, "samples_per_operation_per_repetition": SAMPLES,
            "repetitions": REPETITIONS, "operations": measures,
            "time_ratio_to_one_mul": {name: value["median_ns_per_call"] / mul_time
                                      for name, value in measures.items()}}


def main():
    report = {
        "kind": "local_python_onb_field_api_time_calibration",
        "scope": "implementation-specific Python timing ratios, not a mathematical field-operation equivalence",
        "runs": [benchmark(n) for n in (53, 83)],
        "source_sha256": sha(Path(__file__)),
        "field_source_sha256": sha(CODEGEN / "field.py"),
        "runtime": {"python": sys.version, "platform": platform.platform()},
    }
    path = HERE / "runs" / "n53_n83_field_unit_perf.json"
    path.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"runs": [
        {"degree": run["degree"],
         "mul_ns": run["operations"]["mul"]["median_ns_per_call"],
         "relative": run["time_ratio_to_one_mul"]}
        for run in report["runs"]]}))


if __name__ == "__main__":
    main()

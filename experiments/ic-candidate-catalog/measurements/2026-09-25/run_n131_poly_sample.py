#!/usr/bin/env python3
"""Sample subgroup-usable x density for an unmaterialized N131 polynomial base."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import random
import resource
import sys
import time


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
SOURCE = ROOT / "experiments/nonfrobenius-ic/index_calculus.py"
sys.path.insert(0, str(SOURCE.parent))
import index_calculus as ic  # noqa: E402


def canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def wilson95(successes: int, trials: int) -> tuple[float, float]:
    z = 1.959963984540054
    p = successes / trials
    denominator = 1 + z * z / trials
    center = (p + z * z / (2 * trials)) / denominator
    half = z * math.sqrt(p * (1 - p) / trials + z * z / (4 * trials * trials)) / denominator
    return max(0.0, center - half), min(1.0, center + half)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dimension", type=int, choices=(24, 28), required=True)
    parser.add_argument("--samples", type=int, default=1024)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        parser.error("output already exists")
    if not 1 <= args.samples <= 4096:
        parser.error("samples must be between 1 and 4096")
    ledger = ic.Ledger()
    curve, order = ic.setup("ecc2k130", ledger)
    population = 1 << args.dimension
    xs = random.Random(args.seed).sample(range(population), args.samples)
    start = time.perf_counter_ns()
    records = []
    for x in xs:
        lifts = curve.lift(x)
        assert all(curve.on_curve(point) for point in lifts)
        if len(lifts) == 2:
            assert curve.neg(lifts[0]) == lifts[1]
        usable = bool(lifts) and curve.mul(lifts[0], order) is None
        records.append({"x": x, "lift_count": len(lifts),
                        "subgroup_usable": usable})
    elapsed_ns = time.perf_counter_ns() - start
    usable_x = sum(item["subgroup_usable"] for item in records)
    interval = wilson95(usable_x, args.samples)
    profile_id = f"n131_poly_d{args.dimension}_m{5 if args.dimension == 28 else 6}"
    report = {
        "kind": "bounded_uniform_x_subgroup_base_density_sample",
        "status": "sample_only_not_exact_base_count",
        "profile_id": profile_id,
        "field_degree": 131,
        "subgroup_order": str(order),
        "dimension": args.dimension,
        "x_population": population,
        "sampling": "uniform without replacement from all d-bit polynomial-coordinate x values",
        "seed": args.seed,
        "sample_count": args.samples,
        "sample_x_sha256": hashlib.sha256(canonical(xs).encode()).hexdigest(),
        "usable_x_sample_count": usable_x,
        "usable_point_sample_count": 2 * usable_x,
        "usable_x_rate": usable_x / args.samples,
        "usable_x_wilson95": interval,
        "estimated_actual_base_points": 2 * population * usable_x / args.samples,
        "estimated_base_points_wilson95": [2 * population * bound for bound in interval],
        "exact_actual_base_points": None,
        "exact_factor_base_digest": None,
        "wall_ns": elapsed_ns,
        "peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "source_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "records": records,
        "single_target_online_ms": None,
        "rho_speedup": None,
    }
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Materialize a bounded N131 ONB Hamming-weight base with subgroup filtering."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import resource
import signal
import sys
import time


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
CODE = ROOT / "ecc2k130/codegen"
sys.path.insert(0, str(CODE))
import curves  # noqa: E402
import field  # noqa: E402
import indexcalc  # noqa: E402


def canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def timeout_handler(_signum: int, _frame: object) -> None:
    raise TimeoutError("base construction exceeded declared wall limit")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--weight", type=int, choices=(2, 3), required=True)
    parser.add_argument("--wall-limit-seconds", type=int, default=300)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        parser.error("output already exists")
    profile_id = f"n131_onb_hw{args.weight}_m{args.weight + 2}"
    profiles = json.loads((HERE.parents[1] / "profiles.json").read_text())["profiles"]
    profile = next(item for item in profiles if item["id"] == profile_id)
    order = curves.curveOrder(131)
    assert order % 4 == 0
    assert order // 4 == 680564733841876926932320129493409985129
    subgroup_order = order // 4
    onb = field.Onb(131)
    curve = curves.Curve(onb)
    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(args.wall_limit_seconds)
    whole_start = start = time.perf_counter_ns()
    status = "complete"
    try:
        points, orbits = indexcalc.factorBase(onb, curve, args.weight)
        construction_ns = time.perf_counter_ns() - start
        start = time.perf_counter_ns()
        usable = [rep for rep in orbits if curve.mul(points[rep], subgroup_order) is None]
        filtering_ns = time.perf_counter_ns() - start
        start = time.perf_counter_ns()
        encoded = []
        for rep in usable:
            for coordinate in orbits[rep]:
                point = points[coordinate]
                for signed in (point, curve.neg(point)):
                    encoded.append([onb.toCoords(signed[0]), onb.toCoords(signed[1])])
        encoded.sort()
        assert len(encoded) == len({tuple(point) for point in encoded})
        encoding_ns = time.perf_counter_ns() - start
        report = {
            "status": status,
            "profile_id": profile_id,
            "field_degree": 131,
            "field_representation": "permuted_type_II_optimal_normal_basis",
            "subgroup_order": str(subgroup_order),
            "hamming_weight_limit": args.weight,
            "candidate_x_coordinates": sum(math.comb(131, k) for k in range(args.weight + 1)),
            "geometric_x_coordinates": len(points),
            "geometric_x_orbits": len(orbits),
            "subgroup_usable_x_orbits": len(usable),
            "subgroup_usable_points_before_folding": len(encoded),
            "subgroup_usable_folded_columns": len(usable),
            "point_encoding": "sorted decimal ONB coordinate-mask pairs, both signs",
            "point_set_sha256": hashlib.sha256(canonical(encoded).encode()).hexdigest(),
            "phase_wall_ns": {"geometric_construction": construction_ns,
                              "orbit_representative_subgroup_filter": filtering_ns,
                              "point_encoding": encoding_ns},
            "peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            "source_sha256": {name: hashlib.sha256((CODE / name).read_bytes()).hexdigest()
                              for name in ("indexcalc.py", "curves.py", "field.py")},
            "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "factor_log_cost": None,
            "pdp_solver_cost": None,
            "single_target_online_ms": None,
        }
    except TimeoutError:
        report = {"status": "timeout", "profile_id": profile_id,
                  "wall_limit_seconds": args.wall_limit_seconds,
                  "elapsed_wall_ns": time.perf_counter_ns() - whole_start,
                  "subgroup_usable_points_before_folding": None,
                  "single_target_online_ms": None}
    finally:
        signal.alarm(0)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()

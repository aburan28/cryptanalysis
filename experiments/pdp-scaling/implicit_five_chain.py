#!/usr/bin/env python3
"""Exact compact five-point constraint graph and four cofactor target fibers.

This is a symbolic arithmetic circuit, not an expanded Boolean ANF or a
completed SAT/GB solve. Each ADD gate denotes the complete curve group law,
including infinity, doubling, inverse, and generic addition cases.
"""

import argparse
import hashlib
import json
from pathlib import Path
import resource
import sys
import time

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
from gf2n import Curve, GF2n, INF, Point
from target_fiber import KERNEL_4, projected_preimages, scalar_mul


def encode(p):
    return None if p == INF else [hex(p.x), hex(p.y)]


def decode(p):
    return INF if p is None else Point(int(p[0], 16), int(p[1], 16))


def graph(n, l, modulus, target, subgroup_order, cofactor):
    """Factor graph with no S6 monomial expansion; exact for all branches."""
    curve = Curve(GF2n(n, modulus), 1)
    if cofactor == 4:
        torsion = KERNEL_4
        lifts = projected_preimages(curve, target, subgroup_order)
    elif n == 31 and cofactor == 1492:
        # The [1492] kernel combines rational 4-torsion and 373-torsion.
        odd = next((q for x in range(2, 100) if (p := curve.lift_x(x)) is not None
                    if (q := scalar_mul(curve, p, 4 * subgroup_order)) != INF), INF)
        if odd == INF or scalar_mul(curve, odd, 373) != INF:
            raise ValueError("could not construct 373-torsion")
        odd_kernel = [scalar_mul(curve, odd, i) for i in range(373)]
        torsion = tuple(curve.add(p, k) for p in odd_kernel for k in KERNEL_4)
        first = scalar_mul(curve, target, pow(cofactor, -1, subgroup_order))
        lifts = tuple(curve.add(first, k) for k in torsion)
        if len(set(lifts)) != cofactor or scalar_mul(curve, first, cofactor) != target \
                or scalar_mul(curve, odd, cofactor) != INF:
            raise ValueError("incomplete cofactor fiber")
    else:
        raise ValueError("unsupported cofactor fiber")
    branches = []
    for k, lifted in zip(torsion, lifts):
        start = time.monotonic()
        circuit = {
            "field": {"n": n, "modulus": str(modulus), "encoding": "polynomial basis"},
            "curve": "y^2+xy=x^3+1", "variables": {
                "original_points": [f"P{i}" for i in range(1, 6)],
                "intermediate_points": ["A", "B", "C"],
                "x_bounds": {f"P{i}": 1 << l for i in range(1, 6)}},
            "constraints": [
                ["FINITE", f"P{i}"] for i in range(1, 6)
            ] + [["ON_CURVE", f"P{i}"] for i in range(1, 6)] + [
                 ["ADD", "P1", "P2", "A"], ["ADD", "P3", "P4", "B"],
                 ["ADD", "A", "B", "C"], ["ADD", "C", "P5", encode(lifted)]],
            "kernel": encode(k), "original_target": encode(lifted),
            "projected_target": encode(target),
            "witness_check": f"[{cofactor}](P1+P2+P3+P4+P5)=R; exact signed group replay",
            "representation": "implicit exact group-law gates; no Boolean expansion"}
        payload = json.dumps(circuit, sort_keys=True, separators=(",", ":")).encode()
        branches.append({"kernel": encode(k), "lift": encode(lifted),
                         "circuit_sha256": hashlib.sha256(payload).hexdigest(),
                         "bytes": len(payload), "group_add_gates": 4,
                         "curve_constraints": 5, "finite_constraints": 5,
                         "x_bound_bits": 5 * l,
                         "point_coordinate_bits_upper_bound": 16 * n,
                         "encoding_seconds": time.monotonic() - start,
                         "peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                         "solver_status": "not-run", "circuit": circuit})
    return branches


def exhaustive_control():
    """Enumerate small original-point tuples and compare all four fibers."""
    curve = Curve(GF2n(13), 1)
    r = 2003  # E(F_2^13) = 4*r
    points = sorted({q for x in range(8) if (p := curve.lift_x(x)) is not None
                     for q in (p, curve.neg(p))}, key=lambda p: (p.x, p.y))
    from itertools import product
    target = next((q for p in points if (q := scalar_mul(curve, p, 4)) != INF), INF)
    if target == INF:
        raise ValueError("small control has no subgroup target")
    fiber = set(projected_preimages(curve, target, r))
    checked = matches = 0
    for chosen in product(points, repeat=5):
        total = curve.sum(chosen)
        in_fiber = total in fiber
        projected = scalar_mul(curve, total, 4) == target
        if in_fiber != projected:
            raise ValueError("fiber and projected sum disagree")
        checked += 1
        matches += projected
    return {"n": 13, "l": 3, "original_signed_points": len(points),
            "ordered_five_tuples": checked, "matches": matches,
            "four_lift_equivalence": True}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    frozen = json.loads(args.manifest.read_text())
    base = frozen["base"]
    curve = Curve(GF2n(base["n"], base["modulus"]), 1)
    target = decode(frozen["streams"][0]["queries"][0]["target"])
    if scalar_mul(curve, target, base["r"]) != INF:
        raise ValueError("invalid subgroup target")
    start = time.monotonic()
    branches = graph(base["n"], base["l"], base["modulus"], target, base["r"], base["cofactor"])
    report = {"manifest_sha256": hashlib.sha256(args.manifest.read_bytes()).hexdigest(),
              "n": base["n"], "l": base["l"], "projected_target": encode(target),
              "cofactor": base["cofactor"], "branches": branches,
              "fiber_encoding_wall_seconds": time.monotonic() - start,
              "peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
              "limitations": ["No Boolean equations or algebraic roots generated",
                              "No solver was run; relation yield and solving degree unknown"]}
    if base["n"] == 31:
        report["exhaustive_small_control"] = exhaustive_control()
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"n": base["n"], "branches": len(branches),
                      "peak_rss_kib": report["peak_rss_kib"],
                      "seconds": report["fiber_encoding_wall_seconds"],
                      "solver_status": "not-run"}))


if __name__ == "__main__":
    main()

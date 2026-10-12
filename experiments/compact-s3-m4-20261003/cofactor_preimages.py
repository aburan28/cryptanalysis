#!/usr/bin/env python3
"""Enumerate every raw target that maps to one public subgroup target."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import resource
import time
from pathlib import Path

from run_probe import HERE, curve_record, curves, field, sha


def cyclic_subgroup(curve, point, bound):
    result = []
    current = None
    while True:
        result.append(current)
        current = curve.add(current, point)
        if current is None:
            return result
        assert len(result) < bound


def kernel_of_cofactor(curve, onb, r, h, seed):
    rng = random.Random(seed)
    kernel = {None}
    generator_points = []
    trials = 0
    while len(kernel) < h:
        trials += 1
        assert trials <= 1000, "cofactor kernel did not reach exact size"
        candidate = curve.pointFromX(onb.fromCoords(rng.getrandbits(onb.m)))
        if candidate is None:
            continue
        torsion = curve.mul(candidate, r)
        assert curve.mul(torsion, h) is None
        if torsion in kernel:
            continue
        cyclic = cyclic_subgroup(curve, torsion, h + 1)
        expanded = {curve.add(old, new) for old in kernel for new in cyclic}
        assert len(expanded) > len(kernel) and h % len(expanded) == 0
        kernel = expanded
        generator_points.append(torsion)
    assert len(kernel) == h
    return kernel, generator_points, trials


def enumerate_preimages(n, kind):
    manifest_path, candidate = curve_record(n)
    stage_path = HERE / "runs" / f"n{n}_{kind}_frozen.json"
    stage = json.loads(stage_path.read_text())
    assert stage["curve_id"] == candidate["curve"]["curve_id"]
    assert stage["workload_kind"] == kind
    onb = field.Onb(n)
    curve = curves.Curve(onb)
    r = int(candidate["curve"]["subgroup_order"])
    h = int(candidate["curve"]["cofactor"])
    assert math.gcd(r, h) == 1
    public = tuple(int(value) for value in stage["public_subgroup_target"])
    assert curve.onCurve(public) and curve.mul(public, r) is None
    began = time.perf_counter()
    kernel, generators, trials = kernel_of_cofactor(
        curve, onb, r, h, seed=130000 + n + (1000 if kind == "planted" else 0))
    raw_base = curve.mul(public, pow(h, -1, r))
    assert raw_base is not None and curve.mul(raw_base, h) == public
    stage_raw = tuple(int(value) for value in stage["raw_target"])
    assert curve.mul(stage_raw, h) == public
    if kind == "ordinary":
        assert raw_base == stage_raw
    raw_preimages = {curve.add(raw_base, torsion) for torsion in kernel}
    assert None not in raw_preimages and len(raw_preimages) == h
    assert all(curve.mul(point, h) == public for point in raw_preimages)
    assert stage_raw in raw_preimages
    points = sorted(raw_preimages,
                    key=lambda point: (onb.toCoords(point[0]),
                                       onb.toCoords(point[1])))
    xs = [onb.toCoords(point[0]) for point in points]
    assert len(set(xs)) == h
    width = (n + 7) // 8
    packed = b"".join(x.to_bytes(width, "little") for x in xs)
    return {
        "kind": "complete_raw_target_preimage_coset",
        "workload_kind": kind,
        "proposal_id": {53: "Q1306", 83: "Q1307"}[n],
        "candidate_id": None,
        "workload_id": stage["workload_id"],
        "curve_id": stage["curve_id"],
        "isogeny": "none",
        "n": n,
        "cofactor": h,
        "subgroup_order": str(r),
        "public_target": list(stage["public_subgroup_target"]),
        "kernel_size": len(kernel),
        "kernel_generator_points": [list(point) for point in generators],
        "kernel_generation_trials": trials,
        "raw_target_preimage_count": len(points),
        "raw_target_x_coordinates": xs,
        "raw_target_x_sha256": hashlib.sha256(packed).hexdigest(),
        "raw_target_x_encoding": f"sorted {width}-byte little-endian normal-basis x coordinates",
        "raw_target_points": [[str(value) for value in point] for point in points],
        "elapsed_seconds": time.perf_counter() - began,
        "peak_rss_raw": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "peak_rss_units": "bytes on Darwin, KiB on Linux",
        "curve_manifest_sha256": sha(manifest_path),
        "stage_receipt_sha256": sha(stage_path),
        "field_source_sha256": sha(Path(field.__file__)),
        "curve_source_sha256": sha(Path(curves.__file__)),
        "source_sha256": sha(Path(__file__)),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, choices=(53, 83), required=True)
    parser.add_argument("--kind", choices=("ordinary", "planted"),
                        default="ordinary")
    args = parser.parse_args()
    output = HERE / "runs" / f"n{args.n}_{args.kind}_raw_preimages.json"
    assert not output.exists()
    result = enumerate_preimages(args.n, args.kind)
    output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"n": args.n, "cofactor": result["cofactor"],
                      "preimages": result["raw_target_preimage_count"],
                      "trials": result["kernel_generation_trials"],
                      "elapsed_seconds": result["elapsed_seconds"],
                      "sha256": result["raw_target_x_sha256"]}))


if __name__ == "__main__":
    main()

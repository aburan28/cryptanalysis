#!/usr/bin/env sage -python
"""Exhaustively compare homogeneous S3 to rational group sums on two fields."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import resource
import sys
import time

from sage.all import EllipticCurve, GF


HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def peak_bytes():
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return value if sys.platform == "darwin" else value*1024


def coordinate(point):
    return None if point.is_zero() else point[0]


def homogeneous_s3(left, middle, right, b, one, zero):
    def projective(value):
        return (one, zero) if value is None else (value, one)
    x1, z1 = projective(left)
    x2, z2 = projective(middle)
    x3, z3 = projective(right)
    pair = x1*x2*z3 + x2*x3*z1 + x3*x1*z2
    product_z = z1*z2*z3
    return pair*pair + x1*x2*x3*product_z + b*product_z*product_z


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-info", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        parser.error("refusing to overwrite exhaustive receipt")
    started = time.perf_counter()
    runtime = json.loads(args.runtime_info.read_text())
    config = json.loads((HERE / "CONFIG.json").read_text())
    if runtime.get("status") != "verified":
        raise ValueError("checked Sage runtime did not verify")
    results = []
    for degree in config["small_field_exhaustive_degrees"]:
        k = GF(2**degree, "t")
        one, zero = k.one(), k.zero()
        for tag, b in (("one", one), ("generator", k.gen())):
            curve = EllipticCurve(k, [one, zero, zero, zero, b])
            grouped = {None: [curve(0)]}
            for point in curve.points():
                if not point.is_zero():
                    grouped.setdefault(point[0], []).append(point)
            if any(len(points) > 2 for points in grouped.values()):
                raise ArithmeticError("an x class has more than two points")
            classes = list(grouped)
            pair_sums = {}
            for left in classes:
                for middle in classes:
                    pair_sums[left, middle] = {
                        coordinate(p+q) for p in grouped[left]
                        for q in grouped[middle]}
            triples = accepted = infinity_cases = zero_cases = 0
            for left in classes:
                for middle in classes:
                    for right in classes:
                        actual = homogeneous_s3(
                            left, middle, right, b, one, zero) == zero
                        expected = right in pair_sums[left, middle]
                        if actual != expected:
                            raise ArithmeticError(
                                "projective S3 disagrees with group law: "
                                + str((degree, tag, left, middle, right)))
                        triples += 1
                        accepted += int(actual)
                        infinity_cases += int(actual and None in
                                              (left, middle, right))
                        zero_cases += int(actual and zero in
                                          (left, middle, right))
            if infinity_cases == 0 or zero_cases == 0:
                raise ArithmeticError("exceptional classes were not exercised")
            results.append({"degree": degree, "b": tag,
                            "group_order": len(curve.points()),
                            "x_classes_including_infinity": len(classes),
                            "ordered_class_triples": triples,
                            "accepted_triples": accepted,
                            "accepted_with_infinity": infinity_cases,
                            "accepted_with_x_zero": zero_cases})
    receipt = {"schema": "ecc2k130-263-projective-s3-small-field-v1",
               "status": "PASS_EXHAUSTIVE_GROUP_LAW_EQUIVALENCE",
               "config_sha256": sha(HERE / "CONFIG.json"),
               "source_sha256": sha(Path(__file__)),
               "sage_runtime_info_sha256": sha(args.runtime_info),
               "results": results,
               "wall_seconds": time.perf_counter()-started,
               "peak_rss_bytes": peak_bytes()}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(receipt, indent=2, sort_keys=True)+"\n")
    print(json.dumps({"status": receipt["status"],
                      "triples": sum(row["ordered_class_triples"]
                                     for row in results),
                      "wall_seconds": receipt["wall_seconds"]}), flush=True)


if __name__ == "__main__":
    main()

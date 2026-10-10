#!/usr/bin/env sage -python
"""Independently replay Q1420 lift transport and native W24 m6 controls."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import time

from sage.all import EllipticCurve, GF, PolynomialRing, ZZ

import field as ref


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-info", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        parser.error("refusing to overwrite replay receipt")
    started = time.perf_counter()
    runtime = ref.read(args.runtime_info)
    config = ref.read(ref.HERE / "CONFIG.json")
    lifts = ref.read(ref.HERE / "runs/R1/lifts.json")
    geometry = ref.read(ref.HERE / "runs/R1/geometry_controls.json")
    primary = ref.read(ref.INPUT / "primary_workload.json")
    controls = ref.read(ref.INPUT / "point_controls.json")
    route = ref.read(ref.ROUTE)
    if runtime.get("status") != "verified":
        raise ValueError("checked Sage runtime did not verify")
    if (ref.sha(ref.ROUTE) != config["route_manifest_sha256"]
            or ref.sha(ref.INPUT / "primary_workload.json")
            != config["primary_workload_sha256"]
            or ref.sha(ref.INPUT / "base_selection.json")
            != config["base_selection_sha256"]
            or lifts["config_sha256"] != ref.sha(ref.HERE / "CONFIG.json")
            or geometry["config_sha256"] != ref.sha(ref.HERE / "CONFIG.json")
            or geometry["point_controls_sha256"]
            != ref.sha(ref.INPUT / "point_controls.json")
            or primary["workload_id"] != config["primary_workload_id"]):
        raise ValueError("input or control identity changed")

    ring = PolynomialRing(GF(2), "t")
    t = ring.gen()
    k = GF(2**131, "t", modulus=t**131+t**13+t**2+t+1)
    powers = [k.gen()**index for index in range(131)]

    def decode(word):
        word = int(word)
        if word < 0 or word > ref.MASK:
            raise ValueError("field word outside GF(2^131)")
        return sum((powers[index] for index in range(131)
                    if word & (1 << index)), k.zero())

    def encode(value):
        return sum(int(bit) << index for index, bit in
                   enumerate(value.polynomial().list()))

    source = EllipticCurve(k, [1, 0, 0, 0, 1])
    codomain_coeffs = route["curve_nodes"]["target"][
        "coefficients_a1_a2_a3_a4_a6"]
    codomain = EllipticCurve(k, [decode(value) for value in codomain_coeffs])
    poly = PolynomialRing(k, "X")
    forward = source.isogeny(poly([decode(value) for value in route[
        "isogeny"]["forward_map"]["kernel_polynomial_coefficients"]]),
        check=True)
    if [encode(value) for value in forward.codomain().ainvs()] != codomain_coeffs:
        raise ArithmeticError("independent map codomain replay failed")
    a = int(codomain_coeffs[3])
    alpha, b = ref.coefficients("descendant_native")
    normalized = EllipticCurve(k, [1, 0, 0, 0, decode(b)])
    if b != int(codomain_coeffs[4]) ^ ref.square(a):
        raise ArithmeticError("normalization coefficient changed")
    order = ZZ(primary["subgroup_order"])
    mapped_sets = {}
    for policy, curve in (("source", source), ("descendant_native", codomain)):
        archived = lifts[policy]
        public = primary["targets"][0]["source" if policy == "source"
                                             else "descendant"]
        if archived["public_query"] != public:
            raise ArithmeticError("lift query differs from primary workload")
        query = curve([decode(word) for word in public])
        torsion = curve([decode(word) for word in archived["torsion"]])
        if (order*query != curve(0) or 4*torsion != curve(0)
                or 2*torsion == curve(0)):
            raise ArithmeticError("subgroup or order-four torsion failed")
        rows = archived["raw_target_lifts"]
        points = [curve([decode(word) for word in pair]) for pair in rows]
        if (len(rows) != 4 or len({pair[0] for pair in rows}) != 4
                or any(point != query+j*torsion or 4*point != 4*query
                       for j, point in enumerate(points))):
            raise ArithmeticError("four lifts do not match group law")
        mapped_sets[policy] = points
    if (forward(mapped_sets["source"][0]) != mapped_sets[
            "descendant_native"][0]
            or {tuple((encode(forward(point)[0]), encode(forward(point)[1])))
                for point in mapped_sets["source"]}
            != {tuple(row) for row in lifts["descendant_native"][
                "raw_target_lifts"]}):
        raise ArithmeticError("four-lift transport failed")

    for policy, curve, expected_alpha, expected_b in (
            ("source", source, 1, 1),
            ("descendant_native", normalized, alpha, b)):
        entry = geometry[policy]
        if (entry["alpha"] != expected_alpha
                or entry["normalized_b"] != expected_b
                or entry["codomain_y_shift_A"]
                != (a if policy == "descendant_native" else 0)):
            raise ArithmeticError("leaf curve constants changed")
        selected = sorted(controls[policy], key=lambda row: row["mask"])[:6]
        rows = entry["leaves"]
        if [row["mask"] for row in rows] != [row["mask"] for row in selected]:
            raise ArithmeticError("positive control masks changed")
        points = []
        for row, stored in zip(rows, selected):
            x, z, w = ref.leaf(row["mask"], expected_alpha)
            if (row["w"] != w or row["z"] != z or row["raw_point"][0] != x
                    or row["u"] != ref.halftrace(w)
                    or ref.trace(ref.multiply(expected_alpha, z)) != 0
                    or ref.multiply(row["u"], x ^ expected_alpha)
                    != expected_alpha):
                raise ArithmeticError("independent native leaf replay failed")
            point = curve([decode(word) for word in row["raw_point"]])
            projected = 4*point
            if policy == "descendant_native":
                projected = codomain([projected[0], projected[1]+decode(a)])
            expected_curve = source if policy == "source" else codomain
            archived = expected_curve([decode(word) for word in stored[policy]])
            if projected not in (archived, -archived):
                raise ArithmeticError("leaf cofactor projection changed")
            points.append(point)
        pairs = [points[j]+points[j+1] for j in (0, 2, 4)]
        middle = pairs[0]+pairs[1]
        target = middle+pairs[2]
        if any(point.is_zero() or point[0] == 0 for point in
               pairs+[middle, target]):
            raise ArithmeticError("control is outside finite S3 chart")
        xs = [encode(point[0]) for point in pairs+[middle, target]]
        if (entry["intermediate_x"] != xs[:4]
                or entry["target_x"] != xs[4]
                or entry["target_raw_point_normalized"] !=
                [encode(target[0]), encode(target[1])]):
            raise ArithmeticError("balanced-tree control coordinates changed")
        pairs_x = [(rows[j]["raw_point"][0], rows[j+1]["raw_point"][0],
                    xs[j//2]) for j in (0, 2, 4)]
        pairs_x.extend(((xs[0], xs[1], xs[3]), (xs[3], xs[2], xs[4])))
        if any(ref.s3(left, middle_x, right, expected_b) != 0
               for left, middle_x, right in pairs_x):
            raise ArithmeticError("independent S3 evaluation failed")
    result = {
        "schema": "ecc2k130-263-native-w24-independent-geometry-replay-v1",
        "status": "PASS_TWO_CURVES_FOUR_LIFTS_AND_M6_CONTROLS",
        "primary_workload_id": primary["workload_id"],
        "source_lift_count": 4,
        "descendant_lift_count": 4,
        "positive_control_count_each": 6,
        "config_sha256": ref.sha(ref.HERE / "CONFIG.json"),
        "producer_source_sha256": ref.sha(ref.HERE / "produce_geometry.py"),
        "verifier_source_sha256": ref.sha(Path(__file__)),
        "reference_field_source_sha256": ref.sha(ref.HERE / "field.py"),
        "lifts_sha256": ref.sha(ref.HERE / "runs/R1/lifts.json"),
        "geometry_controls_sha256": ref.sha(
            ref.HERE / "runs/R1/geometry_controls.json"),
        "sage_runtime_info_sha256": ref.sha(args.runtime_info),
        "wall_seconds": time.perf_counter()-started,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True)+"\n")
    print(json.dumps({"status": result["status"],
                      "wall_seconds": result["wall_seconds"]}), flush=True)


if __name__ == "__main__":
    main()

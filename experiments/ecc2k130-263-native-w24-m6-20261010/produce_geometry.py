#!/usr/bin/env sage -python
"""Build Q1420 four-lift and positive m6 controls on both exact curves."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import resource
import sys
import time

from sage.all import EllipticCurve, GF, PolynomialRing, ZZ
from sage.version import version as sage_version


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
INPUT = ROOT / "experiments/ecc2k130-263-equal-w24-workload-20261005"
ROUTE = ROOT / "experiments/koblitz-polynomial-w-pair-20260925/ecc2k130_degree263_route_manifest.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def peak_bytes():
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return value if sys.platform == "darwin" else value * 1024


def save_new(path, record):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(record, stream, indent=2, sort_keys=True)
        stream.write("\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-info", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    outputs = [args.out_dir / name for name in
               ("lifts.json", "geometry_controls.json", "producer_receipt.json")]
    if any(path.exists() for path in outputs):
        parser.error("refusing to overwrite geometry artifacts")
    started = time.perf_counter()
    config = read(HERE / "CONFIG.json")
    primary = read(INPUT / "primary_workload.json")
    base = read(INPUT / "base_selection.json")
    controls = read(INPUT / "point_controls.json")
    route = read(ROUTE)
    runtime = read(args.runtime_info)
    if runtime.get("status") != "verified":
        raise ValueError("checked Sage runtime did not verify")
    if (sha(ROUTE) != config["route_manifest_sha256"]
            or sha(INPUT / "primary_workload.json") != config["primary_workload_sha256"]
            or sha(INPUT / "base_selection.json") != config["base_selection_sha256"]
            or primary["workload_id"] != config["primary_workload_id"]
            or route["route_id"] != config["route_id"]):
        raise ValueError("frozen source/input identity changed")
    for policy in ("source", "descendant_native"):
        if (base[policy]["selected_mask_stream_sha256"]
                != config["selected_mask_stream_sha256"][policy]
                or base[policy]["selected_usable_points_B"]
                != config["selected_usable_points_B_each"]):
            raise ValueError("factor-base identity changed")

    binary = PolynomialRing(GF(2), "t")
    t = binary.gen()
    field = GF(2**131, "t", modulus=t**131+t**13+t**2+t+1)
    powers = [field.gen()**index for index in range(131)]

    def decode(value):
        value = int(value)
        return sum((powers[index] for index in range(value.bit_length())
                    if value & (1 << index)), field.zero())

    def encode(value):
        return sum(int(bit) << index for index, bit in
                   enumerate(value.polynomial().list()))

    def words(point):
        if point.is_zero():
            raise ValueError("finite point required")
        return [encode(point[0]), encode(point[1])]

    def halftrace(value):
        total = field.zero()
        for _ in range(66):
            total += value
            value = value**4
        return total

    source = EllipticCurve(field, [1, 0, 0, 0, 1])
    polynomial = PolynomialRing(field, "X")
    forward_poly = polynomial([decode(value) for value in route["isogeny"][
        "forward_map"]["kernel_polynomial_coefficients"]])
    forward = source.isogeny(forward_poly, check=True)
    codomain = forward.codomain()
    target_record = route["curve_nodes"]["target"]
    if [encode(coefficient) for coefficient in codomain.ainvs()] != target_record[
            "coefficients_a1_a2_a3_a4_a6"]:
        raise ArithmeticError("isogeny codomain changed")
    a = decode(target_record["coefficients_a1_a2_a3_a4_a6"][3])
    b = decode(target_record["coefficients_a1_a2_a3_a4_a6"][4]) + a*a
    alpha = b ** (2**129)
    if alpha**4 != b:
        raise ArithmeticError("wrong fourth root")
    normalized = EllipticCurve(field, [1, 0, 0, 0, b])
    order = ZZ(primary["subgroup_order"])
    source_query = source([decode(value) for value in primary["targets"][0]["source"]])
    desc_query = codomain([decode(value) for value in primary["targets"][0]["descendant"]])
    if (order*source_query != source(0) or order*desc_query != codomain(0)
            or forward(source_query) != desc_query):
        raise ArithmeticError("public subgroup point or route failed")
    source_torsion = source([field.one(), field.one()])
    desc_torsion = codomain([alpha, alpha*alpha+a])
    if (2*source_torsion != source([field.zero(), field.one()])
            or 4*source_torsion != source(0)
            or 2*desc_torsion != codomain([field.zero(), alpha*alpha+a])
            or 4*desc_torsion != codomain(0)):
        raise ArithmeticError("order-four torsion check failed")
    map_setup_seconds = time.perf_counter() - started

    lift_sets = {}
    for name, curve, query, torsion in (
            ("source", source, source_query, source_torsion),
            ("descendant_native", codomain, desc_query, desc_torsion)):
        points = [query+j*torsion for j in range(4)]
        if (len(set(points)) != 4
                or len({encode(point[0]) for point in points}) != 4
                or any(4*point != 4*query for point in points)):
            raise ArithmeticError("four target x coordinates are not distinct")
        lift_sets[name] = {"public_query": words(query),
                           "torsion": words(torsion),
                           "raw_target_lifts": [words(point) for point in points]}
    mapped = {tuple(words(forward(source([decode(v) for v in point]))))
              for point in lift_sets["source"]["raw_target_lifts"]}
    desc_set = {tuple(point) for point in lift_sets["descendant_native"][
        "raw_target_lifts"]}
    if mapped != desc_set:
        raise ArithmeticError("degree-263 map changed the four-lift set")
    lift_record = {
        "schema": "ecc2k130-263-native-w24-four-lift-v1",
        "status": "PASS_EXACT_FOUR_LIFTS_AND_TRANSPORT",
        "config_sha256": sha(HERE / "CONFIG.json"),
        "primary_workload_id": primary["workload_id"],
        "primary_workload_sha256": sha(INPUT / "primary_workload.json"),
        "route_manifest_sha256": sha(ROUTE),
        "subgroup_order": str(order),
        "source_curve_id": config["source_curve_id"],
        "descendant_curve_id": config["descendant_curve_id"],
        "source": lift_sets["source"],
        "descendant_native": lift_sets["descendant_native"],
        "transported_source_lift_set_matches_descendant": True,
    }

    basis = [field.gen()**j + (field.gen()**j).trace()
             for j in range(1, 25)]
    if any(int(value.trace()) != 0 for value in basis):
        raise ArithmeticError("W24 basis is not trace zero")
    geometry = {}
    for policy, curve, scale, coefficient in (
            ("source", source, field.one(), field.one()),
            ("descendant_native", normalized, alpha, b)):
        rows = sorted(controls[policy], key=lambda row: row["mask"])[
            :config["control_masks_per_policy"]]
        if len(rows) != 6 or len({row["mask"] for row in rows}) != 6:
            raise ArithmeticError("six distinct controls required")
        raw_points = []
        leaves = []
        for row in rows:
            mask = int(row["mask"])
            if mask > config[policy + "_last_selected_mask"]:
                raise ArithmeticError("control outside selected base")
            w = sum((basis[j] for j in range(24) if mask & (1 << j)),
                    field.zero())
            u = halftrace(w)
            z = 1/w
            x = scale*(1+1/u)
            if (u*u+u != w or int((scale*z).trace()) != 0
                    or u*(x+scale) != scale
                    or int((x+coefficient/(x*x)).trace()) != 0):
                raise ArithmeticError("native leaf identity failed")
            y = x*halftrace(x+coefficient/(x*x))
            point = curve([x, y])
            projected = 4*point
            if policy == "descendant_native":
                projected = codomain([projected[0], projected[1]+a])
            archived = (source if policy == "source" else codomain)(
                [decode(value) for value in row[policy]])
            if projected not in (archived, -archived):
                raise ArithmeticError("raw control does not project to base")
            raw_points.append(point)
            leaves.append({"mask": mask, "w": encode(w), "u": encode(u),
                           "z": encode(z), "raw_point": words(point),
                           "projected_matches_stored_sign_class": True})
        pairs = [raw_points[j]+raw_points[j+1] for j in (0, 2, 4)]
        combined = pairs[0]+pairs[1]
        target = combined+pairs[2]
        if any(point.is_zero() or point[0] == 0 for point in
               pairs+[combined, target]):
            raise ArithmeticError("positive control left finite S3 chart")
        xs = [encode(point[0]) for point in pairs+[combined, target]]
        geometry[policy] = {
            "curve_id": config["source_curve_id"] if policy == "source"
                        else config["descendant_curve_id"],
            "normalized_b": encode(coefficient), "alpha": encode(scale),
            "codomain_y_shift_A": encode(a) if policy == "descendant_native" else 0,
            "leaves": leaves,
            "intermediate_x": xs[:4], "target_x": xs[4],
            "target_raw_point_normalized": words(target),
            "all_s3_links_zero": True,
        }
    geometry_record = {
        "schema": "ecc2k130-263-native-w24-m6-positive-controls-v1",
        "status": "PASS_TWO_EXACT_M6_GEOMETRY_CONTROLS",
        "config_sha256": sha(HERE / "CONFIG.json"),
        "base_selection_sha256": sha(INPUT / "base_selection.json"),
        "point_controls_sha256": sha(INPUT / "point_controls.json"),
        "source": geometry["source"],
        "descendant_native": geometry["descendant_native"],
    }
    receipt = {
        "schema": "ecc2k130-263-native-w24-geometry-producer-v1",
        "status": "PASS_GEOMETRY_CONSTRUCTION_PENDING_INDEPENDENT_REPLAY",
        "candidate_id": None,
        "primary_workload_id": primary["workload_id"],
        "config_sha256": sha(HERE / "CONFIG.json"),
        "producer_sha256": sha(Path(__file__)),
        "sage_runtime_info_sha256": sha(args.runtime_info),
        "sage_version": sage_version,
        "route_manifest_sha256": sha(ROUTE),
        "map_setup_wall_seconds": map_setup_seconds,
        "total_wall_seconds": time.perf_counter()-started,
        "peak_rss_bytes": peak_bytes(),
        "natural_relation_yield": None,
        "verified_relation_rank": None,
        "online_wall_time": None,
        "rho_ratio": None,
    }
    for path, value in zip(outputs, (lift_record, geometry_record, receipt)):
        save_new(path, value)
    print(json.dumps({"status": receipt["status"],
                      "wall_seconds": receipt["total_wall_seconds"],
                      "peak_rss_bytes": receipt["peak_rss_bytes"]}), flush=True)


if __name__ == "__main__":
    main()

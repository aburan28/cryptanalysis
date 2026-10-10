#!/usr/bin/env sage -python
"""Check six archived distinct W24 leaves and a finite projective-S3 chain."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
import time

from sage.all import EllipticCurve, GF, PolynomialRing


HERE = Path(__file__).resolve().parent
NATIVE = HERE.parent / "ecc2k130-263-native-w24-m6-20261010"
PROJECTIVE = HERE.parent / "ecc2k130-263-projective-s3-20261010"
WORKLOAD = HERE.parent / "ecc2k130-263-equal-w24-workload-20261005"
sys.path.insert(0, str(PROJECTIVE))
import binary_group as group  # noqa: E402


ref = group.f


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def checked_sources(config):
    pins = {
        NATIVE / "runs/R1/geometry_controls.json": "geometry_controls_sha256",
        NATIVE / "runs/R1/verification.json": "native_verification_sha256",
        WORKLOAD / "primary_workload.json": "primary_workload_sha256",
        NATIVE / "field.py": "field_source_sha256",
        PROJECTIVE / "binary_group.py": "binary_group_source_sha256",
    }
    if any(sha(path) != config[key] for path, key in pins.items()):
        raise ValueError("frozen geometry or source hash changed")
    geometry = ref.read(NATIVE / "runs/R1/geometry_controls.json")
    verification = ref.read(NATIVE / "runs/R1/verification.json")
    workload = ref.read(WORKLOAD / "primary_workload.json")
    if (geometry["status"] != "PASS_TWO_EXACT_M6_GEOMETRY_CONTROLS"
            or verification["status"]
            != "PASS_TWO_CURVES_FOUR_LIFTS_AND_M6_CONTROLS"
            or verification["geometry_controls_sha256"]
            != config["geometry_controls_sha256"]
            or config["geometry_leaf_indices"] != list(range(6))
            or config["signs"] != [0] * 6
            or workload["workload_id"] != "eee7f6ee5f6b"
            or workload["source_curve_id"] != config["source_curve_id"]
            or workload["descendant_curve_id"] != config["descendant_curve_id"]
            or config["subgroup_projection_degree"] != 4):
        raise ValueError("frozen control selection or parent proof changed")
    return geometry, workload


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-info", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        parser.error("refusing to overwrite checked witness")
    started = time.perf_counter()
    config = ref.read(HERE / "CONFIG.json")
    geometry, workload = checked_sources(config)
    runtime = ref.read(args.runtime_info)
    if runtime.get("status") != "verified":
        raise ValueError("checked Sage runtime receipt is not verified")
    ring = PolynomialRing(GF(2), "t")
    t = ring.gen()
    field = GF(2**131, "t", modulus=t**131+t**13+t**2+t+1)
    powers = [field.gen()**index for index in range(ref.DEGREE)]

    def decode(word):
        word = int(word)
        return sum((powers[index] for index in range(word.bit_length())
                    if word & (1 << index)), field.zero())

    def encode(value):
        return sum(int(bit) << index for index, bit in
                   enumerate(value.polynomial().list()))

    def encode_point(point):
        return None if point.is_zero() else [encode(point[0]), encode(point[1])]

    controls = {}
    for policy in config["policies"]:
        alpha, b = ref.coefficients(policy)
        curve = EllipticCurve(field, [1, 0, 0, 0, decode(b)])
        rows = [geometry[policy]["leaves"][index]
                for index in config["geometry_leaf_indices"]]
        masks = [row["mask"] for row in rows]
        if len(set(masks)) != 6 or masks != sorted(masks):
            raise ArithmeticError("selected masks are not distinct and sorted")
        leaves = []
        for mask, row in zip(masks, rows):
            x, z, w = ref.leaf(mask, alpha)
            point = curve([decode(value) for value in row["raw_point"]])
            if (x != row["raw_point"][0] or z != row["z"]
                    or w != row["w"] or not group.on_curve(
                        tuple(row["raw_point"]), b)):
                raise ArithmeticError("archived leaf differs from exact base")
            leaves.append(point)
        if len({point[0] for point in leaves}) != 6:
            raise ArithmeticError("raw leaf x coordinates collide")
        fourfold = [4 * point for point in leaves]
        order = int(workload["subgroup_order"])
        if (any(point.is_zero() or not (order * point).is_zero()
                for point in fourfold)
                or len({tuple(encode_point(point)) for point in fourfold}) != 6):
            raise ArithmeticError("fourfold subgroup points are not usable")
        sage_pairs = [leaves[index] + leaves[index + 1]
                      for index in (0, 2, 4)]
        sage_combined = sage_pairs[0] + sage_pairs[1]
        sage_target = sage_combined + sage_pairs[2]
        sage_chain = sage_pairs + [sage_combined, sage_target]
        if (any(point.is_zero() for point in sage_chain)
                or encode_point(sage_target)
                != config["expected_targets"][policy]
                or not (order * (4 * sage_target)).is_zero()):
            raise ArithmeticError("control chain is not finite or target changed")
        pure_leaves = [tuple(row["raw_point"]) for row in rows]
        pure_pairs = [group.add(pure_leaves[index], pure_leaves[index + 1], b)
                      for index in (0, 2, 4)]
        pure_combined = group.add(pure_pairs[0], pure_pairs[1], b)
        pure_target = group.add(pure_combined, pure_pairs[2], b)
        pure_chain = pure_pairs + [pure_combined, pure_target]
        if [list(point) for point in pure_chain] != [
                encode_point(point) for point in sage_chain]:
            raise ArithmeticError("Sage and polynomial-basis sums disagree")
        projected = [group.projective_x(point) for point in pure_chain]
        links = [
            (group.projective_x(pure_leaves[0]),
             group.projective_x(pure_leaves[1]), projected[0]),
            (group.projective_x(pure_leaves[2]),
             group.projective_x(pure_leaves[3]), projected[1]),
            (group.projective_x(pure_leaves[4]),
             group.projective_x(pure_leaves[5]), projected[2]),
            (projected[0], projected[1], projected[3]),
            (projected[3], projected[2], projected[4]),
        ]
        if any(group.s3_projective(*link, b) != 0 for link in links):
            raise ArithmeticError("projective S3 link failed")
        controls[policy] = {
            "curve_id": config["source_curve_id"] if policy == "source"
                        else config["descendant_curve_id"],
            "normalized_b": b,
            "alpha": alpha,
            "leaf_masks": masks,
            "leaves": [{"mask": mask,
                        "raw_point_normalized": list(row["raw_point"]),
                        "z": row["z"]}
                       for mask, row in zip(masks, rows)],
            "intermediates": [{"x": x, "finite": bool(z)}
                              for x, z in projected[:4]],
            "target_x": projected[4][0],
            "target_point_normalized": encode_point(sage_target),
            "fourfold_subgroup_points": [encode_point(point)
                                         for point in fourfold],
            "all_six_masks_distinct": True,
            "all_intermediates_finite": True,
            "all_five_projective_links_zero": True,
            "sage_binary_group_agree": True,
            "fourfold_points_distinct_in_subgroup": True,
        }
    result = {
        "schema": "ecc2k130-263-distinct-s3-witness-v1",
        "status": "PASS_TWO_FINITE_SIX_DISTINCT_CONTROLS",
        "candidate_id": None,
        "config_sha256": sha(HERE / "CONFIG.json"),
        "geometry_controls_sha256": config["geometry_controls_sha256"],
        "native_verification_sha256": config["native_verification_sha256"],
        "sage_runtime_info_sha256": sha(args.runtime_info),
        "source_sha256": sha(Path(__file__)),
        "binary_group_source_sha256": config["binary_group_source_sha256"],
        "policies": controls,
        "wall_seconds": time.perf_counter() - started,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": result["status"],
                      "wall_seconds": result["wall_seconds"]}), flush=True)


if __name__ == "__main__":
    main()

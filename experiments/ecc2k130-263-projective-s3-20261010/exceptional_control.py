#!/usr/bin/env sage -python
"""Produce a checked n131 W24 cancellation witness for each curve model."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import time

from sage.all import EllipticCurve, GF, PolynomialRing

import binary_group as group


HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "ecc2k130-263-native-w24-m6-20261010"
ref = group.f


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-info", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        parser.error("refusing to overwrite exceptional control")
    started = time.perf_counter()
    config = json.loads((HERE / "CONFIG.json").read_text())
    parent_verification = ref.read(PARENT / "runs/R1/verification.json")
    parent = ref.read(PARENT / "runs/R1/geometry_controls.json")
    runtime = ref.read(args.runtime_info)
    if (runtime.get("status") != "verified"
            or parent_verification["status"]
            != "PASS_TWO_CURVES_FOUR_LIFTS_AND_M6_CONTROLS"
            or parent_verification["geometry_controls_sha256"]
            != sha(PARENT / "runs/R1/geometry_controls.json")
            or sha(PARENT / "runs/R1/verification.json")
            != config["parent_verification_sha256"]):
        raise ValueError("parent control chain or runtime changed")
    ring = PolynomialRing(GF(2), "t")
    t = ring.gen()
    k = GF(2**131, "t", modulus=t**131+t**13+t**2+t+1)
    powers = [k.gen()**index for index in range(131)]

    def decode(word):
        word = int(word)
        return sum((powers[index] for index in range(word.bit_length())
                    if word & (1 << index)), k.zero())

    def encode(value):
        return sum(int(bit) << index for index, bit in
                   enumerate(value.polynomial().list()))

    def encode_point(point):
        return None if point.is_zero() else [encode(point[0]), encode(point[1])]

    controls = {}
    for policy in ("source", "descendant_native"):
        alpha, b = ref.coefficients(policy)
        curve = EllipticCurve(k, [1, 0, 0, 0, decode(b)])
        rows = parent[policy]["leaves"]
        if len(rows) < 5:
            raise ValueError("parent has too few W24 controls")
        first = curve([decode(value) for value in rows[0]["raw_point"]])
        leaves = [first, -first]
        leaves.extend(curve([decode(value) for value in row["raw_point"]])
                      for row in rows[1:5])
        masks = [rows[0]["mask"], rows[0]["mask"]]
        masks.extend(row["mask"] for row in rows[1:5])
        witnesses = [rows[0], rows[0]] + rows[1:5]
        if (masks != sorted(masks) or leaves[0]+leaves[1] != curve(0)):
            raise ArithmeticError("first pair does not cancel in mask order")
        pairs = [leaves[j]+leaves[j+1] for j in (0, 2, 4)]
        combined = pairs[0]+pairs[1]
        target = combined+pairs[2]
        if (not pairs[0].is_zero() or any(point.is_zero() for point in
                                         pairs[1:]+[combined, target])):
            raise ArithmeticError("exceptional control has wrong chart")
        pure = [tuple(encode_point(point)) for point in leaves]
        pure_pairs = [group.add(pure[j], pure[j+1], b)
                      for j in (0, 2, 4)]
        pure_combined = group.add(pure_pairs[0], pure_pairs[1], b)
        pure_target = group.add(pure_combined, pure_pairs[2], b)
        sage_chain = [encode_point(point) for point in
                      pairs+[combined, target]]
        pure_chain = [list(point) if point is not None else None for point in
                      pure_pairs+[pure_combined, pure_target]]
        if sage_chain != pure_chain:
            raise ArithmeticError("independent binary group law disagrees")
        projective = [group.projective_x(point) for point in
                      pure_pairs+[pure_combined, pure_target]]
        links = [
            (group.projective_x(pure[0]), group.projective_x(pure[1]),
             projective[0]),
            (group.projective_x(pure[2]), group.projective_x(pure[3]),
             projective[1]),
            (group.projective_x(pure[4]), group.projective_x(pure[5]),
             projective[2]),
            (projective[0], projective[1], projective[3]),
            (projective[3], projective[2], projective[4]),
        ]
        if any(group.s3_projective(*link, b) != 0 for link in links):
            raise ArithmeticError("projective S3 link failed")
        controls[policy] = {
            "curve_id": config["source_curve_id"] if policy == "source"
                        else config["descendant_curve_id"],
            "normalized_b": b,
            "alpha": alpha,
            "leaf_masks": masks,
            "leaves": [{"mask": mask, "raw_point_normalized":
                        encode_point(point), "z": row["z"]}
                       for mask, point, row in zip(masks, leaves, witnesses)],
            "intermediates": [{"x": x, "finite": bool(z)}
                              for x, z in projective[:4]],
            "target_x": projective[4][0],
            "target_point_normalized": sage_chain[4],
            "first_pair_is_infinity": True,
            "all_links_zero": True,
            "independent_group_law_matches_sage": True,
        }
    receipt = {
        "schema": "ecc2k130-263-projective-s3-exceptional-control-v1",
        "status": "PASS_TWO_N131_CANCELLATION_GROUP_CONTROLS",
        "config_sha256": sha(HERE / "CONFIG.json"),
        "parent_geometry_sha256": sha(PARENT / "runs/R1/geometry_controls.json"),
        "parent_verification_sha256": sha(PARENT / "runs/R1/verification.json"),
        "sage_runtime_info_sha256": sha(args.runtime_info),
        "source_sha256": sha(Path(__file__)),
        "binary_group_source_sha256": sha(HERE / "binary_group.py"),
        "policies": controls,
        "wall_seconds": time.perf_counter()-started,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(receipt, indent=2, sort_keys=True)+"\n")
    print(json.dumps({"status": receipt["status"],
                      "wall_seconds": receipt["wall_seconds"]}), flush=True)


if __name__ == "__main__":
    main()

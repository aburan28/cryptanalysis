#!/usr/bin/env python3
"""Materialize Q1467's exact N53 base and matched single-target inputs."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
ROOT = HERE.parents[2]
Q1467 = PARENT / "q1467_density_bridge"
sys.path.insert(0, str(PARENT))
sys.path.insert(0, str(ROOT / "experiments/koblitz-pair-claw-20260929"))

from enumerate_q1413_projected_x import canonical_rotation  # noqa: E402
from orbit_key import OrbitKey  # noqa: E402
from run_probe import curves, field  # noqa: E402

OUTPUT = HERE / "inputs"
CASES = ("n53_planted_unpinned", "n53_ordinary")


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def render() -> dict[str, bytes]:
    receipt = json.loads((Q1467 / "n53_w3_26_orbits.json").read_text())
    assert receipt["proposal_id"] == "Q1467"
    assert receipt["curve_id"] == "EC1N53Ckb1hf77aab617904"
    assert receipt["actual_usable_points_B_before_folding"] == 2756
    assert receipt["selected_projected_columns_K"] == 26
    selected = [int(key, 16) for key in receipt[
        "selected_projected_orbit_keys_onb_hex"]]
    assert len(selected) == len(set(selected)) == 26
    columns = {key: index for index, key in enumerate(selected)}
    onb = field.Onb(53)
    curve = curves.Curve(onb)
    orbit = OrbitKey(onb)
    points = set()
    for encoded in receipt["allowed_raw_x_masks_onb_hex"]:
        raw = curve.pointFromX(onb.fromCoords(int(encoded, 16)))
        assert raw is not None
        subgroup = curve.mul(raw, receipt["cofactor"])
        assert subgroup is not None
        assert curve.mul(subgroup, receipt["subgroup_order"]) is None
        key = canonical_rotation(orbit.cycle_bits(subgroup[0]), 53)
        assert key in columns
        for point in (subgroup, curve.neg(subgroup)):
            assert curve.onCurve(point)
            points.add((columns[key], int(onb.toCoords(point[0])),
                        int(onb.toCoords(point[1]))))
    assert len(points) == 2756
    assert set(Counter(row[0] for row in points).values()) == {106}
    ordered = sorted(points)
    base_lines = ["Q1468BASE1 53 2756 26"]
    base_lines += [f"{column} {x:x} {y:x}" for column, x, y in ordered]
    data = {"base_points.txt": ("\n".join(base_lines) + "\n").encode()}
    metadata = {
        "kind": "q1468_n53_exact_pair_oracle_inputs",
        "proposal_id": "Q1468", "candidate_id": None, "run_id": None,
        "isogeny": "none", "point_decomposition_stage_code": "PDP4mitm",
        "curve_id": receipt["curve_id"],
        "degree_n": 53, "subgroup_order": receipt["subgroup_order"],
        "factor_base_actual_B": 2756, "folded_columns_K": 26,
        "factor_base_enumerated_set_sha256": receipt[
            "selected_projected_orbit_keys_digest_sha256"],
        "allowed_raw_x_masks_digest_sha256": receipt[
            "allowed_raw_x_masks_digest_sha256"],
        "base_point_encoding": "column_decimal x_onb_coords_hex y_onb_coords_hex",
        "target_encoding": "Q1468TARGET1 53 followed by x_onb_coords_hex y_onb_coords_hex",
        "targets": {},
    }
    for name in CASES:
        source = json.loads((Q1467 / "inputs" / name / "meta.json").read_text())
        assert source["curve_id"] == receipt["curve_id"]
        assert source["factor_base_actual_B"] == 2756
        assert source["folded_columns_K"] == 26
        point = tuple(source["public_target"])
        assert curve.onCurve(point)
        assert curve.mul(point, receipt["subgroup_order"]) is None
        x, y = (int(onb.toCoords(component)) for component in point)
        leaf = f"{name}_target.txt"
        data[leaf] = f"Q1468TARGET1 53\n{x:x} {y:x}\n".encode()
        metadata["targets"][name] = {
            "workload_id": source["workload_id"],
            "public_target": list(point),
            "input_role": source["input_role"],
            "target_file": leaf,
            "q1467_meta_sha256": sha((Q1467 / "inputs" / name /
                                     "meta.json").read_bytes()),
        }
    metadata["base_points_sha256"] = sha(data["base_points.txt"])
    data["meta.json"] = (json.dumps(metadata, indent=2,
                                     sort_keys=True) + "\n").encode()
    return data


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    data = render()
    if args.check:
        assert {path.name for path in OUTPUT.iterdir()} == set(data)
        assert all((OUTPUT / name).read_bytes() == payload
                   for name, payload in data.items())
    else:
        assert not OUTPUT.exists(), "refuse overwrite"
        OUTPUT.mkdir()
        for name, payload in data.items():
            (OUTPUT / name).write_bytes(payload)
    print(json.dumps({"status": "pass", "base_points": 2756,
                      "base_sha256": sha(data["base_points.txt"]),
                      "targets": list(CASES)}), flush=True)


if __name__ == "__main__":
    main()

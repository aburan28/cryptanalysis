#!/usr/bin/env python3
"""Audit Q1481 key archives with independent elliptic-curve group operations."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from enumerate_base import (
    HERE, PROTOCOL, ROOT, canonical_rotation, curves, field,
    onb_x_from_cycle_mask, representatives, sha, OrbitKey,
)


def read_keys(path: Path, n: int) -> list[int]:
    packed = path.read_bytes()
    width = (n + 7) // 8
    assert len(packed) % width == 0
    keys = [int.from_bytes(packed[i:i + width], "little")
            for i in range(0, len(packed), width)]
    assert keys == sorted(set(keys))
    assert all(0 < key < (1 << n) - 1 for key in keys)
    return keys


def independent_raw_checks(n: int, d: int):
    """Choose each stratum's edge/interior masks without using run controls."""
    masks = []
    for span in range(1, d + 1):
        if span == 1:
            masks.append(1)
            continue
        top = 1 << (span - 1)
        interiors = {0, (1 << (span - 2)) - 1,
                     (1 << (span - 2)) // 2}
        for interior in sorted(interiors):
            masks.append(1 | top | (interior << 1))
    return masks


def audit_one(n: int, protocol: dict) -> dict:
    instance = protocol["instances"][str(n)]
    d = instance["nominal_window_dimension_d"]
    receipt_path = HERE / f"n{n}_d{d}_base.json"
    packed_path = HERE / f"n{n}_d{d}_projected_keys.bin"
    receipt = json.loads(receipt_path.read_text())
    packed = packed_path.read_bytes()
    digest = hashlib.sha256(packed).hexdigest()
    keys = read_keys(packed_path, n)
    key_set = set(keys)
    assert receipt["proposal_id"] == "Q1481"
    assert receipt["candidate_id"] is None
    assert receipt["curve_id"] == instance["curve_id"]
    assert receipt["isogeny"] == "none"
    assert receipt["nominal_window_dimension_d"] == d
    assert receipt["nominal_raw_x_orbits"] == 1 << (d - 1)
    assert receipt["signed_frobenius_columns_K"] == len(keys)
    assert receipt["actual_usable_points_B_before_folding"] == 2 * n * len(keys)
    assert receipt["packed_projected_key_file_bytes"] == len(packed)
    assert receipt["packed_projected_key_file_sha256"] == digest
    assert receipt["enumerated_set_sha256"] == digest
    assert receipt["protocol_sha256"] == sha(PROTOCOL)
    assert receipt["source_sha256"] == protocol["source_sha256"][
        "enumerate_base.py"]
    assert receipt["runtime_info_sha256"] == protocol["runtime_info_sha256"]
    assert receipt["complete_solve_work_log2"] is None
    strata = receipt["strata"]
    assert len(strata) == d
    for span, row in enumerate(strata, start=1):
        assert row["span"] == span
        assert row["raw_x_orbits"] == (
            1 if span == 1 else 1 << (span - 2))
    assert sum(row["raw_x_orbits"] for row in strata) == 1 << (d - 1)
    assert sum(row["rational_x_orbits"] -
               row["identity_projection_orbits"] -
               row["duplicate_projected_orbits"]
               for row in strata) == len(keys)
    assert receipt["geometric_rational_point_count_before_projection"] == (
        2 * n * sum(row["rational_x_orbits"] for row in strata))

    onb = field.Onb(n)
    curve = curves.Curve(onb)
    orbit = OrbitKey(onb)
    control_masks = {row["raw_cycle_mask"] for row in receipt[
        "independent_group_control_inputs"]}
    selected = sorted(control_masks.union(independent_raw_checks(n, d)))
    membership_checks = 0
    rational_checks = nonrational_checks = identity_checks = 0
    for mask in selected:
        assert mask > 0 and mask.bit_length() <= d
        assert mask & 1
        x = onb_x_from_cycle_mask(mask, onb, orbit)
        point = curve.pointFromX(x)
        archived = next((row for row in receipt[
            "independent_group_control_inputs"]
                         if row["raw_cycle_mask"] == mask), None)
        if point is None:
            nonrational_checks += 1
            if archived is not None:
                assert not archived["rational"]
                assert archived["projected_orbit_key"] is None
            continue
        rational_checks += 1
        projected = curve.mul(point, instance["cofactor"])
        if projected is None:
            identity_checks += 1
            if archived is not None:
                assert archived["rational"]
                assert archived["projected_orbit_key"] is None
            continue
        assert curve.onCurve(projected)
        assert curve.mul(projected, instance["subgroup_order"]) is None
        key = canonical_rotation(orbit.cycle_bits(projected[0]), n)
        assert key in key_set
        assert len({((key << i) | (key >> (n - i))) & ((1 << n) - 1)
                    for i in range(n)}) == n
        if archived is not None:
            assert archived["rational"]
            assert archived["projected_orbit_key"] == key
        membership_checks += 1
    assert sum(1 for _ in representatives(d)) == 1 << (d - 1)
    return {"n": n, "curve_id": instance["curve_id"],
            "nominal_window_dimension_d": d,
            "actual_usable_B": receipt[
                "actual_usable_points_B_before_folding"],
            "folded_K": len(keys), "enumerated_set_sha256": digest,
            "receipt_sha256": sha(receipt_path),
            "packed_key_file_sha256": digest,
            "independent_group_checks": len(selected),
            "rational_checks": rational_checks,
            "nonrational_checks": nonrational_checks,
            "identity_checks": identity_checks,
            "archive_membership_checks": membership_checks,
            "status": "PASS"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    protocol = json.loads(PROTOCOL.read_text())
    assert protocol["source_sha256"]["verify_base.py"] == sha(Path(__file__))
    for relative, digest in protocol["dependency_sha256"].items():
        assert sha(ROOT / relative) == digest
    result = {"kind": "q1481_independent_base_archive_audit",
              "proposal_id": "Q1481", "candidate_id": None,
              "isogeny": "none", "protocol_sha256": sha(PROTOCOL),
              "rows": [audit_one(n, protocol) for n in (53, 83)],
              "status": "PASS", "complete_solve_work_log2": None}
    path = HERE / "archive_audit.json"
    if args.check or path.exists():
        assert json.loads(path.read_text()) == result
        print("Q1481 base archive audit PASS (archived)")
    else:
        path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
        print("Q1481 base archive audit PASS")


if __name__ == "__main__":
    main()

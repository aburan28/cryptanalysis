#!/usr/bin/env python3
"""Reconstruct Q1488's ordinary N53 relation inside Q1482's raw S3 inputs."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
sys.path.insert(0, str(PARENT))

from chain_s3 import evaluate_s3  # noqa: E402
from run_probe import curves, field  # noqa: E402
from s3_root_oracle import s3_roots  # noqa: E402
from q1481_window_orbit_base.enumerate_base import (  # noqa: E402
    OrbitKey, canonical_rotation, onb_x_from_cycle_mask,
    representatives,
)
from q1482_window_s3.build_formula import (  # noqa: E402
    raw_targets_and_public,
)
from q1423_target_coupled.target_inputs import (  # noqa: E402
    encode_targets,
)


DESIGN = HERE / "design_protocol.json"
PROTOCOL = HERE / "protocol.json"
RUNTIME = HERE / "sage_runtime_info.json"
OUT = HERE / "bridge_result.json"
Q1481 = PARENT / "q1481_window_orbit_base"
Q1482 = PARENT / "q1482_window_s3"
Q1488 = PARENT / "q1488_window_pair_table"
INPUT_PATHS = {
    "q1488_n53_ordinary_receipt": Q1488 / "runs/n53_ordinary.json",
    "q1488_archive_audit": Q1488 / "archive_audit.json",
    "q1482_n53_ordinary_input": Q1482 / "inputs/n53_ordinary/input.json",
    "q1482_n53_ordinary_targets": Q1482 / "inputs/n53_ordinary/targets.txt",
    "q1481_n53_projected_keys": Q1481 / "n53_d14_projected_keys.bin",
    "q1481_n53_base_receipt": Q1481 / "n53_d14_base.json",
    "q1482_formula_source": Q1482 / "build_formula.py",
    "q1482_model_verifier_source": Q1482 / "verify_model.py",
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def add_all(curve, points):
    total = None
    for point in points:
        total = curve.add(total, point)
    return total


def window_starts(cycle_mask: int, n: int, d: int) -> list[int]:
    full = (1 << n) - 1
    starts = []
    for start in range(n):
        mask = ((1 << d) - 1) << start
        mask = (mask | (mask >> n)) & full
        if cycle_mask & ~mask == 0:
            starts.append(start)
    return starts


def reconstruct() -> dict:
    design = json.loads(DESIGN.read_text())
    protocol = json.loads(PROTOCOL.read_text())
    assert design["proposal_id"] == protocol["proposal_id"] == "Q1490"
    assert design["candidate_id"] is protocol["candidate_id"] is None
    assert design["run_id"] is protocol["run_id"] is None
    assert design["isogeny"] == protocol["isogeny"] == "none"
    assert protocol["design_sha256"] == sha(DESIGN)
    assert protocol["source_sha256"] == sha(Path(__file__))
    assert protocol["runtime_info_sha256"] == sha(RUNTIME)
    assert json.loads(RUNTIME.read_text())["status"] == "verified"
    for label, path in INPUT_PATHS.items():
        expected = design["frozen_inputs_sha256"][label]
        assert sha(path) == expected == protocol["frozen_inputs_sha256"][
            label], label

    parent = json.loads(INPUT_PATHS["q1488_n53_ordinary_receipt"].read_text())
    parent_audit = json.loads(INPUT_PATHS["q1488_archive_audit"].read_text())
    q1482_input = json.loads(INPUT_PATHS[
        "q1482_n53_ordinary_input"].read_text())
    base = json.loads(INPUT_PATHS["q1481_n53_base_receipt"].read_text())
    assert parent_audit["status"] == "passed"
    assert parent["verified_relation_count"] == 1
    assert parent["candidate_id"] is parent["run_id"] is None
    assert parent["isogeny"] == "none"
    for row in (parent, q1482_input, base):
        assert row["curve_id"] == design["curve_id"]
    assert parent["factor_base_actual_B"] == q1482_input[
        "factor_base_actual_B"] == base[
            "actual_usable_points_B_before_folding"] == design[
                "factor_base_actual_B"]
    assert parent["folded_columns_K"] == q1482_input[
        "folded_columns_K"] == base["signed_frobenius_columns_K"] == design[
            "factor_base_folded_columns_K"]
    assert parent["factor_base_enumerated_set_sha256"] == base[
        "enumerated_set_sha256"] == design[
            "factor_base_enumerated_set_sha256"]

    n, d = design["field_degree_n"], base[
        "nominal_window_dimension_d"]
    assert n == 53 and d == 14
    cofactor = base["cofactor"]
    subgroup_order = json.loads((Q1481 / "protocol.json").read_text())[
        "instances"]["53"]["subgroup_order"]
    onb = field.Onb(n)
    curve = curves.Curve(onb)
    orbit = OrbitKey(onb)
    relation = parent["ordinary_query"]["relation"]
    target = tuple(parent["target"])
    points = [tuple(point) for point in relation["points"]]
    keys = relation["folded_column_keys"]
    assert len(points) == len(keys) == len(set(keys)) == 4
    assert add_all(curve, points) == target
    assert all(curve.onCurve(point) and
               curve.mul(point, subgroup_order) is None
               for point in points)
    assert [orbit.canonical(point)[0] for point in points] == keys
    archived = INPUT_PATHS["q1481_n53_projected_keys"].read_bytes()
    width = (n + 7) // 8
    archived_keys = {int.from_bytes(archived[i:i + width], "little")
                     for i in range(0, len(archived), width)}
    assert len(archived_keys) == base["signed_frobenius_columns_K"]
    assert set(keys) <= archived_keys

    target_keys = set(keys)
    matched = {}
    raw_scanned = rational = identity = 0
    for raw_cycle_mask, span in representatives(d):
        raw_scanned += 1
        x = onb_x_from_cycle_mask(raw_cycle_mask, onb, orbit)
        raw = curve.pointFromX(x)
        if raw is None:
            continue
        rational += 1
        projected = curve.mul(raw, cofactor)
        if projected is None:
            identity += 1
            continue
        key = canonical_rotation(orbit.cycle_bits(projected[0]), n)
        if key in target_keys:
            assert key not in matched
            matched[key] = (raw_cycle_mask, span, raw, projected)
    assert raw_scanned == base["nominal_raw_x_orbits"] == 8192
    assert rational == base["signed_frobenius_columns_K"] == 4060
    assert identity == 0 and len(matched) == 4

    lifts = []
    raw_points = []
    for point, key in zip(points, keys):
        raw_cycle_mask, span, raw_rep, projected_rep = matched[key]
        compatible = []
        for shift in range(n):
            raw_shifted = curve.frob(raw_rep, shift)
            projected_shifted = curve.frob(projected_rep, shift)
            for sign in (1, -1):
                candidate_projected = (projected_shifted if sign == 1
                                       else curve.neg(projected_shifted))
                if candidate_projected == point:
                    candidate_raw = (raw_shifted if sign == 1
                                     else curve.neg(raw_shifted))
                    compatible.append((shift, sign, candidate_raw))
        assert len(compatible) == 1
        shift, sign, raw = compatible[0]
        assert curve.mul(raw, cofactor) == point
        cycle_mask = orbit.cycle_bits(raw[0])
        starts = window_starts(cycle_mask, n, d)
        assert starts and onb.toCoords(raw[0]) != 0
        raw_points.append(raw)
        lifts.append({
            "folded_column_key": key,
            "representative_raw_cycle_mask": raw_cycle_mask,
            "representative_span": span,
            "frobenius_shift": shift,
            "sign": sign,
            "raw_point": list(raw),
            "raw_x_normal_basis_coordinates": onb.toCoords(raw[0]),
            "raw_cycle_mask": cycle_mask,
            "valid_window_starts": starts,
            "projected_point": list(point),
        })

    left_mid = curve.add(raw_points[0], raw_points[1])
    right_mid = curve.add(raw_points[2], raw_points[3])
    raw_target = curve.add(left_mid, right_mid)
    assert left_mid is not None and right_mid is not None
    assert raw_target is not None
    assert curve.mul(raw_target, cofactor) == target
    raw_targets, q1482_public = raw_targets_and_public(n, "ordinary")
    assert tuple(q1482_public) == target
    assert len(raw_targets) == q1482_input["target_preimage_x_count"] == 428
    assert encode_targets(n, raw_targets) == INPUT_PATHS[
        "q1482_n53_ordinary_targets"].read_bytes()
    raw_target_x = onb.toCoords(raw_target[0])
    assert raw_target_x in raw_targets
    target_index = raw_targets.index(raw_target_x)
    assert raw_targets.count(raw_target_x) == 1

    chain = (
        (raw_points[0][0], raw_points[1][0], left_mid[0]),
        (raw_points[2][0], raw_points[3][0], right_mid[0]),
        (left_mid[0], right_mid[0], raw_target[0]),
    )
    for a, b, c in chain:
        assert evaluate_s3(onb, a, b, c) == 0
        assert c in s3_roots(onb, a, b)
    assert len({lift["folded_column_key"] for lift in lifts}) == 4
    return {
        "kind": "q1490_n53_ordinary_relation_raw_window_bridge",
        "proposal_id": "Q1490", "candidate_id": None,
        "run_id": None, "isogeny": "none",
        "status": "PASS",
        "curve_id": design["curve_id"],
        "field_degree_n": n,
        "factor_base_actual_B": design["factor_base_actual_B"],
        "factor_base_folded_columns_K": design[
            "factor_base_folded_columns_K"],
        "factor_base_enumerated_set_sha256": design[
            "factor_base_enumerated_set_sha256"],
        "ordinary_public_target": list(target),
        "four_projected_points": [list(point) for point in points],
        "four_raw_lifts": lifts,
        "raw_pair_mid_points": [list(left_mid), list(right_mid)],
        "raw_pair_mid_x_normal_basis_coordinates": [
            onb.toCoords(left_mid[0]), onb.toCoords(right_mid[0])],
        "raw_target_point": list(raw_target),
        "raw_target_x_normal_basis_coordinates": raw_target_x,
        "q1482_target_preimage_index": target_index,
        "q1482_target_preimage_count": len(raw_targets),
        "three_direct_s3_links_zero": True,
        "three_independent_root_memberships": True,
        "four_distinct_folded_columns": True,
        "raw_representatives_checked": raw_scanned,
        "rational_representatives_checked": rational,
        "identity_projections_checked": identity,
        "matched_projected_columns": len(matched),
        "known_witness_control_only": True,
        "natural_relation_yield_estimate": None,
        "successful_unpinned_solver_cost": None,
        "complete_n131_log2_work": None,
        "challenge_run_admitted": False,
        "design_sha256": sha(DESIGN),
        "protocol_sha256": sha(PROTOCOL),
        "source_sha256": sha(Path(__file__)),
        "runtime_info_sha256": sha(RUNTIME),
        "parent_q1488_receipt_sha256": sha(INPUT_PATHS[
            "q1488_n53_ordinary_receipt"]),
        "parent_q1482_input_sha256": sha(INPUT_PATHS[
            "q1482_n53_ordinary_input"]),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    result = reconstruct()
    encoded = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.check:
        assert OUT.read_text() == encoded
        print("Q1490 ordinary witness bridge PASS (archived)")
    else:
        assert not OUT.exists(), "refusing to overwrite archived bridge"
        OUT.write_text(encoded)
        print(json.dumps({"status": result["status"],
                          "raw_target_index": result[
                              "q1482_target_preimage_index"],
                          "matched_columns": result[
                              "matched_projected_columns"]},
                         sort_keys=True))


if __name__ == "__main__":
    main()

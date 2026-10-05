#!/usr/bin/env python3
"""Independent curve-group replay of sampled Q1437 W7 controls."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
sys.path.insert(0, str(PARENT))
from enumerate_q1413_projected_x import canonical_rotation  # noqa: E402
from run_probe import ROOT, curves, field, sha  # noqa: E402

sys.path.insert(0, str(ROOT / "experiments/koblitz-pair-claw-20260929"))
from orbit_key import OrbitKey  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--emit", action="store_true")
    args = parser.parse_args()
    protocol = json.loads((HERE / "protocol.json").read_text())
    sample = json.loads((HERE / "sample.json").read_text())
    assert protocol["verification_source_sha256"] == sha(Path(__file__))
    assert sample["protocol_sha256"] == sha(HERE / "protocol.json")
    assert sample["source_sha256"] == protocol["source_sha256"]
    assert sample["runtime_info_sha256"] == protocol["runtime_info_sha256"]
    assert sample["candidate_id"] is None and sample["isogeny"] == "none"
    assert sample["curve_id"] == protocol["curve_id"]
    assert sample["sample_size"] == protocol["sample_size"]
    assert sample["population_weight7_x_masks"] == math.comb(131, 7)
    assert sample["population_weight7_x_orbits"] == math.comb(131, 7) // 131
    assert len(sample["independent_group_controls"]) == protocol[
        "independent_control_count"]
    assert sample["actual_usable_points_B_before_folding"] is None
    assert sample["complete_solve_work_log2"] is None

    onb = field.Onb(131)
    curve = curves.Curve(onb)
    orbit = OrbitKey(onb)
    rational = nonrational = nonidentity = 0
    for control in sample["independent_group_controls"]:
        mask = control["normal_x_mask"]
        assert mask.bit_count() == 7
        x = onb.fromCoords(mask)
        assert control["raw_orbit_key"] == canonical_rotation(
            orbit.cycle_bits(x), 131)
        point = curve.pointFromX(x)
        if point is None:
            nonrational += 1
            assert control["rational"] is False
            assert control["projected_orbit_key"] is None
            continue
        rational += 1
        assert control["rational"] is True
        projected = curve.mul(point, 4)
        if projected is None:
            assert control["projected_orbit_key"] is None
            continue
        nonidentity += 1
        assert curve.onCurve(projected)
        assert curve.mul(projected, protocol["subgroup_order"]) is None
        assert control["projected_orbit_key"] == canonical_rotation(
            orbit.cycle_bits(projected[0]), 131)

    population = sample["population_weight7_x_orbits"]
    rate = sample["sample_rational_rate"]
    base = json.loads((PARENT / "runs/n131_q1413_projected_x_w6.json").read_text())
    assert sha(PARENT / "runs/n131_q1413_projected_x_w6.json") == protocol[
        "exact_w6_base_receipt_sha256"]
    estimate = sample["conditional_estimate"]
    assert math.isclose(estimate["conditional_K"],
                        base["signed_frobenius_columns_K"] + population * rate)
    assert math.isclose(estimate["conditional_B"],
                        262 * estimate["conditional_K"])
    assert math.isclose(estimate[
        "optimistic_four_nonzeros_times_K_squared_log2"],
        math.log2(4 * estimate["conditional_K"] ** 2))
    result = {
        "kind": "q1437_independent_group_control_replay",
        "status": "passed", "controls": rational + nonrational,
        "rational_controls": rational, "nonrational_controls": nonrational,
        "nonidentity_group_projections": nonidentity,
        "protocol_sha256": sha(HERE / "protocol.json"),
        "sample_sha256": sha(HERE / "sample.json"),
        "source_sha256": sha(Path(__file__)),
        "scope": "32 sampled group-law controls and estimate arithmetic; no full W7 enumeration or relation solve",
    }
    if args.emit:
        output = HERE / "verification.json"
        assert not output.exists(), "refuse to overwrite verifier receipt"
        output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Replay Q1438 sparse-base controls with independent Sage point arithmetic."""

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
    assert protocol["verifier_sha256"] == sha(Path(__file__))
    rows = []
    for n in (53, 83):
        instance = protocol["instances"][str(n)]
        path = HERE / f"n{n}_w{instance['new_weight_bound']}_base.json"
        receipt = json.loads(path.read_text())
        assert receipt["protocol_sha256"] == sha(HERE / "protocol.json")
        assert receipt["source_sha256"] == protocol["source_sha256"]
        assert receipt["curve_id"] == instance["curve_id"]
        assert receipt["candidate_id"] is None and receipt["isogeny"] == "none"
        assert receipt["actual_usable_points_B_before_folding"] == (
            2 * n * receipt["signed_frobenius_columns_K"])
        assert receipt["reference_folded_columns_K"] == instance[
            "reference_columns_K"]
        assert receipt["reference_exact_set_checked"] is True
        assert len(receipt["strata"]) == instance["new_weight_bound"]
        assert sum(row["raw_x_orbits"] for row in receipt["strata"]) == sum(
            math.comb(n, i) // n
            for i in range(1, instance["new_weight_bound"] + 1))
        onb = field.Onb(n)
        curve = curves.Curve(onb)
        orbit = OrbitKey(onb)
        positive = negative = 0
        for control in receipt["independent_group_controls"]:
            x = onb.fromCoords(control["normal_x_mask"])
            point = curve.pointFromX(x)
            if point is None:
                negative += 1
                assert control["rational"] is False
                assert control["projected_orbit_key"] is None
                continue
            positive += 1
            assert control["rational"] is True
            projected = curve.mul(point, instance["cofactor"])
            if projected is None:
                assert control["projected_orbit_key"] is None
                continue
            assert curve.onCurve(projected)
            assert curve.mul(projected, instance["subgroup_order"]) is None
            assert control["projected_orbit_key"] == canonical_rotation(
                orbit.cycle_bits(projected[0]), n)
        assert positive == negative == 16
        rows.append({"degree_n": n, "curve_id": instance["curve_id"],
                     "factor_base_B": receipt[
                         "actual_usable_points_B_before_folding"],
                     "folded_columns_K": receipt["signed_frobenius_columns_K"],
                     "enumerated_set_sha256": receipt["enumerated_set_sha256"],
                     "positive_group_controls": positive,
                     "negative_group_controls": negative,
                     "receipt_sha256": sha(path)})
    result = {"kind": "q1438_independent_dense_base_group_replay",
              "status": "passed", "proposal_id": "Q1438",
              "candidate_id": None, "isogeny": "none", "rows": rows,
              "protocol_sha256": sha(HERE / "protocol.json"),
              "source_sha256": sha(Path(__file__)),
              "scope": "32 group-law controls per degree; no second full base enumeration or ordinary relation solve"}
    if args.emit:
        output = HERE / "verification.json"
        assert not output.exists(), "refuse to overwrite verification receipt"
        output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()

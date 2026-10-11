#!/usr/bin/env python3
"""Replay exact S3 root-chain certificates and group relations."""

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PARENT = ROOT / "experiments/compact-s3-m4-20261003"
Q1419 = PARENT / "q1419_partial_pin"
Q1316 = ROOT / "experiments/compact-s3-m4-external-roots-20261010"
sys.path[:0] = [str(Q1419), str(PARENT), str(Q1316),
                str(ROOT / "ecc2k130/codegen")]
import field  # noqa: E402
from chain_s3 import evaluate_s3  # noqa: E402
from run_cell import (OrbitKey, canonical_x, curves, read_base_keys,
                      read_profile, verify_relation)  # noqa: E402
from oracle import Counted, roots  # noqa: E402


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text())


def check_degree(n, frozen, protocol):
    result_path = HERE / f"n{n}_run.json"
    result = load(result_path)
    profile, parent, fixture = read_profile(protocol, n)
    control = frozen["degrees"][str(n)]
    raw = fixture["fixture"]
    assert result["proposal_id"] == frozen["proposal_id"]
    assert result["candidate_id"] is result["run_id"] is None
    assert result["isogeny"] == "none"
    assert result["freeze_sha256"] == digest(HERE / "freeze.json")
    assert result["curve_id"] == control["curve_id"] == profile["curve_id"]
    assert result["actual_usable_points_B"] == control[
        "actual_usable_points_B"] == profile["factor_base_actual_B"]
    assert result["folded_columns_K"] == control[
        "folded_columns_K"] == profile["folded_columns_K"]
    assert result["factor_base_enumerated_set_sha256"] == control[
        "factor_base_enumerated_set_sha256"] == profile[
            "factor_base_enumerated_set_sha256"]
    assert result["workload_id"] == control["workload_id"] == profile[
        "workload_id"]
    assert result["public_target"] == control["public_target"] == profile[
        "public_target"]
    assert digest(Q1419 / "runs" / f"n{n}_three_leaves/receipt.json") == (
        control["parent_receipt_sha256"])
    assert digest(ROOT / profile["fixture_receipt"]["path"]) == control[
        "fixture_sha256"]
    assert result["fixed_raw_leaf_x_coords"] == control[
        "fixed_raw_leaf_x_coords"] == raw["raw_leaf_x"][:3]
    onb = field.Onb(n)
    target = int(raw["raw_sum"][0])
    assert result["target_preimage_x_coords"] == onb.toCoords(target)
    assert result["target_preimage_x_coords"] in parent[
        "raw_preimage_x_coordinates"]
    assert result["archived_witness_fourth_leaf_x_coords"] == raw[
        "raw_leaf_x"][3]
    x0, x1, x2 = [onb.fromCoords(value) for value in raw["raw_leaf_x"][:3]]
    ctx = Counted(onb)
    expected = []
    for a in roots(ctx, x0, x1):
        for b in roots(ctx, a, target):
            for c in roots(ctx, x2, b):
                expected.append((onb.toCoords(a), onb.toCoords(b),
                                 onb.toCoords(c)))
    observed = [(row["first_mid_x_coords"],
                 row["second_mid_x_coords"],
                 row["fourth_leaf_x_coords"])
                for row in result["root_paths"]]
    assert observed == expected
    assert result["oracle_field_calls"] == ctx.calls
    assert raw["raw_leaf_x"][3] in [row[2] for row in observed]
    assert result["root_chain_seconds_exploratory"] >= 0
    assert result["base_load_seconds_exploratory"] >= 0
    assert result["candidate_checks_seconds_exploratory"] >= 0
    keys = read_base_keys(profile, onb)
    curve = curves.Curve(onb)
    orbit = OrbitKey(onb) if n == 83 else None
    successes = 0
    for row in result["root_paths"]:
        a, b, c = (onb.fromCoords(value) for value in (
            row["first_mid_x_coords"], row["second_mid_x_coords"],
            row["fourth_leaf_x_coords"]))
        assert evaluate_s3(onb, x0, x1, a) == 0
        assert evaluate_s3(onb, a, b, target) == 0
        assert evaluate_s3(onb, x2, b, c) == 0
        coords = row["fourth_leaf_x_coords"]
        if not coords or coords.bit_count() > profile[
            "normal_basis_weight_bound"]:
            status = "outside_weight_or_zero"
        else:
            point = curve.pointFromX(c)
            if point is None:
                status = "nonrational_raw_x"
            else:
                subgroup = curve.mul(point, profile["cofactor"])
                if subgroup is None:
                    status = "identity_projection"
                else:
                    assert curve.mul(subgroup, profile["subgroup_order_r"]) is None
                    key = canonical_x(onb, subgroup[0]) if n == 53 else (
                        orbit.canonical(subgroup)[0])
                    status = "exact_base_hit" if key in keys else (
                        "outside_exact_base")
        assert status == row["status"]
        if status == "exact_base_hit":
            leaves = raw["raw_leaf_x"][:3] + [coords]
            bits = [[2+i*n+j for j in range(n)] for i in range(4)]
            model = {bit: bool(value >> j & 1)
                     for value, vector in zip(leaves, bits)
                     for j, bit in enumerate(vector)}
            relation = verify_relation(profile, model, bits)
            assert relation == row["relation"]
            successes += relation["status"] == "verified_four_point_relation"
        else:
            assert row["relation"] is None
    assert successes == result["verified_relation_count"] > 0
    return {"n": n, "paths": len(observed), "verified_relations": successes,
            "run_sha256": digest(result_path)}


def main():
    frozen = load(HERE / "freeze.json")
    assert frozen["schema"] == "q20261010172500-freeze-v1"
    assert frozen["proposal_id"] == "Q20261010172500"
    assert frozen["candidate_id"] is frozen["run_id"] is None
    assert frozen["isogeny"] == "none"
    assert frozen["q1419_protocol_sha256"] == digest(Q1419 / "protocol.json")
    assert frozen["q1316_oracle_sha256"] == digest(Q1316 / "oracle.py")
    for name, value in frozen["source_sha256"].items():
        assert digest(HERE / name) == value
    protocol = load(Q1419 / "protocol.json")
    rows = [check_degree(n, frozen, protocol) for n in (53, 83)]
    output = HERE / "audit.json"
    assert not output.exists()
    output.write_text(json.dumps({"schema": "q20261010172500-audit-v1",
        "status": "PASS", "freeze_sha256": digest(HERE / "freeze.json"),
        "auditor_sha256": digest(Path(__file__)), "rows": rows},
        sort_keys=True, indent=2) + "\n")
    print(json.dumps({"status": "PASS", "rows": rows}))


if __name__ == "__main__":
    main()

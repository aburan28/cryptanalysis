#!/usr/bin/env python3
"""Exact conditional completion of a balanced four-leaf S3 chain."""

import argparse
import hashlib
import json
import sys
import time
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

PROPOSAL = "Q20261010172500"
FREEZE = HERE / "freeze.json"


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text())


def save(path, value):
    path = Path(path)
    assert not path.exists(), path
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")


def freeze():
    protocol = load(Q1419 / "protocol.json")
    rows = {}
    for n in (53, 83):
        profile, parent, fixture = read_profile(protocol, n)
        receipt_path = Q1419 / "runs" / f"n{n}_three_leaves/receipt.json"
        rows[str(n)] = {
            "curve_id": profile["curve_id"],
            "actual_usable_points_B": profile["factor_base_actual_B"],
            "folded_columns_K": profile["folded_columns_K"],
            "factor_base_enumerated_set_sha256": profile[
                "factor_base_enumerated_set_sha256"],
            "workload_id": profile["workload_id"],
            "public_target": profile["public_target"],
            "weight_bound": profile["normal_basis_weight_bound"],
            "parent_receipt_sha256": digest(receipt_path),
            "fixture_sha256": digest(ROOT / profile["fixture_receipt"]["path"]),
            "parent_target_x_options_sha256": hashlib.sha256(json.dumps(
                parent["raw_preimage_x_coordinates"],
                separators=(",", ":")).encode()).hexdigest(),
            "fixed_raw_leaf_x_coords": fixture["fixture"]["raw_leaf_x"][:3],
        }
    save(FREEZE, {"schema": "q20261010172500-freeze-v1",
                  "proposal_id": PROPOSAL, "candidate_id": None,
                  "run_id": None, "isogeny": "none",
                  "q1419_protocol_sha256": digest(Q1419 / "protocol.json"),
                  "q1316_oracle_sha256": digest(Q1316 / "oracle.py"),
                  "source_sha256": {name: digest(HERE / name) for name in
                                    ("PROTOCOL.md", "experiment.py", "audit.py")},
                  "degrees": rows})
    print(json.dumps({"freeze_sha256": digest(FREEZE)}))


def check_freeze():
    frozen = load(FREEZE)
    assert frozen["q1419_protocol_sha256"] == digest(Q1419 / "protocol.json")
    assert frozen["q1316_oracle_sha256"] == digest(Q1316 / "oracle.py")
    for name, value in frozen["source_sha256"].items():
        assert digest(HERE / name) == value
    return frozen


def root_paths(ctx, x0, x1, x2, target):
    f = ctx.f
    answer = []
    for z0 in roots(ctx, x0, x1):
        assert evaluate_s3(f, x0, x1, z0) == 0
        for z1 in roots(ctx, z0, target):
            assert evaluate_s3(f, z0, z1, target) == 0
            for x3 in roots(ctx, x2, z1):
                assert evaluate_s3(f, x2, x3, z1) == 0
                answer.append((z0, z1, x3))
    return answer


def candidate_status(profile, onb, curve, keys, orbit, coords):
    n = profile["field_degree_n"]
    weight = profile["normal_basis_weight_bound"]
    if coords == 0 or coords.bit_count() > weight:
        return "outside_weight_or_zero"
    point = curve.pointFromX(onb.fromCoords(coords))
    if point is None:
        return "nonrational_raw_x"
    subgroup = curve.mul(point, profile["cofactor"])
    if subgroup is None:
        return "identity_projection"
    assert curve.mul(subgroup, profile["subgroup_order_r"]) is None
    key = canonical_x(onb, subgroup[0]) if n == 53 else (
        orbit.canonical(subgroup)[0])
    return "exact_base_hit" if key in keys else "outside_exact_base"


def run_degree(frozen, n, protocol):
    profile, parent, fixture = read_profile(protocol, n)
    control = frozen["degrees"][str(n)]
    receipt_path = Q1419 / "runs" / f"n{n}_three_leaves/receipt.json"
    assert digest(receipt_path) == control["parent_receipt_sha256"]
    assert digest(ROOT / profile["fixture_receipt"]["path"]) == control[
        "fixture_sha256"]
    assert profile["curve_id"] == control["curve_id"]
    assert profile["factor_base_actual_B"] == control["actual_usable_points_B"]
    assert profile["folded_columns_K"] == control["folded_columns_K"]
    assert profile["factor_base_enumerated_set_sha256"] == control[
        "factor_base_enumerated_set_sha256"]
    assert fixture["fixture"]["raw_leaf_x"][:3] == control[
        "fixed_raw_leaf_x_coords"]
    onb = field.Onb(n)
    raw = fixture["fixture"]
    x0, x1, x2 = [onb.fromCoords(value) for value in raw["raw_leaf_x"][:3]]
    target = int(raw["raw_sum"][0])
    target_coords = onb.toCoords(target)
    assert target_coords in parent["raw_preimage_x_coordinates"]
    ctx = Counted(onb)
    started = time.monotonic()
    paths = root_paths(ctx, x0, x1, x2, target)
    root_seconds = time.monotonic() - started
    assert raw["raw_leaf_x"][3] in [onb.toCoords(path[2]) for path in paths]
    started = time.monotonic()
    keys = read_base_keys(profile, onb)
    base_load_seconds = time.monotonic() - started
    curve = curves.Curve(onb)
    orbit = OrbitKey(onb) if n == 83 else None
    results = []
    started = time.monotonic()
    for z0, z1, x3 in paths:
        coords = onb.toCoords(x3)
        status = candidate_status(profile, onb, curve, keys, orbit, coords)
        relation = None
        if status == "exact_base_hit":
            leaves = raw["raw_leaf_x"][:3] + [coords]
            bits = [[2+i*n+j for j in range(n)] for i in range(4)]
            model = {bit: bool(value >> j & 1)
                     for value, row in zip(leaves, bits)
                     for j, bit in enumerate(row)}
            relation = verify_relation(profile, model, bits)
            assert relation["raw_leaf_x"] == leaves
        results.append({"first_mid_x_coords": onb.toCoords(z0),
                        "second_mid_x_coords": onb.toCoords(z1),
                        "fourth_leaf_x_coords": coords,
                        "status": status, "relation": relation})
    check_seconds = time.monotonic() - started
    assert any(row["relation"] and row["relation"]["status"] ==
               "verified_four_point_relation" for row in results)
    return {"schema": "q20261010172500-run-v1", "proposal_id": PROPOSAL,
            "candidate_id": None, "run_id": None, "isogeny": "none",
            "curve_id": profile["curve_id"], "field_degree_n": n,
            "actual_usable_points_B": profile["factor_base_actual_B"],
            "folded_columns_K": profile["folded_columns_K"],
            "factor_base_enumerated_set_sha256": profile[
                "factor_base_enumerated_set_sha256"],
            "workload_id": profile["workload_id"],
            "public_target": profile["public_target"],
            "freeze_sha256": digest(FREEZE),
            "fixed_raw_leaf_x_coords": raw["raw_leaf_x"][:3],
            "target_preimage_x_coords": target_coords,
            "archived_witness_fourth_leaf_x_coords": raw["raw_leaf_x"][3],
            "oracle_field_calls": ctx.calls,
            "root_chain_seconds_exploratory": root_seconds,
            "base_load_seconds_exploratory": base_load_seconds,
            "candidate_checks_seconds_exploratory": check_seconds,
            "root_paths": results,
            "verified_relation_count": sum(row["relation"] is not None and
                row["relation"]["status"] == "verified_four_point_relation"
                for row in results)}


def run():
    frozen = check_freeze()
    protocol = load(Q1419 / "protocol.json")
    for n in (53, 83):
        path = HERE / f"n{n}_run.json"
        if path.exists():
            continue
        result = run_degree(frozen, n, protocol)
        save(path, result)
        print(json.dumps({"n": n,
                          "root_paths": len(result["root_paths"]),
                          "verified_relation_count": result[
                              "verified_relation_count"],
                          "root_seconds": result[
                              "root_chain_seconds_exploratory"]}), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("freeze", "check", "run"))
    action = parser.parse_args().action
    if action == "freeze":
        freeze()
    elif action == "check":
        check_freeze(); print("PASS: freeze")
    else:
        run()

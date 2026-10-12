#!/usr/bin/env python3
"""Independently replay Q1488's matched-base pair-table stage receipts."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

from build_n53_base import HERE, PARENT, Q1481, ROOT, sha
from sample_window import representative

sys.path.insert(0, str(PARENT))
from run_probe import curves, field  # noqa: E402
sys.path.insert(0, str(Q1481))
from enumerate_base import canonical_rotation, onb_x_from_cycle_mask
from verify_base import read_keys  # noqa: E402
sys.path.insert(0, str(ROOT / "experiments/koblitz-pair-claw-20260929"))
from orbit_key import OrbitKey  # noqa: E402

PROTOCOL = HERE / "protocol.json"
OUT = HERE / "archive_audit.json"


def replay_relation(n: int, cell: dict, relation: dict) -> dict:
    onb = field.Onb(n)
    curve = curves.Curve(onb)
    orbit = OrbitKey(onb)
    target = tuple(cell["public_target"])
    packed = Q1481 / (f"n{n}_d{cell['nominal_window_dimension_d']}"
                       "_projected_keys.bin")
    keys = set(read_keys(packed, n))
    assert len(keys) == cell["folded_columns_K"]
    proof = relation["collision_proof"]
    table_points = [tuple(row) for row in proof[
        "table_pair_original_points"]]
    query_points = [tuple(row) for row in proof[
        "query_pair_original_points"]]
    originals = table_points + query_points
    certificates = (proof["table_pair_membership_certificates"] +
                    proof["query_pair_membership_certificates"])
    assert len(originals) == len(certificates) == 4
    if n == 53:
        assert certificates == [None] * 4
    else:
        for point, cert in zip(originals, certificates):
            assert isinstance(cert, dict)
            ordinal = cert["raw_orbit_ordinal"]
            mask = cert["raw_cycle_mask"]
            shift = cert["frobenius_shift"]
            sign = cert["sign_bit"]
            assert isinstance(ordinal, int) and (
                0 <= ordinal < (1 << (cell[
                    "nominal_window_dimension_d"] - 1)))
            assert mask == representative(
                ordinal, cell["nominal_window_dimension_d"])
            assert isinstance(shift, int) and 0 <= shift < n
            assert sign in (0, 1)
            raw = curve.pointFromX(onb_x_from_cycle_mask(
                mask, onb, orbit))
            assert raw is not None
            projected = curve.mul(raw, cell["cofactor"])
            assert projected is not None
            expected = curve.frob(projected, shift)
            if sign:
                expected = curve.neg(expected)
            assert expected == point
    for point in originals:
        assert curve.onCurve(point)
        assert curve.mul(point, cell["subgroup_order"]) is None
        assert canonical_rotation(orbit.cycle_bits(point[0]), n) in keys
    table_pair = curve.add(*table_points)
    query_pair = curve.add(*query_points)
    residual = curve.add(target, curve.neg(query_pair))
    assert table_pair is not None and residual is not None
    key0, exponent0, sign0 = orbit.canonical(table_pair)
    key1, exponent1, sign1 = orbit.canonical(residual)
    assert key0 == key1
    assert (exponent0, sign0) == (
        proof["table_pair_quotient_exponent"],
        proof["table_pair_quotient_sign"])
    assert (exponent1, sign1) == (
        proof["residual_quotient_exponent"],
        proof["residual_quotient_sign"])
    shift = (exponent0 - exponent1) % n
    sign = sign0 * sign1
    expected = [curve.frob(point, shift) for point in table_points]
    if sign < 0:
        expected = [curve.neg(point) for point in expected]
    expected += query_points
    actual = [tuple(row) for row in relation["points"]]
    assert actual == expected
    assert shift == relation["frobenius_shift_of_table_pair"]
    assert sign == relation["sign_of_table_pair"]
    columns = [orbit.canonical(point)[0] for point in actual]
    assert len(set(columns)) == 4
    assert columns == relation["folded_column_keys"]
    total = None
    for point in actual:
        assert canonical_rotation(orbit.cycle_bits(point[0]), n) in keys
        total = curve.add(total, point)
    assert total == target
    return {"status": "verified_four_point_relation",
            "four_distinct_columns": True,
            "subgroup_and_exact_base_membership_replayed": True}


def audit_one(case: str, protocol: dict) -> dict:
    cell = protocol["cases"][case]
    n = cell["degree_n"]
    receipt_path = HERE / "runs" / f"{case}.json"
    receipt = json.loads(receipt_path.read_text())
    assert receipt["proposal_id"] == "Q1488"
    assert receipt["candidate_id"] is receipt["run_id"] is None
    assert receipt["isogeny"] == "none"
    assert receipt["protocol_sha256"] == sha(PROTOCOL)
    runner_key = ("experiments/compact-s3-m4-20261003/"
                  "q1488_window_pair_table/run_stage.py")
    assert receipt["runner_source_sha256"] == protocol[
        "source_sha256"][runner_key]
    assert receipt["runtime_info_sha256"] == protocol[
        "runtime_info_sha256"]
    assert receipt["case"] == case
    assert receipt["stage_config_id"] == cell["stage_config_id"]
    assert receipt["stage_run_id"] == cell["stage_run_id"]
    assert receipt["workload_id"] == cell["workload_id"]
    assert receipt["matched_q1487_workload_id"] == cell[
        "matched_q1487_workload_id"]
    assert receipt["curve_id"] == cell["curve_id"]
    assert receipt["target"] == cell["public_target"]
    for name in ("factor_base_actual_B", "folded_columns_K",
                 "factor_base_enumerated_set_sha256", "factor_base_sampling"):
        assert receipt[name] == cell[name]
    assert receipt["verified_single_target_dlp"] is False
    assert receipt["complete_n131_log2_work"] is None
    assert receipt["natural_relation_yield_estimate"] is None
    assert receipt["challenge_run_admitted"] is False
    assert receipt["online_single_target_speedup"] is None
    assert receipt["cpu_isolation_receipt"] is None
    table = receipt["target_independent_table"]
    query = receipt["ordinary_query"]
    assert table["samples"] == cell["table_pair_sample_cap"]
    assert (table["distinct_keys"] + table["duplicate_keys"] +
            table["identity_pairs"]) == table["samples"]
    assert 0 <= query["samples"] <= cell["query_pair_sample_cap"]
    assert query["key_hits"] >= query["improper_column_rejections"]
    assert table["wall_ns"] >= 0 and query["wall_ns"] >= 0
    for stage, samples in ((table, table["samples"]),
                           (query, query["samples"])):
        sampler = stage["sampler"]
        assert sampler["accepted_points"] == 2 * samples
        if n == 53:
            assert sampler["indexed_draws"] == 2 * samples
        else:
            assert sampler["raw_orbit_draws"] == (
                sampler["nonrational_x"] +
                sampler["identity_projections"] +
                sampler["accepted_points"])
        assert all(value >= 0 for value in stage["curve_api_calls"].values())
        assert stage["curve_api_calls"]["add"] >= samples
    if query["status"] == "verified_four_point_relation":
        assert receipt["verified_relation_count"] == 1
        checked = replay_relation(n, cell, query["relation"])
    else:
        assert query["status"] in ("sample_cap", "wall_cap")
        assert receipt["verified_relation_count"] == 0
        assert query["relation"] is None
        checked = {"status": "no_relation_returned"}
    return {"case": case, "degree_n": n,
            "status": query["status"],
            "table_pair_samples": table["samples"],
            "query_pair_samples": query["samples"],
            "table_curve_api_calls": table["curve_api_calls"],
            "query_curve_api_calls": query["curve_api_calls"],
            "verified_relation_count": receipt["verified_relation_count"],
            "relation_check": checked,
            "receipt_sha256": sha(receipt_path)}


def audit() -> dict:
    protocol = json.loads(PROTOCOL.read_text())
    assert protocol["proposal_id"] == "Q1488"
    assert protocol["candidate_id"] is protocol["run_id"] is None
    assert protocol["isogeny"] == "none"
    assert protocol["challenge_run_admitted"] is False
    assert protocol["complete_n131_log2_work"] is None
    for relative, digest in protocol["source_sha256"].items():
        assert sha(ROOT / relative) == digest, relative
    for relative, digest in protocol["input_sha256"].items():
        assert sha(ROOT / relative) == digest, relative
    assert sha(HERE / "sage_runtime_info.json") == protocol[
        "runtime_info_sha256"]
    assert sha(HERE / "validation.json") == protocol[
        "validation_sha256"]
    q1482 = json.loads((PARENT /
        "q1482_window_s3/protocol.json").read_text())
    q1487 = json.loads((PARENT /
        "q1487_inverse_partner/protocol.json").read_text())
    for n in (53, 83):
        case = f"n{n}_ordinary"
        cell = protocol["cases"][case]
        base = json.loads((Q1481 / f"n{n}_d{cell['nominal_window_dimension_d']}"
                           "_base.json").read_text())
        assert cell["curve_id"] == base["curve_id"] == q1482[
            "cases"][case]["curve_id"] == q1487[
                "cases"][case]["curve_id"]
        assert cell["public_target"] == q1482["cases"][case][
            "public_target"] == q1487["cases"][case]["public_target"]
        assert cell["factor_base_actual_B"] == base[
            "actual_usable_points_B_before_folding"]
        assert cell["folded_columns_K"] == base[
            "signed_frobenius_columns_K"]
        assert cell["factor_base_enumerated_set_sha256"] == base[
            "enumerated_set_sha256"]
        canonical = json.dumps(cell["workload"], sort_keys=True,
                               separators=(",", ":"),
                               ensure_ascii=False).encode("utf-8")
        assert hashlib.sha256(canonical).hexdigest()[:12] == cell[
            "workload_id"]
    rows = [audit_one(case, protocol) for case in protocol["run_order"]]
    return {"kind": "q1488_matched_window_base_pair_table_archive_audit",
            "proposal_id": "Q1488", "candidate_id": None,
            "run_id": None, "isogeny": "none",
            "protocol_sha256": sha(PROTOCOL), "rows": rows,
            "ordinary_verified_relations": sum(
                row["verified_relation_count"] for row in rows),
            "natural_relation_yield_estimate": None,
            "complete_n131_log2_work": None,
            "challenge_run_admitted": False,
            "status": "passed"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    current = audit()
    if args.check:
        assert json.loads(OUT.read_text()) == current
    else:
        assert not OUT.exists(), "refuse overwrite"
        OUT.write_text(json.dumps(current, indent=2, sort_keys=True) +
                       "\n")
    print("Q1488 matched pair-table archive audit: PASS")

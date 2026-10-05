#!/usr/bin/env python3
"""Independently audit Q1445's frozen inputs and measured stage receipts."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "ecc2k130/codegen"))
import curves  # noqa: E402
import field  # noqa: E402

sys.path.insert(0, str(ROOT / "experiments/koblitz-pair-claw-20260929"))
from orbit_key import OrbitKey  # noqa: E402

PROTOCOL = HERE / "protocol.json"
OUTPUT = HERE / "verification.json"


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_n53_membership(points):
    material = json.loads((HERE / "n53_w4_points_receipt.json").read_text())
    data = (HERE / "n53_w4_points.bin").read_bytes()
    assert hashlib.sha256(data).hexdigest() == material["point_file_sha256"]
    width = 7
    assert len(data) == 2 * width * material["factor_base_actual_B"]
    onb = field.Onb(53)
    base = set()
    for i in range(0, len(data), 2 * width):
        x = int.from_bytes(data[i:i + width], "little")
        y = int.from_bytes(data[i + width:i + 2 * width], "little")
        base.add((onb.fromCoords(x), onb.fromCoords(y)))
    assert len(base) == material["factor_base_actual_B"]
    assert all(point in base for point in points)


def verify_n83_membership(curve, onb, originals, certificates, cofactor,
                          weight):
    assert len(originals) == len(certificates) == 4
    for point, certificate in zip(originals, certificates):
        assert isinstance(certificate, dict)
        mask = certificate["raw_normal_x_mask"]
        sign_bit = certificate["sign_bit"]
        assert isinstance(mask, int) and 1 <= mask < (1 << 83)
        assert 1 <= mask.bit_count() <= weight
        assert sign_bit in (0, 1)
        raw = curve.pointFromX(onb.fromCoords(mask))
        assert raw is not None
        projected = curve.mul(raw, cofactor)
        assert projected is not None
        expected = curve.neg(projected) if sign_bit else projected
        assert expected == point


def verify_relation(n, cell, relation):
    onb = field.Onb(n)
    curve = curves.Curve(onb)
    orbit = OrbitKey(onb)
    target = tuple(cell["public_target"])
    proof = relation["collision_proof"]
    table_points = [tuple(row) for row in proof["table_pair_original_points"]]
    query_points = [tuple(row) for row in proof["query_pair_original_points"]]
    originals = table_points + query_points
    if n == 53:
        verify_n53_membership(originals)
        assert proof["table_pair_membership_certificates"] == [None, None]
        assert proof["query_pair_membership_certificates"] == [None, None]
    else:
        verify_n83_membership(
            curve, onb, originals,
            proof["table_pair_membership_certificates"] +
            proof["query_pair_membership_certificates"],
            cell["cofactor"], cell["weight_bound"])
    zero_pair = curve.add(*table_points)
    one_pair = curve.add(*query_points)
    residual = curve.add(target, curve.neg(one_pair))
    assert zero_pair is not None and residual is not None
    key0, exponent0, sign0 = orbit.canonical(zero_pair)
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
    assert expected == actual
    assert shift == relation["frobenius_shift_of_table_pair"]
    assert sign == relation["sign_of_table_pair"]
    columns = [orbit.canonical(point)[0] for point in actual]
    assert len(set(columns)) == 4
    assert columns == relation["folded_column_keys"]
    if n == 53:
        verify_n53_membership(actual)
    total = None
    for point in actual:
        assert curve.onCurve(point)
        assert curve.mul(point, cell["subgroup_order"]) is None
        total = curve.add(total, point)
    assert total == target
    return {"status": "verified_four_point_relation",
            "four_distinct_columns": True,
            "subgroup_and_membership_replayed": True}


def verify_cell(n, protocol):
    cell = protocol["cells"][str(n)]
    receipt_path = HERE / f"runs/n{n}_ordinary.json"
    receipt = json.loads(receipt_path.read_text())
    assert receipt["proposal_id"] == "Q1445"
    assert receipt["candidate_id"] is None and receipt["run_id"] is None
    assert receipt["isogeny"] == "none"
    assert receipt["protocol_sha256"] == sha(PROTOCOL)
    assert receipt["curve_id"] == cell["curve_id"]
    assert receipt["workload_id"] == cell["workload_id"]
    assert receipt["target"] == cell["public_target"]
    for got, expected in (
        (receipt["factor_base_actual_B"], cell["factor_base_actual_B"]),
        (receipt["folded_columns_K"], cell["folded_columns_K"]),
        (receipt["factor_base_enumerated_set_sha256"],
         cell["factor_base_enumerated_set_sha256"]),
        (receipt["factor_base_sampling"], cell["factor_base_sampling"]),
    ):
        assert got == expected
    table = receipt["target_independent_table"]
    query = receipt["ordinary_query"]
    assert table["samples"] == cell["table_sample_cap"]
    assert (table["distinct_keys"] + table["duplicate_keys"] +
            table["identity_pairs"]) == table["samples"]
    assert 0 <= query["samples"] <= cell["query_sample_cap"]
    assert query["key_hits"] >= query["improper_column_rejections"]
    assert table["wall_ns"] >= 0 and query["wall_ns"] >= 0
    for stage, samples in ((table, cell["table_sample_cap"]),
                           (query, query["samples"])):
        sampler = stage["sampler"]
        assert sampler["accepted_points"] == 2 * samples
        if n == 83:
            assert (sampler["raw_x_draws"] == sampler["nonrational_x"] +
                    sampler["identity_projections"] +
                    sampler["accepted_points"])
        else:
            assert sampler["indexed_draws"] == sampler["accepted_points"]
    if query["status"] == "verified_four_point_relation":
        assert receipt["verified_relation_count"] == 1
        relation_check = verify_relation(n, cell, query["relation"])
    else:
        assert query["status"] in ("sample_cap", "wall_cap")
        assert receipt["verified_relation_count"] == 0
        assert query["relation"] is None
        relation_check = {"status": "no_relation_returned"}
    assert receipt["verified_single_target_dlp"] is False
    assert receipt["complete_n131_log2_work"] is None
    assert receipt["online_single_target_speedup"] is None
    assert receipt["cpu_isolation_receipt"] is None
    return {"degree": n, "status": query["status"],
            "verified_relation_count": receipt["verified_relation_count"],
            "relation_check": relation_check,
            "receipt_sha256": sha(receipt_path)}


def verify():
    protocol = json.loads(PROTOCOL.read_text())
    assert protocol["proposal_id"] == "Q1445"
    assert protocol["candidate_id"] is None
    assert protocol["isogeny"] == "none"
    assert protocol["challenge_run_admitted"] is False
    for name, digest in protocol["source_sha256"].items():
        assert sha(ROOT / name) == digest, name
    for name, digest in protocol["input_sha256"].items():
        assert sha(ROOT / name) == digest, name
    assert sha(HERE / "sage_runtime_info.json") == protocol[
        "sage_runtime_info_sha256"]
    q1438 = json.loads((PARENT / "q1438_dense_base/protocol.json").read_text())
    q1444 = json.loads((PARENT / "q1444_wdsat_adapter/protocol.json").read_text())
    for n in (53, 83):
        cell = protocol["cells"][str(n)]
        base = json.loads((PARENT / f"q1438_dense_base/n{n}_w"
                           f"{cell['weight_bound']}_base.json").read_text())
        assert cell["curve_id"] == q1438["instances"][str(n)]["curve_id"]
        assert cell["curve_id"] == q1444["cells"][f"n{n}_ordinary"]["curve_id"]
        assert cell["public_target"] == q1444["cells"][f"n{n}_ordinary"][
            "public_target"]
        assert cell["factor_base_actual_B"] == base[
            "actual_usable_points_B_before_folding"]
        assert cell["folded_columns_K"] == base["signed_frobenius_columns_K"]
        assert cell["factor_base_enumerated_set_sha256"] == base[
            "enumerated_set_sha256"]
        workload = cell["workload"]
        canonical = json.dumps(workload, sort_keys=True,
                               separators=(",", ":"),
                               ensure_ascii=False).encode("utf-8")
        assert hashlib.sha256(canonical).hexdigest()[:12] == cell["workload_id"]
    return {"proposal_id": "Q1445", "protocol_sha256": sha(PROTOCOL),
            "cells": [verify_cell(n, protocol) for n in (53, 83)],
            "complete_n131_log2_work": None,
            "challenge_run_admitted": False,
            "status": "pass"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    result = verify()
    if args.check:
        assert json.loads(OUTPUT.read_text()) == result
        print("Q1445 archive: PASS")
    else:
        assert not OUTPUT.exists(), "refuse overwrite"
        OUTPUT.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
        print(json.dumps({"status": "pass", "cells": result["cells"]},
                         sort_keys=True))

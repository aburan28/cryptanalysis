#!/usr/bin/env python3
"""Rebuild and independently replay the n=23 pair-claw IC receipt."""

import hashlib
import json
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CODEGEN = HERE.parents[1] / "ecc2k130" / "runner" / "codegen"
sys.path.insert(0, str(CODEGEN))

import curves
import field
import indexcalc


def frozen(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def sha(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def rank(rows, columns, order):
    matrix = [row[:] for row in rows]
    current = 0
    for column in range(columns):
        pivot = next((i for i in range(current, len(matrix))
                      if matrix[i][column] % order), None)
        if pivot is None:
            continue
        matrix[current], matrix[pivot] = matrix[pivot], matrix[current]
        inverse = pow(matrix[current][column], -1, order)
        matrix[current] = [x * inverse % order for x in matrix[current]]
        for i in range(current + 1, len(matrix)):
            factor = matrix[i][column]
            matrix[i] = [(a - factor * b) % order
                         for a, b in zip(matrix[i], matrix[current])]
        current += 1
    return current


def verify():
    path = HERE / "runs" / "n23_one_target.json"
    report = json.loads(path.read_text())
    source_hash = sha(HERE / "run_n23.py")
    assert report["source_sha256"] == source_hash
    for name, digest in report["dependency_sha256"].items():
        assert digest == sha(CODEGEN / name)
    assert report["proposal_id"] == "Q1036"
    identity = report["curve_identity_record"]
    curve_id = "EC1N23Ckb1h" + hashlib.sha256(frozen(identity)).hexdigest()[:12]
    assert report["curve_id"] == curve_id == "EC1N23Ckb1haed91d8afed0"
    assert identity["field"]["basis"] == "type_ii_optimal_normal"
    assert identity["field"]["n"] == 23
    assert report["isogeny"] == "none"
    assert report["workload_id"] == hashlib.sha256(frozen(
        report["workload"])).hexdigest()[:12]

    candidate_id = report["candidate_id"]
    candidate_path = HERE / "candidates" / f"{candidate_id}.json"
    candidate = json.loads(candidate_path.read_text())
    record = {key: value for key, value in candidate.items()
              if key not in ("candidate_id", "candidate_record_sha256")}
    candidate_hash = hashlib.sha256(frozen(record)).hexdigest()
    assert candidate_hash == candidate["candidate_record_sha256"]
    assert candidate_hash == report["candidate_record_sha256"]
    assert candidate_id == ("IC1N23Ckb1fb322PDP4clawRCwalkLAgauss"
                            f"TDdirectISO0h{candidate_hash[:12]}")
    assert report["run_id"] == f"{candidate_id}W{report['workload_id']}R1"
    assert candidate["curve"]["curve_id"] == curve_id
    assert candidate["isogeny"] == "none"

    onb = field.Onb(23)
    curve = curves.Curve(onb)
    order = identity["curve"]["subgroup_order"]
    assert curves.curveOrder(23) == identity["curve"]["order"] == 4 * order
    assert curves.isPrimeBig(order)
    generator = tuple(identity["curve"]["generator"])
    assert generator == curve.randomPointOfOrder(order, 4, random.Random(23))
    assert curve.mul(generator, order) is None

    # Rebuild the base from the mathematical policy, including every sign.
    points = set()
    rational = 0
    for support in indexcalc.combinationsUpTo(23, 2):
        if not support:
            continue
        x = onb.fromCoords(sum(1 << bit for bit in support))
        lifted = curve.pointFromX(x)
        if lifted is None:
            continue
        rational += 1
        projected = curve.mul(lifted, 4)
        if projected is not None:
            assert curve.mul(projected, order) is None
            points.add(projected)
            points.add(curve.neg(projected))
    base = report["factor_base"]
    assert rational == base["rational_x_coordinates"] == 161
    assert len(points) == base["actual_usable_points_B_before_folding"] == 322
    digest = hashlib.sha256()
    for x, y in sorted(points):
        digest.update(f"{x},{y}\n".encode())
    assert digest.hexdigest() == base["enumerated_set_sha256"]
    assert candidate["factor_base"] == base

    eigen = base["frobenius_eigenvalue_mod_r"]
    assert curve.mul(generator, eigen) == curve.frob(generator)
    labels = {}
    representatives = []
    for point in sorted(points):
        if point in labels:
            continue
        column = len(representatives)
        representatives.append(point)
        value, coefficient = point, 1
        for _ in range(23):
            for signed, coeff in ((value, coefficient),
                                  (curve.neg(value), -coefficient % order)):
                old = labels.get(signed)
                if old is not None:
                    assert old == (column, coeff)
                labels[signed] = (column, coeff)
            value = curve.frob(value)
            coefficient = coefficient * eigen % order
    assert len(labels) == 322
    assert len(representatives) == base["signed_frobenius_columns"] == 7
    assert [list(point) for point in representatives] == report["representatives"]

    def row_and_replay(result, target):
        relation = result["relation"]
        assert result["status"] == "verified_four_point_relation"
        assert relation is not None
        points4 = [tuple(point) for point in relation["points"]]
        assert len(points4) == 4 and all(point in labels for point in points4)
        assert all(points4[i] != curve.neg(points4[j])
                   for i in range(4) for j in range(i))
        first = relation["first_meta"]
        second = relation["second_meta"]
        assert first[0] != second[0]
        base_ordered = sorted(points)
        assert points4[:2] == [base_ordered[first[1]], base_ordered[first[2]]]
        assert points4[2:] == [base_ordered[second[1]], base_ordered[second[2]]]
        total = None
        for point in points4:
            total = curve.add(total, point)
        assert total == target
        row = [0] * 7
        for point in points4:
            column, coefficient = labels[point]
            row[column] = (row[column] + coefficient) % order
        return row

    rows, rhs = [], []
    alpha_rng = random.Random(report["workload"]["setup_alpha_seed"])
    for index, result in enumerate(report["relation_collection"]):
        alpha = alpha_rng.randrange(1, order)
        assert result["query_number"] == index + 1
        assert result["alpha"] == alpha
        query_target = curve.mul(generator, alpha)
        assert result["target"] == list(query_target)
        row = row_and_replay(result, query_target)
        assert row == result["relation_row"]
        novel = rank(rows + [row], 7, order) > len(rows)
        assert novel == result["novel_row"]
        if novel:
            rows.append(row)
            rhs.append(alpha)
    assert rows == report["matrix_rows"]
    assert rhs == report["matrix_rhs"]
    assert report["verified_relation_count"] == len(report["relation_collection"])
    assert report["novel_rows"] == report["final_rank"] == rank(rows, 7, order) == 7
    logs = report["representative_logs"]
    assert len(logs) == 7
    assert all(sum(a * b for a, b in zip(row, logs)) % order == alpha
               for row, alpha in zip(rows, rhs))
    assert all(curve.mul(generator, value) == point
               for value, point in zip(logs, representatives))

    target = tuple(report["workload"]["target"])
    assert all(result["target"] != list(target)
               for result in report["relation_collection"])
    target_row = row_and_replay(report["target_result"], target)
    assert target_row == report["target_relation_row"]
    scalar = sum(a * b for a, b in zip(target_row, logs)) % order
    assert scalar == report["recovered_scalar"]
    assert curve.mul(generator, scalar) == target
    assert scalar == report["fixture_scalar_validation_only"] == 987654
    assert report["verified_single_target_dlp"] is True
    assert report["online_one_target_wall_ns"] == sum(
        report["online_phase_wall_ns"].values())
    assert report["rho_online_wall_ns"] is None
    assert report["online_speedup"] is None
    return {"curve_id": curve_id, "candidate_id": candidate_id,
            "actual_B": 322, "columns": 7, "rank": 7,
            "recovered_scalar": scalar,
            "online_wall_ms": report["online_one_target_wall_ns"] / 1e6,
            "online_group_add_calls": report[
                "online_group_api_calls_including_replay_and_scalar_check"]["add"]}


if __name__ == "__main__":
    print(json.dumps(verify(), sort_keys=True))

#!/usr/bin/env python3
"""Independent Sage replay and complete N41 four-atom public-point census."""

import hashlib
import json
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
PRIOR = BASE / "n41_diagonal_double_norm_20261010"
GEOMETRY = BASE / "n41_two_free_pair_occupancy_20261009/geometry_snapshot.json"
R = 549756390943


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def point_key(point):
    return None if point.is_zero() else (int(point[0].to_integer()),
                                         int(point[1].to_integer()))


def main():
    p = json.loads((HERE / "protocol.json").read_text())
    inputs = json.loads((PRIOR / "input.json").read_text())
    positive = json.loads((HERE / "positive_result.json").read_text())
    public = json.loads((HERE / "public_result.json").read_text())
    monitor_public = json.loads((HERE / "public_monitor.json").read_text())
    assert p["status"] == "FROZEN_BEFORE_RUN"
    assert p["source_sha256"]["prior_input"] == sha(PRIOR / "input.json")
    assert p["source_sha256"]["geometry"] == sha(GEOMETRY)
    assert positive["status"] == public["status"] == "COMPLETE"
    assert monitor_public["status"] == "COMPLETE"
    assert monitor_public["worker_result_sha256"] == sha(HERE / "public_result.json")
    binary = PolynomialRing(GF(2), "t")
    t = binary.gen()
    f = GF(2**41, "a", modulus=t**41+t**3+1)
    curve = EllipticCurve(f, [1, 0, 0, 0, 1])
    source = json.loads(GEOMETRY.read_text())["n41"]
    basis_w = source["window_basis_w"][0]
    basis_u = source["window_basis_halftrace"][0]
    source_rows = source["point_rows_by_unique_rotation"]["0"]
    source_points = {(row[3], row[5]): curve(f.from_integer(row[0]), f.from_integer(row[1]))
                     for row in source_rows}
    columns = {row[3]: row[2] for row in source_rows}
    assert len(source_points) == 64 and len(columns) == 32

    def frob(point, power):
        if point.is_zero():
            return point
        x, y = point[0], point[1]
        for _ in range(power):
            x, y = x**2, y**2
        return curve(x, y)

    def coordinate(basis, mask):
        result = f.zero()
        for i, value in enumerate(basis):
            if mask >> i & 1:
                result += f.from_integer(value)
        return result

    states = []
    for rotation in [20, 30]:
        slot = {}
        for (mask, sign), projected in sorted(source_points.items()):
            w = coordinate(basis_w, mask)
            u = coordinate(basis_u, mask)
            assert u**2+u == w and w != 0
            raw_x = 1 + 1/u
            options = [point for point in curve.lift_x(raw_x, all=True)
                       if 4*point == projected]
            assert len(options) == 1
            raw = frob(options[0], rotation)
            atom = raw + frob(raw, 1)
            assert not atom.is_zero() and atom[0] == 1/(w**(2**rotation))
            assert R*(4*atom) == curve(0)
            slot[(mask, sign)] = atom
        states.append(slot)
    projected_union = {point_key(4*atom) for slot in states for atom in slot.values()}
    assert len(projected_union) == 128

    pairs = []
    for slot in states:
        rows = sorted(slot.items())
        pair_rows = []
        for i, ((mask_a, sign_a), a) in enumerate(rows):
            for (mask_b, sign_b), b in rows[i+1:]:
                if columns[mask_a] == columns[mask_b]:
                    continue
                total = a+b
                assert not total.is_zero() and total[0] != 0
                pair_rows.append({"point": total,
                                  "masks": [mask_a, mask_b],
                                  "signs": [sign_a, sign_b],
                                  "columns": [columns[mask_a], columns[mask_b]]})
        assert len(pair_rows) == 1956
        pairs.append(pair_rows)

    positive_hit = next(hit for lift in positive["lifts"]
                        for hit in lift["bucket_pair_hits"]
                        if hit["exact_witness"] is not None)
    witness = positive_hit["exact_witness"]
    left = sum((states[0][(m, s)] for m, s in zip(witness["left_masks"],
                                                   witness["left_signs"])), curve(0))
    right = sum((states[1][(m, s)] for m, s in zip(witness["right_masks"],
                                                    witness["right_signs"])), curve(0))
    raw_total = left + right
    assert point_key(left) == tuple(witness["left_point"])
    assert point_key(right) == tuple(witness["right_point"])
    assert point_key(raw_total) == tuple(inputs["positive_raw_sum"])
    assert point_key(4*raw_total) == tuple(inputs["positive_subgroup_target"])
    assert len(set(witness["columns"])) == 4

    public_q = curve(*(f.from_integer(x) for x in inputs["public_subgroup_target"]))
    assert R*public_q == curve(0)
    core = pow(4, -1, R)*public_q
    torsion = curve(f.one(), f.zero())
    lifts = [core+i*torsion for i in range(4)]
    traces = [int((1/point[0]).trace()) for point in lifts]
    assert traces == [0, 1, 0, 1]
    assert all((1/row["point"][0]).trace() == 0 for side in pairs for row in side)
    left_index = {}
    for row in pairs[0]:
        left_index.setdefault(point_key(row["point"]), []).append(row)
    checked_pairs = 0
    exact_public_hits = 0
    for index in (0, 2):
        target = lifts[index]
        for row in pairs[1]:
            needed = target - row["point"]
            for left_row in left_index.get(point_key(needed), []):
                checked_pairs += 1
                if len(set(left_row["columns"]+row["columns"])) == 4:
                    exact_public_hits += 1
    assert exact_public_hits == 0
    assert all(lift["global_common_degree"] == 0 for lift in public["lifts"])
    result = {"status": "PASS", "candidate_id": None,
              "curve_id": source["curve_id"], "public_target": inputs["public_subgroup_target"],
              "actual_base_points_B": len(projected_union),
              "folded_columns_K": len(set(columns.values())),
              "pair_states_per_side": [len(rows) for rows in pairs],
              "positive_raw_sum": list(point_key(raw_total)),
              "positive_distinct_columns": len(set(witness["columns"])),
              "public_lift_reciprocal_traces": traces,
              "public_exact_group_hits": exact_public_hits,
              "public_pair_sum_coordinate_matches_before_column_filter": checked_pairs,
              "source_sha256": sha(Path(__file__)),
              "geometry_sha256": sha(GEOMETRY),
              "positive_result_sha256": sha(HERE / "positive_result.json"),
              "public_result_sha256": sha(HERE / "public_result.json"),
              "public_monitor_sha256": sha(HERE / "public_monitor.json")}
    with (HERE / "sage_audit.json").open("x") as out:
        json.dump(result, out, sort_keys=True, indent=2)
        out.write("\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

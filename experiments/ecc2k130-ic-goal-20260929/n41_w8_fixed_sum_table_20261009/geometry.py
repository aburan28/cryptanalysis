#!/usr/bin/env python3
"""Exact W8 fixed-sum pair domains on seven Frobenius rotations."""

import hashlib
import json
import random
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
GOAL = HERE.parent
sys.path.insert(0, str(GOAL))
import run_n41_disjoint_s5_sat as source

BASIS = GOAL / "n41_lowpower_w8_s6/basis8.json"
POINTS = GOAL / "n41_lowpower_w8_s6/native_input.txt"
PUBLIC = GOAL / "n41_adjacent_pairpair/public_target.json"
ROTATIONS = (0, 6, 12, 18, 24, 30, 36)
SEED_SUM = 56
R = 549756390943


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def frob(field, value, count):
    for _ in range(count):
        value = field.mul(value, value)
    return value


def point_frob(field, point, count):
    return tuple(frob(field, value, count) for value in point)


def aval(field, value):
    return field.mul(value, value) ^ value


def rank(words):
    pivots = {}
    for value in words:
        while value:
            lead = value.bit_length() - 1
            if lead not in pivots:
                pivots[lead] = value
                break
            value ^= pivots[lead]
    return len(pivots)


def read_source():
    basis = json.loads(BASIS.read_text())
    if (basis["curve_id"] != "EC1N41Ckb1h7d5e80d3c4d0" or
            basis["dimension_per_summand"] != 8):
        raise ValueError("frozen W8 basis changed")
    lines = POINTS.read_text().splitlines()
    header = list(map(int, lines[0].split()))
    if header[:3] != [1458168294740, 1672312028033, R]:
        raise ValueError("frozen public point changed")
    count = int(lines[1])
    if count != 250:
        raise ValueError("frozen W8 source count changed")
    rows = [list(map(int, line.split())) for line in lines[2:2+count]]
    if len(rows) != 250 or any(len(row) != 6 or row[4] != 0 for row in rows):
        raise ValueError("frozen source row encoding changed")
    return basis["basis_halftrace_by_unique_rotation"][0], rows


def main():
    output = HERE / "geometry.json"
    if output.exists():
        raise FileExistsError(output)
    started = time.monotonic_ns()
    field = source.Field(41, [0, 3])
    curve = source.Curve(field, 0)
    basis, rows = read_source()
    public = json.loads(PUBLIC.read_text())
    if public["curve_id"] != "EC1N41Ckb1h7d5e80d3c4d0":
        raise ValueError("public curve identity changed")
    grouped = {}
    for x, y, col, mask, branch, sign in rows:
        grouped.setdefault(mask, []).append((sign, (x, y), col))
    if len(grouped) != 125 or any(len(row) != 2 for row in grouped.values()):
        raise ValueError("W8 usable mask geometry changed")
    columns = {mask: values[0][2] for mask, values in grouped.items()}
    if len(set(columns.values())) != 117:
        raise ValueError("W8 folded column count changed")
    raw = {}
    for mask, values in grouped.items():
        u = source.coordinate(basis, mask)
        if u in (0, 1):
            raise ValueError("exceptional source phi")
        x = field.inv(u) ^ 1
        lifts = source.points_with_x(curve, x)
        for sign, projected, col in values:
            hits = [point for point in lifts if curve.mul(4, point) == projected]
            if len(hits) != 1 or curve.mul(R, projected) is not None:
                raise ValueError("source raw lift or subgroup failed")
            raw[(mask, sign)] = hits[0]
    permitted = [a for a in sorted(grouped) if (b := a ^ SEED_SUM) in grouped
                 and a < b and columns[a] != columns[b]]
    if len(permitted) != 40:
        raise ValueError("fixed-sum pair count changed")
    active_masks = set(permitted) | {a ^ SEED_SUM for a in permitted}
    active_columns = {columns[mask] for mask in active_masks}
    if len(active_masks) != 80 or len(active_columns) != 77:
        raise ValueError("fixed-sum usable base geometry changed")
    sval = source.coordinate(basis, SEED_SUM)
    product_basis = []
    for v in basis:
        av = aval(field, v)
        product_basis.append(field.mul(av, av) ^ field.mul(aval(field, sval), av))
    if rank(product_basis) != 7:
        raise ValueError("fixed-sum product map lost rank seven")
    blocks = []
    union_points = set()
    for rotation in ROTATIONS:
        rotated_basis = [frob(field, v, rotation) for v in basis]
        rotated_s = frob(field, sval, rotation)
        rotated_product = [frob(field, v, rotation) for v in product_basis]
        states = []
        for a in permitted:
            b = a ^ SEED_SUM
            found_z = set()
            for sign_a in (0, 1):
                for sign_b in (0, 1):
                    pa = point_frob(field, raw[(a, sign_a)], rotation)
                    pb = point_frob(field, raw[(b, sign_b)], rotation)
                    total = curve.add(pa, pb)
                    if total is None or total[0] == 1:
                        raise ValueError("exceptional fixed-sum pair output")
                    z = field.inv(total[0] ^ 1)
                    au = source.coordinate(rotated_basis, a)
                    bu = source.coordinate(rotated_basis, b)
                    if (au ^ bu != rotated_s or
                            field.mul(aval(field, z),
                                      field.mul(aval(field, au), aval(field, bu)))
                            != field.mul(rotated_s ^ z, rotated_s ^ z)):
                        raise ValueError("fixed-sum S3 identity failed")
                    projected = curve.mul(4, total)
                    if projected is None or curve.mul(R, projected) is not None:
                        raise ValueError("pair output failed subgroup test")
                    states.append({"a": a, "b": b, "sign_a": sign_a,
                                   "sign_b": sign_b, "z": z,
                                   "raw_sum": list(total),
                                   "projected_sum": list(projected),
                                   "columns": [columns[a], columns[b]]})
                    found_z.add(z)
                    union_points.add(curve.mul(4, pa))
                    union_points.add(curve.mul(4, pb))
            if len(found_z) != 2:
                raise ValueError("pair S3 roots did not form two x values")
        if len(states) != 160:
            raise ValueError("rotated fixed-sum state count changed")
        blocks.append({"rotation": rotation, "s": rotated_s,
                       "basis": rotated_basis, "product_basis": rotated_product,
                       "states": states})
    rng = random.Random(20261009174000)
    control = None
    for _ in range(100000):
        picked = [rng.choice(block["states"]) for block in blocks]
        cols = [col for row in picked for col in row["columns"]]
        if len(set(cols)) == len(cols):
            total = None
            for row in picked:
                total = curve.add(total, tuple(row["raw_sum"]))
            if total is not None and total[0] not in (0, 1):
                control = {"raw_target": list(total),
                           "subgroup_target": list(curve.mul(4, total)),
                           "states": picked}
                break
    if control is None:
        raise ValueError("no seven-pair distinct-column control in seeded draws")
    result = {"status": "EXACT_FIXED_SUM_GEOMETRY", "proposal_id": "Q20261009174000",
              "candidate_id": None, "run_id": None,
              "curve_id": public["curve_id"], "field_modulus": "t^41+t^3+1",
              "subgroup_order": R, "source_dimension": 8,
              "fixed_seed_sum_code": SEED_SUM, "permitted_mask_pairs": len(permitted),
              "permitted_canonical_a": permitted,
              "rotations": list(ROTATIONS), "folded_columns_K": 77,
              "source_folded_columns_before_fixed_sum": 117,
              "active_mask_count_per_rotation": len(active_masks),
              "actual_usable_base_points_B": len(union_points),
              "pair_states_per_block": 160, "pair_x_outputs_per_block": 80,
              "product_map_rank": 7, "mask_columns": columns,
              "blocks": blocks, "positive_control": control,
              "source_sha256": {"geometry.py": sha(__file__),
                                "basis8.json": sha(BASIS),
                                "native_input.txt": sha(POINTS),
                                "public_target.json": sha(PUBLIC)},
              "construction_wall_ns": time.monotonic_ns() - started}
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: result[key] for key in
                      ("status", "permitted_mask_pairs", "pair_states_per_block",
                       "actual_usable_base_points_B", "construction_wall_ns")}))


if __name__ == "__main__":
    main()

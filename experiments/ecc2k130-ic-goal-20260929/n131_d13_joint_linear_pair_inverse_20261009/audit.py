#!/usr/bin/env sage -python
"""Independent Sage rank and group replay for the joint d13 pair inverse."""

import hashlib
import json
import statistics
import sys
from pathlib import Path

from sage.all import GF, matrix, vector

HERE = Path(__file__).resolve().parent
GOAL = HERE.parent
BASE = GOAL / "n131_d13_batched_pair_inverse_20261009"
SOURCE = GOAL / "n131_d13_same_rotation_pairs_20261009"
CODEGEN = HERE.parents[2] / "ecc2k130/codegen"
sys.path.insert(0, str(CODEGEN))
import curves
import field


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def phi(onb, basis, code):
    mask = 0
    for bit, value in enumerate(basis):
        if (code >> bit) & 1:
            mask ^= value
    return onb.fromCoords(mask)


def output_mask(onb, point):
    if point is None or point[0] == onb.one():
        return None
    return onb.toCoords(onb.inv(onb.add(point[0], onb.one())))


def main():
    output = HERE / "audit.json"
    if output.exists():
        raise FileExistsError(output)
    protocol_path, result_path = HERE / "protocol.json", HERE / "result.json"
    protocol, result = json.loads(protocol_path.read_text()), json.loads(result_path.read_text())
    if (protocol["status"] != "FROZEN" or result["status"] != "PASS_EXACT_MATCH" or
            result["source_sha256"]["protocol"] != sha(protocol_path)):
        raise ValueError("frozen source or result changed")
    paths = {"run": HERE / "run.py", "audit": HERE / "audit.py",
             "freeze": HERE / "freeze.py", "field": CODEGEN / "field.py",
             "base_run": BASE / "run.py", "base_protocol": BASE / "protocol.json",
             "base_result": BASE / "result.json",
             "dual_run": GOAL / "n131_d13_syndrome_pair_inverse_20261009/run.py",
             "dual_result": GOAL / "n131_d13_syndrome_pair_inverse_20261009/result.json",
             "source_run": SOURCE / "run.py", "source_result": SOURCE / "result.json",
             "pivots": SOURCE / "pivots.bin",
             "valid_codes": SOURCE / "valid_codes.json",
             "runtime": HERE / "runtime_info.json"}
    if any(sha(path) != protocol["source_sha256"][name]
           for name, path in paths.items()):
        raise ValueError("frozen dependency digest changed")
    base_protocol = json.loads((BASE / "protocol.json").read_text())
    old = json.loads((BASE / "result.json").read_text())
    inputs = protocol["inputs"]
    if inputs[:64] != base_protocol["inputs"] or len(inputs) != 72:
        raise ValueError("frozen input sequence changed")
    if [item["pairs"] for item in result["input_pair_results"][:64]] != \
            [item["pairs"] for item in old["input_pair_results"]]:
        raise ValueError("joint inverse differs from prior group-replayed outputs")
    onb = field.Onb(131)
    curve = curves.Curve(onb)
    basis = [int(mask, 16) for mask in protocol["basis_masks_hex"]]
    A = lambda value: onb.add(onb.sqr(value), value)
    values = [onb.fromCoords(mask) for mask in basis]
    squares = [onb.sqr(value) for value in values]
    transformed = [A(value) for value in values]
    products = [onb.mul(transformed[i], transformed[j])
                for i in range(13) for j in range(i, 13)]
    product_matrix = matrix(GF(2), 131, 91,
                            lambda row, col: (onb.toCoords(products[col]) >> row) & 1)
    if product_matrix.rank() != 91:
        raise ValueError("independent Sage product rank differs")
    rank_checks = pair_replays = 0
    for i, item in enumerate(inputs):
        saved = result["input_pair_results"][i]
        if (saved["input_index"] != i or saved["kind"] != item["kind"] or
                saved["z_mask"] != item["z_mask"]):
            raise ValueError("saved input detail changed")
        if item["kind"] == "exceptional":
            if saved["joint_detail"]["status"] != "EXCEPTIONAL_EMPTY":
                raise ValueError("exceptional coordinate branch changed")
            continue
        z = onb.fromCoords(item["z_mask"])
        az = A(z)
        columns = [onb.toCoords(value) for value in squares]
        columns += [onb.toCoords(onb.mul(az, value)) for value in products]
        mat = matrix(GF(2), 131, 104,
                     lambda row, col: (columns[col] >> row) & 1)
        rank = mat.rank()
        if rank != saved["joint_detail"]["rank"]:
            raise ValueError("Sage combined rank differs")
        if item["kind"] == "constructed_rank_drop":
            if (rank >= 104 or rank != item["expected_rank"] or
                    saved["joint_detail"]["status"] != "RANK_FALLBACK"):
                raise ValueError("constructed rank-drop control missed fallback")
        if item["kind"] == "positive":
            if rank != 104 or tuple(item["pair"]) not in [tuple(p) for p in saved["pairs"]]:
                raise ValueError("positive output lost its unique-sum witness")
            coefficients = mat.solve_right(vector(GF(2),
                [(onb.toCoords(onb.sqr(z)) >> row) & 1 for row in range(131)]))
            sum_code = sum(int(coefficients[bit]) << bit for bit in range(13))
            if sum_code != (item["pair"][0] ^ item["pair"][1]) or \
                    sum_code != saved["joint_detail"]["sum"]:
                raise ValueError("Sage seed-sum solution differs")
        for a, b in saved["pairs"]:
            points = []
            for code in (a, b):
                value = phi(onb, basis, code)
                point = curve.pointFromX(onb.add(onb.inv(value), onb.one()))
                if point is None or curve.mul(point, 4) is None:
                    raise ValueError("accepted code lacks subgroup-usable point")
                points.append(point)
            outputs = {output_mask(onb, curve.add(points[0], points[1])),
                       output_mask(onb, curve.add(points[0], curve.neg(points[1])))}
            if item["z_mask"] not in outputs:
                raise ValueError("accepted pair does not sum to proposed output")
            pair_replays += 1
        rank_checks += 1
    raw = result["raw"]
    if len(raw) != 2 * 72 * 2:
        raise ValueError("timing row count changed")
    cells = {(row["repetition"], row["input_index"], row["method"]): row for row in raw}
    if len(cells) != len(raw):
        raise ValueError("duplicate timing cell")
    ratios = []
    for rep in range(2):
        for i in range(72):
            old_row, new_row = cells[(rep, i, "syndrome8")], cells[(rep, i, "joint_linear")]
            if (old_row["pair_count"] != new_row["pair_count"] or
                    new_row["pair_count"] != len(result["input_pair_results"][i]["pairs"]) or
                    old_row["wall_ns"] <= 0 or new_row["wall_ns"] <= 0):
                raise ValueError("paired timing cell changed")
            ratios.append(old_row["wall_ns"] / new_row["wall_ns"])
    if statistics.median(ratios) != result["paired_syndrome_over_joint"]["median"]:
        raise ValueError("paired median differs from raw cells")
    receipt = {"kind": "n131_d13_joint_linear_pair_inverse_audit",
               "status": "PASS_SAGE_RANK_AND_GROUP_REPLAY", "candidate_id": None,
               "run_id": None, "product_rank": 91,
               "combined_rank_checks": rank_checks,
               "group_pairs_replayed": pair_replays,
               "timing_rows_checked": len(raw),
               "source_sha256": {"protocol": sha(protocol_path),
                                 "result": sha(result_path),
                                 "audit": sha(Path(__file__))}}
    output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": receipt["status"],
                      "rank_checks": rank_checks,
                      "group_pairs_replayed": pair_replays}))


if __name__ == "__main__":
    main()

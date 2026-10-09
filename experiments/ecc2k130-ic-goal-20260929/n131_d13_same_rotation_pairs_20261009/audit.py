#!/usr/bin/env sage -python
"""Independently replay the complete N131 known-sum pivot index and controls."""

import hashlib
import json
import random
import struct
import sys
from pathlib import Path

from sage.all import GF, matrix, vector

HERE = Path(__file__).resolve().parent
GOAL = HERE.parent
STATIC = GOAL / "n131_phi_torsion_frobenius_domains_20261005/m12_d13_static"
PIPELINE = GOAL / "n131_phi_torsion_frobenius_domains_20261005/m12_d13_full_pipeline"
CODEGEN = GOAL.parents[1] / "ecc2k130/codegen"
sys.path.insert(0, str(CODEGEN))
import curves
import field

N, DIM, DOMAIN = 131, 13, 8192
HEADER = struct.Struct("<8sHBB")


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def phi(onb, basis, code):
    coordinate = 0
    for bit in range(DIM):
        if (code >> bit) & 1:
            coordinate ^= basis[bit]
    return onb.fromCoords(coordinate)


def t(onb, value):
    return onb.add(onb.sqr(value), value)


def point(onb, curve, basis, code):
    value = phi(onb, basis, code)
    return curve.pointFromX(onb.add(onb.inv(value), onb.one()))


def output_mask(onb, total):
    if total is None or total[0] == onb.one():
        return None
    return onb.toCoords(onb.inv(onb.add(total[0], onb.one())))


def read_index(path):
    pivots = []
    with path.open("rb") as stream:
        if HEADER.unpack(stream.read(HEADER.size)) != (b"D13PIV1\0", DOMAIN, N, DIM):
            raise ValueError("cached index header changed")
        for s in range(DOMAIN):
            width = stream.read(1)
            if len(width) != 1 or width[0] != (0 if s == 0 else 12):
                raise ValueError("cached rank differs from exact contract")
            rows = []
            for _ in range(width[0]):
                data = stream.read(20)
                if len(data) != 20:
                    raise ValueError("truncated cached pivot")
                rows.append((data[0], int.from_bytes(data[1:18], "little"),
                             int.from_bytes(data[18:20], "little")))
            pivots.append(rows)
        if stream.read(1):
            raise ValueError("cached index has trailing data")
    return pivots


def solve_rows(rows, rhs):
    code = 0
    for leading, pivot, combo in rows:
        if (rhs >> leading) & 1:
            rhs ^= pivot
            code ^= combo
    return code if rhs == 0 else None


def full_scan(onb, basis, pivots, valid_set, z_mask):
    z = onb.fromCoords(z_mask)
    zfactor = t(onb, z)
    if zfactor == 0:
        return []
    reciprocal = onb.inv(zfactor)
    z_square = onb.sqr(z)
    found = set()
    for s in range(1, DOMAIN):
        sum_square = onb.sqr(phi(onb, basis, s))
        right = onb.mul(onb.add(sum_square, z_square), reciprocal)
        code = solve_rows(pivots[s], onb.toCoords(right))
        if code is None:
            continue
        other = code ^ s
        if code in valid_set and other in valid_set and code != other:
            found.add(tuple(sorted((code, other))))
    return sorted(found)


def main():
    output = HERE / "audit.json"
    if output.exists():
        raise FileExistsError(output)
    protocol_path, result_path = HERE / "protocol.json", HERE / "result.json"
    protocol = json.loads(protocol_path.read_text())
    result = json.loads(result_path.read_text())
    geometry_path = STATIC / "d13_exact_geometry_v1.json"
    manifest_path = PIPELINE / "d13_m12_candidate_manifest_v1.json"
    valid_path, index_path = HERE / "valid_codes.json", HERE / "pivots.bin"
    if (protocol["status"] != "FROZEN" or
            result["status"] != "PASS_EXACT_PAIR_INVERSE_CONTROLS" or
            result["source_sha256"]["protocol"] != sha(protocol_path) or
            result["source_sha256"]["valid_codes"] != sha(valid_path) or
            result["source_sha256"]["pivots"] != sha(index_path) or
            protocol["source_sha256"]["geometry"] != sha(geometry_path) or
            protocol["source_sha256"]["manifest"] != sha(manifest_path) or
            protocol["source_sha256"]["run"] != sha(HERE / "run.py") or
            protocol["source_sha256"]["runtime"] != sha(HERE / "runtime_info.json")):
        raise ValueError("frozen source or result digest changed")
    geometry = json.loads(geometry_path.read_text())
    basis = [int(value, 16)
             for value in geometry["domain"]["basis_coordinate_masks_hex"]]
    onb = field.Onb(N)
    curve = curves.Curve(onb)
    valid = json.loads(valid_path.read_text())
    if len(valid) != 4134 or len(set(valid)) != 4134 or valid != sorted(valid):
        raise ValueError("saved selector list is not exact and sorted")
    independent_valid = []
    for code in range(1, DOMAIN):
        lifted = point(onb, curve, basis, code)
        if lifted is not None and curve.mul(lifted, 4) is not None:
            independent_valid.append(code)
    if independent_valid != valid:
        raise ValueError("independent selector enumeration differs")
    valid_set = set(valid)
    all_rows = read_index(index_path)
    abase = [t(onb, onb.fromCoords(value)) for value in basis]
    rank_checks = 0
    for s in range(1, DOMAIN):
        sum_factor = t(onb, phi(onb, basis, s))
        columns = [onb.toCoords(onb.add(onb.sqr(value),
                                        onb.mul(sum_factor, value)))
                   for value in abase]
        rows = all_rows[s]
        leadings = [leading for leading, _, _ in rows]
        if leadings != sorted(set(leadings), reverse=True):
            raise ValueError("cached pivots are not in descending row-echelon order")
        for leading, word, combo in rows:
            reconstructed = 0
            for bit, column in enumerate(columns):
                if (combo >> bit) & 1:
                    reconstructed ^= column
            if (word != reconstructed or word.bit_length() - 1 != leading or
                    combo <= 0 or combo >= DOMAIN):
                raise ValueError("cached row differs from exact field product")
            rank_checks += 1
        kernel_word = 0
        for bit, column in enumerate(columns):
            if (s >> bit) & 1:
                kernel_word ^= column
        if kernel_word:
            raise ValueError("swap direction is not the full map kernel")

    sage_matrix_sums = sorted({item["sum_code"] for item in result["positive_controls"]})[:16]
    for s in sage_matrix_sums:
        factor = t(onb, phi(onb, basis, s))
        columns = [onb.toCoords(onb.add(onb.sqr(value), onb.mul(factor, value)))
                   for value in abase]
        mat = matrix(GF(2), N, DIM,
                     lambda row, col: (columns[col] >> row) & 1)
        kernel = mat.right_kernel()
        if mat.rank() != 12 or kernel.dimension() != 1:
            raise ValueError("independent Sage matrix lost rank twelve")
        generator = next(iter(kernel.basis()))
        kernel_code = sum(int(generator[bit]) << bit for bit in range(DIM))
        if kernel_code != s:
            raise ValueError("independent Sage kernel is not pair swapping")

    for item in result["positive_controls"]:
        a, b = item["codes"]
        s, z_mask = item["sum_code"], item["output_phi_mask"]
        if a not in valid_set or b not in valid_set or a ^ b != s:
            raise ValueError("positive control escaped valid pair domain")
        left, right = point(onb, curve, basis, a), point(onb, curve, basis, b)
        roots = {output_mask(onb, curve.add(left, right)),
                 output_mask(onb, curve.add(left, curve.neg(right)))}
        if z_mask not in roots:
            raise ValueError("positive output differs from exact curve addition")
    positive = full_scan(onb, basis, all_rows, valid_set,
                         result["full_inverse_positive_output_phi_mask"])
    negative = full_scan(onb, basis, all_rows, valid_set,
                         result["full_inverse_negative_output_phi_mask"])
    if (positive != [tuple(pair) for pair in result["full_inverse_positive_pairs"]] or
            negative != [tuple(pair) for pair in result["full_inverse_negative_pairs"]]):
        raise ValueError("independent full-index pair membership differs")
    if result["unordered_distinct_pair_descriptors"] != 8542911:
        raise ValueError("pair descriptor count changed")
    receipt = {"kind": "n131_d13_same_rotation_pair_inverse_independent_audit",
               "status": "PASS_FULL_INDEX_AND_GROUP_REPLAY",
               "candidate_id": None, "run_id": None,
               "valid_codes_reenumerated": len(valid),
               "nonzero_seed_sums_checked": DOMAIN - 1,
               "pivot_rows_checked": rank_checks,
               "sage_gf2_matrices_checked": len(sage_matrix_sums),
               "positive_group_outputs_checked": len(result["positive_controls"]),
               "full_positive_pairs": [list(pair) for pair in positive],
               "full_negative_pairs": [list(pair) for pair in negative],
               "source_sha256": {"protocol": sha(protocol_path),
                                 "result": sha(result_path),
                                 "valid_codes": sha(valid_path),
                                 "pivots": sha(index_path),
                                 "audit": sha(Path(__file__))}}
    output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": receipt["status"],
                      "pivot_rows_checked": rank_checks,
                      "sage_matrices": len(sage_matrix_sums)}))


if __name__ == "__main__":
    main()

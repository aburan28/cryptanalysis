"""Exact fixed-first-pair N131 W15 four-atom affine-rank witness."""

import argparse
import hashlib
import json
import time
from pathlib import Path

import sys

HERE = Path(__file__).resolve().parent
GOAL = HERE.parent
sys.path.insert(0, str(GOAL / "n131_w15_basis_aware_fivepair_20261011"))
from arith_control import N, MODULUS, frob, half_trace, mul, square, trace  # noqa: E402

SEEDWISE = GOAL / "n131_w15_seedwise_fouratom_20261011"
INPUT = GOAL / "n131_w14_coupled_sixpair_sat_20261010/control.json"
POSITIVE = SEEDWISE / "protocol.json"
SUPPORT = GOAL / "n131_w15_coupled_sixpair_20261010/support_w15.tsv"
MAX_RIGHT = 512


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, obj):
    Path(path).write_text(json.dumps(obj, sort_keys=True, indent=2) + "\n")


def source_paths():
    return {"run.py": HERE / "run.py",
            "arith_control.py": GOAL / "n131_w15_basis_aware_fivepair_20261011/arith_control.py",
            "table.tsv": SEEDWISE / "table.tsv",
            "prepare_receipt.json": SEEDWISE / "prepare_receipt.json",
            "input.json": INPUT, "positive_protocol.json": POSITIVE,
            "support_w15.tsv": SUPPORT}


def inverse(a):
    assert a
    u, v, g1, g2 = a, MODULUS, 1, 0
    while u != 1:
        shift = u.bit_length() - v.bit_length()
        if shift < 0:
            u, v = v, u
            g1, g2 = g2, g1
            shift = -shift
        u ^= v << shift
        g1 ^= g2 << shift
    while g1.bit_length() > N:
        g1 ^= MODULUS << (g1.bit_length() - N - 1)
    assert mul(a, g1) == 1
    return g1


def s3_roots(c, d):
    cd = mul(c, d)
    A, B, C = 1 ^ square(cd), cd, square(c ^ d)
    if A == 0:
        if B == 0:
            return [] if C else [0]
        roots = [mul(C, inverse(B))]
    elif B == 0:
        roots = [frob(mul(C, inverse(A)), N - 1)]
    else:
        inv_A, inv_B = inverse(A), inverse(B)
        rhs = mul(mul(A, C), square(inv_B))
        if trace(rhs):
            return []
        root = mul(mul(B, inv_A), half_trace(rhs))
        roots = [root, root ^ mul(B, inv_A)]
    assert all(mul(A, square(z)) ^ mul(B, z) ^ C == 0 for z in roots)
    return [z for z in roots if z != 0]


def table():
    return [tuple(map(int, line.split())) for line in
            (SEEDWISE / "table.tsv").read_text().splitlines()]


def freeze():
    data = json.loads(INPUT.read_text())
    positive = json.loads(POSITIVE.read_text())
    prep = json.loads((SEEDWISE / "prepare_receipt.json").read_text())
    rows = table()
    c = data["middle_reciprocals"][2]
    d = data["middle_reciprocals"][3]
    assert prep["seed_mask"] == 13686 and prep["rotation"] == 26
    assert len(rows) == prep["distinct_pair_outputs"]
    assert any(row[0] == c and {row[1], row[2]} == {5576, 8382} for row in rows)
    assert any(frob(row[0], 13) == d and {row[1], row[2]} == {3, 13685} for row in rows)
    assert positive["cases"][0]["expected_masks"] == [[5576, 8382], [3, 13685]]
    record = {"status": "FROZEN_N131_W15_FIXED_FIRST_PAIR_AFFINE_RANK",
              "curve_id": data["curve_id"], "seed_mask": 13686,
              "first_rotation": 26, "second_rotation": 39,
              "fixed_first_reciprocal": c, "positive_second_reciprocal": d,
              "positive_four_atom_reciprocal": positive["cases"][0]["output_z"],
              "fixed_first_masks": [5576, 8382],
              "right_row_cap": MAX_RIGHT,
              "source_sha256": {name: sha(path) for name, path in source_paths().items()}}
    save(HERE / "protocol.json", record)
    print(json.dumps({"status": record["status"], "table_rows": len(rows)}))


def rank_insert(basis, vector):
    value = vector
    while value:
        pivot = value.bit_length() - 1
        if pivot in basis:
            value ^= basis[pivot]
        else:
            basis[pivot] = value
            return True
    return False


def execute():
    protocol = json.loads((HERE / "protocol.json").read_text())
    assert protocol["source_sha256"] == {name: sha(path) for name, path in source_paths().items()}
    rows = table()
    support = {int(a): int(b) for a, b in
               (line.split() for line in SUPPORT.read_text().splitlines())}
    first_columns = {support[mask] for mask in protocol["fixed_first_masks"]}
    selected = []
    positive = next(row for row in rows
                    if frob(row[0], 13) == protocol["positive_second_reciprocal"]
                    and {row[1], row[2]} == {3, 13685})
    selected.append(positive)
    for row in rows:
        if row == positive:
            continue
        if first_columns.isdisjoint({support[row[1]], support[row[2]]}):
            selected.append(row)
        if len(selected) == protocol["right_row_cap"]:
            break
    assert len(selected) == protocol["right_row_cap"]
    start = time.monotonic()
    basis_linear, basis_affine = {}, {}
    witness_linear, witness_affine = [], []
    outputs = []
    for index, (coordinate, left_mask, right_mask) in enumerate(selected):
        d = frob(coordinate, 13)
        roots = s3_roots(protocol["fixed_first_reciprocal"], d)
        assert roots
        assert len({support[left_mask], support[right_mask], *first_columns}) == 4
        for branch, z in enumerate(roots):
            assert trace(z) == 0
            row = {"right_index": index, "right_masks": [left_mask, right_mask],
                   "right_reciprocal": d, "branch": branch, "output_z": z}
            outputs.append(row)
            if rank_insert(basis_linear, z):
                witness_linear.append(row)
            if rank_insert(basis_affine, (1 << N) | z):
                witness_affine.append(row)
    positives = [row for row in outputs
                 if row["right_index"] == 0 and
                 row["output_z"] == protocol["positive_four_atom_reciprocal"]]
    assert len(positives) == 1
    record = {"status": "COMPLETE_N131_W15_FIXED_FIRST_PAIR_AFFINE_RANK",
              "source_protocol_sha256": sha(HERE / "protocol.json"),
              "right_rows": len(selected), "output_rows": len(outputs),
              "positive_root": positives[0],
              "linear_rank": len(basis_linear), "affine_rank": len(basis_affine),
              "linear_rank_witnesses": witness_linear,
              "affine_rank_witnesses": witness_affine,
              "elapsed_seconds_exploratory": time.monotonic() - start}
    save(HERE / "result.json", record)
    print(json.dumps({"status": record["status"],
                      "linear_rank": record["linear_rank"],
                      "affine_rank": record["affine_rank"],
                      "output_rows": record["output_rows"]}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("freeze", "execute"))
    args = parser.parse_args()
    globals()[args.action]()

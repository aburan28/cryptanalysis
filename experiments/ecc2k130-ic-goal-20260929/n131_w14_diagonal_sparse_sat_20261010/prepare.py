#!/usr/bin/env python3
"""Freeze a ten-diagonal-atom control and the sparse-circuit sources."""

import hashlib
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
PAIR = BASE / "n131_w14_diagonal_pair_inverse_20261010"
OLD = BASE / "n131_w14_samepair_target_gate_20261010"
SUPPORT = BASE / "n131_w14_ten_source_gate_20261009"
ROTATIONS = [0, 0, 26, 26, 52, 52, 78, 78, 104, 104]
R = 680564733841876926932320129493409985129


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


old = load("prior_w14_samepair_run_for_diagonal", OLD / "run.py")
diagonal = load("n131_w14_diagonal_inverse_for_control", PAIR / "pair_inverse.py")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    with Path(path).open("x") as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write("\n")


def frob_point(field, point, steps):
    x, y = point
    for _ in range(steps):
        x, y = field.mul(x, x), field.mul(y, y)
    return x, y


def source():
    support, audit, columns, field, curve, basis_w, _ = old.source()
    pair = json.loads((PAIR / "inputs.json").read_text())
    replay = json.loads((PAIR / "sage_audit.json").read_text())
    if pair["status"] != "FROZEN" or replay["status"] != "PASS":
        raise ValueError("diagonal pair source audit changed")
    if len(columns) != 8220 or len(set(columns.values())) != 8160:
        raise ValueError("W14 source support changed")
    return support, audit, columns, field, curve, basis_w, pair


def construct_control():
    _, _, columns, field, curve, basis_w, panel = source()
    inverse = diagonal.DiagonalPairInverse(columns)
    selected, seen = [], set()
    for index, case in enumerate(panel["cases"]):
        if case["kind"] != "positive":
            continue
        a, b = case["a"], case["b"]
        pair_columns = {columns[a], columns[b]}
        if len(pair_columns) != 2 or pair_columns & seen:
            continue
        left, right = inverse.atom(a), inverse.atom(b)
        if case["right_negative"]:
            right = curve.neg(right)
        if curve.add(left, right) != tuple(case["point"]):
            raise AssertionError("frozen pair group sum changed")
        selected.append((index, case, left, right))
        seen.update(pair_columns)
        if len(selected) == 5:
            break
    if len(selected) != 5:
        raise ValueError("five disjoint folded-column pairs unavailable")
    masks = [value for _, case, _, _ in selected for value in (case["a"], case["b"])]
    raw_leaves = [point for _, _, left, right in selected for point in (left, right)]
    leaves = [frob_point(field, point, ROTATIONS[i])
              for i, point in enumerate(raw_leaves)]
    middle, raw_total = old.chain(curve, leaves)
    if any(point is None or point[0] == 0
           for point in [*leaves, *middle, raw_total]):
        raise ValueError("selected control has an exceptional reciprocal join")
    q = curve.mul(4, raw_total)
    if q is None or curve.mul(R, q) is not None:
        raise AssertionError("control target is outside the prime subgroup")
    lifts = old.target_preimages(curve, q)
    if raw_total not in lifts:
        raise AssertionError("raw control sum is absent from target fiber")
    for i, (mask, point) in enumerate(zip(masks, leaves)):
        w = old.coordinate(basis_w, mask)
        rotated_w = old.method.frob(field, w, ROTATIONS[i])
        if field.inv(point[0]) != rotated_w:
            raise AssertionError("reciprocal leaf coordinate changed")
    return {"status": "CONSTRUCTED_TEN_DIAGONAL_ATOM_CONTROL",
            "curve_id": "EC1N131Ckb1heb5f1998f20b",
            "pair_input_indices": [index for index, *_ in selected],
            "rotations": ROTATIONS, "masks": masks,
            "folded_columns": [columns[mask] for mask in masks],
            "raw_leaves": [list(point) for point in leaves],
            "middle_reciprocals": [field.inv(point[0]) for point in middle],
            "raw_sum": list(raw_total), "target_q": list(q),
            "target_preimage_index": lifts.index(raw_total)}


def main():
    control = HERE / "control.json"
    protocol = HERE / "protocol.json"
    if control.exists() or protocol.exists():
        raise FileExistsError("freeze artifacts already exist")
    record = construct_control()
    save(control, record)
    paths = {"prepare": Path(__file__), "circuit": HERE / "circuit.py",
             "profile": HERE / "profile.py", "query": HERE / "query.py",
             "sage_audit_script": HERE / "sage_audit.py",
             "pair_inputs": PAIR / "inputs.json",
             "pair_audit": PAIR / "sage_audit.json",
             "pair_inverse": PAIR / "pair_inverse.py",
             "support": SUPPORT / "support_w14.tsv",
             "support_audit": SUPPORT / "sage_support_audit.json",
             "prior_runner": OLD / "run.py",
             "control": control}
    config = {"status": "FROZEN_BEFORE_CONSTRUCTED_FORMULA",
              "candidate_id": None, "curve_id": record["curve_id"],
              "summands": 10, "rotations": ROTATIONS,
              "actual_projected_factor_base_B": 82200,
              "folded_columns_K": 8160,
              "construction_wall_cap_seconds": 120,
              "rss_cap_bytes": 4294967296,
              "source_sha256": {name: sha(path) for name, path in paths.items()}}
    save(protocol, config)
    print(json.dumps({"status": config["status"],
                      "pair_input_indices": record["pair_input_indices"],
                      "target_preimage": record["target_preimage_index"]}))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Rank the free pair-product columns and exact bounded midpoint sets."""

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

import freeze_protocol

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
OUTPUT = HERE / "result.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def field_data(n):
    words = (PARENT / f"q1420_root_theory/n{n}_field.txt").read_text().split()
    assert words[0] == "Q1420FIELD1" and int(words[1]) == n
    return int(words[2], 16), [int(x, 16) for x in words[3:3 + n]]


def mul(a, b, n, low):
    value = 0
    while b:
        if b & 1:
            value ^= a
        b >>= 1
        a <<= 1
        if a >> n:
            a ^= (1 << n) | low
    return value


def insert(pivots, value):
    while value:
        bit = value.bit_length() - 1
        if bit in pivots:
            value ^= pivots[bit]
        else:
            pivots[bit] = value
            return True
    return False


def pair_rank(fixed_a, fixed_b, n, low, basis):
    free_a = [i for i in range(n) if not (fixed_a >> i) & 1]
    free_b = [j for j in range(n) if not (fixed_b >> j) & 1]
    pivots = {}
    products = 0
    for i in free_a:
        for j in free_b:
            products += 1
            insert(pivots, mul(basis[i], basis[j], n, low))
            if len(pivots) == n:
                return n, products
    return len(pivots), products


def make_result():
    protocol = json.loads(freeze_protocol.OUTPUT.read_text())
    assert protocol == freeze_protocol.make_protocol()
    binary = HERE / "exact_midpoint_rank"
    compile_receipt = json.loads((HERE / "compile_receipt.json").read_text())
    assert compile_receipt["binary_sha256"] == sha(binary)
    assert compile_receipt["source_sha256"] == sha(HERE /
                                                   "exact_midpoint_rank.cpp")
    q1460 = json.loads((PARENT /
        "q1460_fixed_state_support/result.json").read_text())
    q1460_rows = {(r["cell"], r["state_index"]): r for r in q1460["rows"]
                  if r["mode"] == "raw"}
    cells = []
    for cell in protocol["cells"]:
        name, n = cell["name"], cell["degree_n"]
        receipt_path = (PARENT / "q1456_joint_domain_profile/runs" /
                        name / "receipt.json")
        assert sha(receipt_path) == cell["receipt_sha256"]
        receipt = json.loads(receipt_path.read_text())
        snapshots = receipt["solver_report"]["domain_snapshots"]
        low, basis = field_data(n)
        rows, input_lines = [], []
        for index, state in enumerate(snapshots):
            fixed = [int(x, 16) for x in state["leaf_fixed_mask_onb_hex"]]
            rank0, used0 = pair_rank(fixed[0], fixed[1], n, low, basis)
            rank1, used1 = pair_rank(fixed[2], fixed[3], n, low, basis)
            rows.append({
                "state_index": index,
                "pair_candidates": state["pair_candidate_counts"],
                "pair_product_coefficient_ranks": [rank0, rank1],
                "products_examined_to_rank": [used0, used1],
            })
            if max(state["pair_candidate_counts"]) <= protocol[
                    "pair_candidate_cap_for_exact_midpoint_rank"]:
                fields = []
                for f, o in zip(state["leaf_fixed_mask_onb_hex"],
                                state["leaf_ones_onb_hex"]):
                    fields.extend((f, o))
                input_lines.append(" ".join([name, str(index), "raw"] + fields))
        exact_input = "\n".join(input_lines) + "\n"
        field_path = PARENT / f"q1420_root_theory/n{n}_field.txt"
        process = subprocess.run([str(binary), str(field_path),
                                  str(4 if n == 53 else 6)],
                                 input=exact_input, capture_output=True,
                                 text=True, check=True)
        exact = [json.loads(line) for line in process.stdout.splitlines()]
        assert len(exact) == len(input_lines)
        for item in exact:
            old = q1460_rows[(item["cell"], item["state_index"])]
            assert item["pair_candidates"] == old["pair_candidates"]
            assert item["midpoint_cardinalities"] == old[
                "midpoint_cardinalities"]
        cells.append({
            "name": name, "curve_id": cell["curve_id"],
            "workload_id": cell["workload_id"], "degree_n": n,
            "factor_base_actual_B": cell["factor_base_actual_B"],
            "folded_columns_K": cell["folded_columns_K"],
            "factor_base_enumerated_set_sha256": cell[
                "factor_base_enumerated_set_sha256"],
            "pair_product_rows": rows,
            "exact_midpoint_input_sha256": hashlib.sha256(
                exact_input.encode()).hexdigest(),
            "exact_midpoint_rows": exact,
        })
    return {
        "proposal_id": "Q1463", "kind": "free_midpoint_rank_screen",
        "candidate_id": None, "run_id": None, "isogeny": "none",
        "point_decomposition_stage_code": "PDP4hybrid",
        "protocol_sha256": sha(freeze_protocol.OUTPUT),
        "binary_sha256": sha(binary),
        "compile_receipt_sha256": sha(HERE / "compile_receipt.json"),
        "sage_runtime_info_sha256": sha(HERE / "sage_runtime_info.json"),
        "cells": cells,
        "natural_relation_yield_estimate": None,
        "successful_decomposition_cost": None,
        "complete_n131_log2_work": None,
        "challenge_run_admitted": False,
        "interpretation_scope": "linear relaxations of archived free-midpoint states only",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    expected = make_result()
    if args.check:
        assert expected == json.loads(OUTPUT.read_text())
        print("Q1463 rank screen: PASS")
    else:
        if OUTPUT.exists():
            raise FileExistsError(OUTPUT)
        OUTPUT.write_text(json.dumps(expected, indent=2, sort_keys=True) + "\n")

#!/usr/bin/env python3
"""Rebuild the frozen Q1408 S3 formula and lower native XOR rows to CNF."""

import argparse
import gzip
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
STAGE = HERE.parent
ROOT = STAGE.parents[1]
sys.path.insert(0, str(STAGE))

from chain_s3_balanced_multitarget import build_balanced  # noqa: E402
from run_q1325_full_weight5_probe import pin_bits  # noqa: E402


def xor_gate(a, b, z):
    return ((a, b, -z), (a, -b, z), (-a, b, z), (-a, -b, -z))


def lower(formula):
    """Yield equisatisfiable clauses; original variables retain their IDs."""
    for clause in formula.clauses:
        yield clause
    next_var = formula.variables
    for row, rhs in formula.xors:
        acc = row[0]
        for bit in row[1:-1]:
            next_var += 1
            yield from xor_gate(acc, bit, next_var)
            acc = next_var
        last = row[-1]
        if rhs:
            yield (acc, last)
            yield (-acc, -last)
        else:
            yield (acc, -last)
            yield (-acc, last)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--degree", type=int, choices=(53, 83), required=True)
    parser.add_argument("--mode", choices=("ordinary", "control"), required=True)
    parser.add_argument("--output-prefix", type=Path, required=True)
    args = parser.parse_args()
    n = args.degree
    source_label = "n83_q1408" if n == 83 else "n53_q1410"
    source_mode = "ordinary" if args.mode == "ordinary" else (
        "planted_locked" if n == 83 else "witness_locked")
    receipt = STAGE / "runs" / f"{source_label}_{source_mode}.json"
    record = json.loads(receipt.read_text())
    expected = {
        53: ("EC1N53Ckb1hf77aab617904", 24062,
             "05b75578ee58866bc8e5d3199cc77f441fa8649ccbaf88c089e998a00ea435e5"),
        83: ("EC1N83Ckb1h876c2921cb64", 30977592,
             "56c951ad78cc4036d3e8ff70bcb9d7feccacc6c763220b285def056cba30afb8"),
    }[n]
    assert (record["curve_id"], record["factor_base_actual_B"],
            record["factor_base_enumerated_set_sha256"]) == expected
    assert record["isogeny"] == "none"
    formula, leaves, mids, _, selector = build_balanced(
        n, 5 if n == 83 else 3, record["raw_preimage_x_coordinates"])
    if args.mode == "control":
        fixture = record["fixture"]
        assert fixture is not None
        for bits, value in zip(leaves, fixture["raw_leaf_x"]):
            pin_bits(formula, bits, value)
        from chain_s3 import field
        onb = field.Onb(n)
        for bits, point in zip(mids, fixture["raw_pair_sum_points"]):
            pin_bits(formula, bits, onb.toCoords(int(point[0])))
        raw_sum = fixture["raw_sum"]
        selected = record["raw_preimage_x_coordinates"].index(onb.toCoords(int(raw_sum[0])))
        pin_bits(formula, selector, selected)
    archive = STAGE / "runs" / f"{source_label}_{source_mode}.xcnf.gz"
    tmp_xcnf = args.output_prefix.with_suffix(".xcnf")
    formula.write(tmp_xcnf)
    source = tmp_xcnf.read_bytes()
    assert hashlib.sha256(source).hexdigest() == record["attempts"][0]["xcnf_sha256"]
    with gzip.open(archive, "rb") as compressed:
        assert compressed.read() == source
    tmp_xcnf.unlink()
    clauses = list(lower(formula))
    vars_used = max((abs(lit) for row in clauses for lit in row), default=0)
    cnf = args.output_prefix.with_suffix(".cnf")
    with cnf.open("w") as output:
        output.write(f"p cnf {vars_used} {len(clauses)}\n")
        for row in clauses:
            output.write(" ".join(map(str, row)) + " 0\n")
    meta = {
        "proposal_id": "Q1430", "candidate_id": None, "run_id": None,
        "degree": n,
        "curve_id": record["curve_id"], "isogeny": "none",
        "workload_id": record["workload_id"], "mode": args.mode,
        "factor_base_actual_B": record["factor_base_actual_B"],
        "factor_base_folded_columns": record["factor_base_folded_columns"],
        "factor_base_enumerated_set_sha256": record["factor_base_enumerated_set_sha256"],
        "source_xcnf_sha256": hashlib.sha256(source).hexdigest(),
        "cnf_sha256": hashlib.sha256(cnf.read_bytes()).hexdigest(),
        "original_variables": formula.variables, "cnf_variables": vars_used,
        "cnf_clauses": len(clauses), "xor_rows": len(formula.xors),
        "leaves": leaves, "mids": mids,
        "witness_leaf_x": record["fixture"]["raw_leaf_x"] if args.mode == "control" else None,
        "raw_target_x_coordinates": record["raw_preimage_x_coordinates"],
    }
    args.output_prefix.with_suffix(".json").write_text(
        json.dumps(meta, sort_keys=True, indent=2) + "\n")
    with args.output_prefix.with_suffix(".map").open("w") as output:
        output.write(f"{n}\n")
        for bits in (*leaves, *mids):
            output.write(" ".join(map(str, bits)) + "\n")
    print(json.dumps({k: meta[k] for k in ("mode", "cnf_sha256", "cnf_variables",
                                                    "cnf_clauses", "source_xcnf_sha256")}))


if __name__ == "__main__":
    main()

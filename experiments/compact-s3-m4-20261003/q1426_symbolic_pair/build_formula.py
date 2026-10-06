#!/usr/bin/env python3
"""Add a symbolic second-pair S3 link to the exact Q1420 formula."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
sys.path.insert(0, str(PARENT))
sys.path.insert(0, str(PARENT / "q1420_root_theory"))

from chain_s3 import field, multiplication_table, square_destinations  # noqa: E402
from chain_s3_factored import s3_link_factored  # noqa: E402
from q1420_root_theory.build_formula import (  # noqa: E402
    build as parent_build, convert_to_cnf)
from q1425_reverse_pair.relax_control import (  # noqa: E402
    relax_formula, serialize_cnf)


def build(n: int, cell: str):
    assert n in (53, 83)
    assert cell in ("free_partner", "ordinary")
    parent_cell = "full_lock" if cell == "free_partner" else "ordinary"
    formula, meta = parent_build(
        n, "control" if cell == "free_partner" else "ordinary", parent_cell)
    removed = 0
    if cell == "free_partner":
        removed = relax_formula(formula, meta["leaf_variables"], n)
    onb = field.Onb(n)
    s3_link_factored(
        formula, meta["leaf_variables"][2], meta["leaf_variables"][3],
        meta["pair_mid_variables"][1], multiplication_table(onb),
        square_destinations(onb))
    return formula, meta, removed


def build_cnf(n: int, cell: str):
    formula, meta, removed = build(n, cell)
    variables, clauses = convert_to_cnf(formula)
    raw = serialize_cnf(variables, clauses)
    return raw, formula, meta, removed, variables, len(clauses)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--degree", type=int, choices=(53, 83), required=True)
    parser.add_argument("--cell", choices=("free_partner", "ordinary"),
                        required=True)
    args = parser.parse_args()
    start = time.perf_counter()
    raw, formula, _, removed, variables, clauses = build_cnf(
        args.degree, args.cell)
    print(json.dumps({
        "degree_n": args.degree, "cell": args.cell,
        "cnf_variables": variables, "cnf_clauses": clauses,
        "cnf_bytes": len(raw), "cnf_sha256": hashlib.sha256(raw).hexdigest(),
        "original_formula_xor_rows": len(formula.xors),
        "removed_partner_pin_units": removed,
        "build_wall_seconds_exploratory": time.perf_counter() - start,
    }, sort_keys=True))


if __name__ == "__main__":
    main()

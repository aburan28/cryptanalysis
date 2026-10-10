"""Q1429 matched variable-output and constant-output right-pair S3 formulas."""

from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
OLD = ROOT / "experiments/compact-s3-m4-20261003"
sys.path.insert(0, str(OLD))

from chain_s3 import Formula, field, multiplication_table, s3_link, square_destinations  # noqa: E402
from chain_s3_factored import s3_link_factored  # noqa: E402

VARIANTS = ("variable_factored", "fixed_factored", "fixed_direct")


def build(n, weight, output_x, variant):
    assert variant in VARIANTS
    assert 0 < output_x < 1 << n
    onb = field.Onb(n)
    table = multiplication_table(onb)
    destinations = square_destinations(onb)
    formula = Formula()
    leaves = [[formula.new() for _ in range(n)] for _ in range(2)]
    for leaf in leaves:
        formula.at_most(leaf, weight)
        formula.clauses.append(leaf[:])
    if variant == "variable_factored":
        output = [formula.new() for _ in range(n)]
        s3_link_factored(formula, leaves[0], leaves[1], output,
                         table, destinations)
        assumptions = [bit if output_x >> i & 1 else -bit
                       for i, bit in enumerate(output)]
    else:
        output = None
        constant = [1 if output_x >> i & 1 else -1 for i in range(n)]
        link = s3_link_factored if variant == "fixed_factored" else s3_link
        link(formula, leaves[0], leaves[1], constant,
             table, destinations)
        assumptions = []
    return formula, leaves, output, assumptions


def shape(formula):
    return {"variables": formula.variables,
            "cnf_clauses": len(formula.clauses),
            "xor_rows": len(formula.xors),
            "and_gates": len(formula.and_cache),
            "cnf_literals": sum(len(clause) for clause in formula.clauses),
            "xor_literals": sum(len(row) for row, _ in formula.xors)}

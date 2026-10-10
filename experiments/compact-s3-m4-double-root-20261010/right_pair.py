"""One fixed-output S3 pair after external first-pair and outer roots."""

from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
OLD = ROOT / "experiments/compact-s3-m4-20261003"
sys.path.insert(0, str(OLD))

from chain_s3 import Formula, field, multiplication_table, square_destinations  # noqa: E402
from chain_s3_factored import s3_link_factored  # noqa: E402


def build_right_pair(n, weight):
    onb = field.Onb(n)
    table = multiplication_table(onb)
    destinations = square_destinations(onb)
    formula = Formula()
    leaves = [[formula.new() for _ in range(n)] for _ in range(2)]
    output = [formula.new() for _ in range(n)]
    for leaf in leaves:
        formula.at_most(leaf, weight)
        formula.clauses.append(leaf[:])
    s3_link_factored(formula, leaves[0], leaves[1], output,
                     table, destinations)
    return formula, leaves, output

"""Q1423: three-variable-leaf S3 chain after fixing one subgroup base point."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "experiments/compact-s3-m4-20261003"))

from chain_s3 import Formula, multiplication_table, square_destinations  # noqa: E402
from chain_s3_base_orbit import choose_base_orbit_x  # noqa: E402
from chain_s3_factored import s3_link_factored  # noqa: E402
from chain_s3_multitarget import choose_target_x  # noqa: E402
from chain_s3_ordered import less_or_equal  # noqa: E402


def build_exact(n, keys, target_x, arithmetic):
    """N53: three exact subgroup orbit leaves and one S3 intermediate."""
    table, square_dest = arithmetic
    formula = Formula()
    leaves, choices = [], []
    for _ in range(3):
        leaf, orbit, shift = choose_base_orbit_x(formula, n, keys, square_dest)
        leaves.append(leaf)
        choices.append((orbit, shift))
    for left, right in zip(choices, choices[1:]):
        less_or_equal(formula, left[1] + left[0], right[1] + right[0])
    mid = [formula.new() for _ in range(n)]
    target = [1 if target_x >> i & 1 else -1 for i in range(n)]
    s3_link_factored(formula, leaves[0], leaves[1], mid, table, square_dest)
    s3_link_factored(formula, mid, leaves[2], target, table, square_dest)
    return formula, leaves, mid, choices, None


def build_raw(n, weight, target_xs, arithmetic):
    """N83: three raw low-weight leaves and four target preimage choices."""
    table, square_dest = arithmetic
    formula = Formula()
    leaves = [[formula.new() for _ in range(n)] for _ in range(3)]
    for leaf in leaves:
        formula.at_most(leaf, weight)
        formula.clauses.append(leaf[:])
    mid = [formula.new() for _ in range(n)]
    target, selector = choose_target_x(formula, n, target_xs)
    s3_link_factored(formula, leaves[0], leaves[1], mid, table, square_dest)
    s3_link_factored(formula, mid, leaves[2], target, table, square_dest)
    return formula, leaves, mid, None, selector


def arithmetic(onb):
    return multiplication_table(onb), square_destinations(onb)

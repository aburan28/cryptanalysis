"""Balanced four-leaf S3 tree with unsigned leaf-x permutation symmetry removed."""

from chain_s3_balanced_multitarget import build_balanced
from chain_s3_ordered import less_or_equal


def build_ordered_balanced(n, weight, raw_target_xs):
    formula, leaves, pair_sums, target, selector = build_balanced(
        n, weight, raw_target_xs)
    for left, right in zip(leaves, leaves[1:]):
        less_or_equal(formula, left, right)
    return formula, leaves, pair_sums, target, selector

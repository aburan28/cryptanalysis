"""Reverse the final group-addition link of the four-point SAT chain.

If P123 + P4 = T, then P4 = T + (-P123). Encoding both directions should
propagate a known P123 to the remaining leaf. This variant additionally
requires x(T) != x(P123), so it covers a nondegenerate subset of Q1320/Q1321.
"""

from chain_group_add import (affine_add, build_exact_base_group_chain,
                             build_projected_sparse_group_chain, xor_vector)
from chain_s3 import field, multiplication_table, square_destinations


def reverse_last_link(formula, penultimate, last_leaf, target, table,
                      square_dest):
    """Constrain last_leaf = target - penultimate via a forward circuit."""
    n = len(penultimate[0])
    target_bits = tuple([
        1 if value >> position & 1 else -1 for position in range(n)]
        for value in target)
    x, y = penultimate
    negative = (x, xor_vector(formula, x, y))
    recovered, slope = affine_add(
        formula, target_bits, negative, table, square_dest)
    for actual, expected in zip(last_leaf, recovered):
        for a, b in zip(actual, expected):
            formula.xor_relation((a, b))
    return recovered, slope


def build_exact_base_reverse_chain(n, canonical_x_keys, public_target):
    formula, choices, leaves, mids, slopes = build_exact_base_group_chain(
        n, canonical_x_keys, public_target)
    onb = field.Onb(n)
    recovered, reverse_slope = reverse_last_link(
        formula, mids[-1], leaves[-1],
        tuple(onb.toCoords(value) for value in public_target),
        multiplication_table(onb), square_destinations(onb))
    return formula, choices, leaves, mids, slopes, recovered, reverse_slope


def build_projected_sparse_reverse_chain(n, weight, public_target):
    formula, raw_leaves, leaves, mids, slopes = (
        build_projected_sparse_group_chain(n, weight, public_target))
    onb = field.Onb(n)
    recovered, reverse_slope = reverse_last_link(
        formula, mids[-1], leaves[-1],
        tuple(onb.toCoords(value) for value in public_target),
        multiplication_table(onb), square_destinations(onb))
    return (formula, raw_leaves, leaves, mids, slopes, recovered,
            reverse_slope)

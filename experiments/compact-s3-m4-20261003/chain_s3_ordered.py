"""Orbit S3 chain with permutation symmetry broken by leaf-x ordering."""

from chain_s3_orbit import build_orbit


def less_or_equal(formula, left, right):
    """Require unsigned normal-basis x(left) <= x(right)."""
    assert len(left) == len(right)
    equal_prefix = 1
    less = -1
    for a, b in zip(reversed(left), reversed(right)):
        lower_here = formula.and_gate(-a, b)
        first_difference = formula.and_gate(equal_prefix, lower_here)
        less = -formula.and_gate(-less, -first_difference)
        equal_here = formula.new()
        formula.xor_relation((equal_here, a, b), True)
        equal_prefix = formula.and_gate(equal_prefix, equal_here)
    formula.clauses.append([less, equal_prefix])


def build_ordered_orbit(n, weight, raw_preimage_xs):
    formula, leaves, mids, target, pre_selector, shift_selector = build_orbit(
        n, weight, raw_preimage_xs)
    for left, right in zip(leaves, leaves[1:]):
        less_or_equal(formula, left, right)
    return formula, leaves, mids, target, pre_selector, shift_selector

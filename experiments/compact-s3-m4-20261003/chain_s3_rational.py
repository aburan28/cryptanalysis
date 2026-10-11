"""Exact sparse-x rationality clauses for the multi-preimage S3 chain."""

from chain_s3_multitarget import build_multitarget


def forbid_exact_support(formula, variables, mask, max_weight):
    support = [index for index in range(len(variables)) if mask >> index & 1]
    assert 1 <= len(support) <= max_weight
    if len(support) == max_weight:
        # The existing at-most bound forbids every strict superset.
        formula.clauses.append([-variables[index] for index in support])
    else:
        formula.clauses.append(
            [-variables[index] for index in support] +
            [variables[index] for index in range(len(variables))
             if not (mask >> index & 1)])


def add_rationality_filter(formula, leaves, invalid_masks, max_weight):
    for point in leaves:
        for mask in invalid_masks:
            forbid_exact_support(formula, point, mask, max_weight)


def build_rational_multitarget(n, weight, target_xs, invalid_masks):
    formula, leaves, mids, target, selector = build_multitarget(
        n, weight, target_xs)
    add_rationality_filter(formula, leaves, invalid_masks, weight)
    return formula, leaves, mids, target, selector

"""Balanced four-leaf S3 tree with a SAT-selected raw target preimage.

The two leaf pairs have independent intermediate x coordinates. A final
S3 link joins them to one of the complete cofactor-preimage target x values.
Every SAT model still requires an independent full-point group-law check.
"""

from chain_s3 import Formula, field, multiplication_table, square_destinations
from chain_s3_factored import s3_link_factored
from chain_s3_multitarget import choose_target_x


def build_balanced(n, weight, raw_target_xs):
    onb = field.Onb(n)
    table = multiplication_table(onb)
    square_dest = square_destinations(onb)
    formula = Formula()
    leaves = [[formula.new() for _ in range(n)] for _ in range(4)]
    pair_sums = [[formula.new() for _ in range(n)] for _ in range(2)]
    for leaf in leaves:
        formula.at_most(leaf, weight)
        formula.clauses.append(leaf[:])
    target, selector = choose_target_x(formula, n, raw_target_xs)
    s3_link_factored(formula, leaves[0], leaves[1], pair_sums[0],
                     table, square_dest)
    s3_link_factored(formula, leaves[2], leaves[3], pair_sums[1],
                     table, square_dest)
    s3_link_factored(formula, pair_sums[0], pair_sums[1], target,
                     table, square_dest)
    return formula, leaves, pair_sums, target, selector

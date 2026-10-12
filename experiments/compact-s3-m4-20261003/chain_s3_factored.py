"""Three-product S3-chain encoding sharing the (a+b)c product."""

from chain_s3 import (Formula, field, multiplication_table, product,
                      square_destinations)


def s3_link_factored(formula, a, b, c, table, square_dest):
    # ab + ac + bc = ab + (a+b)c in characteristic two.
    ab = product(formula, a, b, table)
    a_plus_b = [formula.new() for _ in a]
    for out, left, right in zip(a_plus_b, a, b):
        formula.xor_relation((out, left, right))
    cross = product(formula, a_plus_b, c, table)
    abc = product(formula, ab, c, table)
    for source, dest in enumerate(square_dest):
        formula.xor_relation((ab[source], cross[source], abc[dest]), True)


def build_factored(n, weight, target_x):
    onb = field.Onb(n)
    table = multiplication_table(onb)
    destinations = square_destinations(onb)
    formula = Formula()
    leaves = [[formula.new() for _ in range(n)] for _ in range(4)]
    intermediates = [[formula.new() for _ in range(n)] for _ in range(2)]
    for point in leaves:
        formula.at_most(point, weight)
        formula.clauses.append(point[:])
    target = [1 if target_x >> i & 1 else -1 for i in range(n)]
    s3_link_factored(formula, leaves[0], leaves[1], intermediates[0],
                     table, destinations)
    s3_link_factored(formula, intermediates[0], leaves[2],
                     intermediates[1], table, destinations)
    s3_link_factored(formula, intermediates[1], leaves[3], target,
                     table, destinations)
    return formula, leaves, intermediates

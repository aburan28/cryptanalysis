"""Compact S3 chain over cofactor-four projections of sparse raw x values.

For E: y^2 + xy = x^3 + 1 in characteristic two,

    x([4]P) * (x(P)^12 + x(P)^4) = x(P)^16 + x(P)^8 + 1.

The raw x is required to be rational by Tr(x + 1/x) = 0. These constraints
encode the exact cofactor-projected weight base without listing its points.
Only the public target x appears in the S3 chain; group signs are checked
after solving.
"""

from chain_s3 import (Formula, field, multiplication_table, product,
                      square_destinations)
from chain_s3_factored import s3_link_factored


def square_bits(bits, square_dest):
    result = [None] * len(bits)
    for source, destination in enumerate(square_dest):
        result[destination] = bits[source]
    assert all(value is not None for value in result)
    return result


def projected_sparse_leaf(formula, n, weight, table, square_dest):
    raw_x = [formula.new() for _ in range(n)]
    formula.at_most(raw_x, weight)
    formula.clauses.append(raw_x[:])

    inverse = [formula.new() for _ in range(n)]
    inverse_check = product(formula, raw_x, inverse, table)
    # In a type-II normal basis, 1 has all coordinate bits set.
    formula.clauses.extend(([bit] for bit in inverse_check))
    # Tr(x + 1/x^2) = Tr(x + 1/x) = 0 is the lift condition.
    formula.xor_relation(raw_x + inverse)

    x4 = square_bits(square_bits(raw_x, square_dest), square_dest)
    x8 = square_bits(x4, square_dest)
    x16 = square_bits(x8, square_dest)
    x12 = product(formula, x8, x4, table)
    denominator = [formula.new() for _ in range(n)]
    for output, left, right in zip(denominator, x12, x4):
        formula.xor_relation((output, left, right))

    projected_x = [formula.new() for _ in range(n)]
    scaled = product(formula, projected_x, denominator, table)
    for value, eighth, sixteenth in zip(scaled, x8, x16):
        formula.xor_relation((value, eighth, sixteenth), True)
    return raw_x, projected_x


def build_projected_sparse_chain(n, weight, target_x):
    assert n in (83, 131)
    assert 0 < target_x < (1 << n)
    onb = field.Onb(n)
    table = multiplication_table(onb)
    square_dest = square_destinations(onb)
    formula = Formula()
    raw_leaves = []
    projected_leaves = []
    for _ in range(4):
        raw, projected = projected_sparse_leaf(
            formula, n, weight, table, square_dest)
        raw_leaves.append(raw)
        projected_leaves.append(projected)
    intermediates = [[formula.new() for _ in range(n)] for _ in range(2)]
    target = [1 if target_x >> i & 1 else -1 for i in range(n)]
    s3_link_factored(formula, projected_leaves[0], projected_leaves[1],
                     intermediates[0], table, square_dest)
    s3_link_factored(formula, intermediates[0], projected_leaves[2],
                     intermediates[1], table, square_dest)
    s3_link_factored(formula, intermediates[1], projected_leaves[3], target,
                     table, square_dest)
    return formula, raw_leaves, projected_leaves, intermediates

"""Exact cofactor-four leaf with the rational-lift inverse reused for doubling."""
from chain_s3 import product
from chain_s3_projected_sparse import square_bits


def projected_sparse_leaf_double_reuse(formula, n, weight, table, square_dest):
    raw_x = [formula.new() for _ in range(n)]
    formula.at_most(raw_x, weight)
    formula.clauses.append(raw_x[:])

    inverse_x = [formula.new() for _ in range(n)]
    inverse_check = product(formula, raw_x, inverse_x, table)
    formula.clauses.extend(([bit] for bit in inverse_check))
    formula.xor_relation(raw_x + inverse_x)

    # E: y² + xy = x³ + 1 has x([2]P) = x² + x⁻².
    x2 = [formula.new() for _ in range(n)]
    for output, a, b in zip(x2, square_bits(raw_x, square_dest),
                            square_bits(inverse_x, square_dest)):
        formula.xor_relation((output, a, b))
    inverse_x2 = [formula.new() for _ in range(n)]
    inverse2_check = product(formula, x2, inverse_x2, table)
    formula.clauses.extend(([bit] for bit in inverse2_check))

    projected_x = [formula.new() for _ in range(n)]
    for output, a, b in zip(projected_x, square_bits(x2, square_dest),
                            square_bits(inverse_x2, square_dest)):
        formula.xor_relation((output, a, b))
    return raw_x, projected_x

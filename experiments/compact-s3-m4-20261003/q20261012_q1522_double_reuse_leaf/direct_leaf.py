"""Exact two-product cofactor-four leaf with a direct projected-x equation."""
from chain_s3 import product
from chain_s3_projected_sparse import square_bits


def projected_sparse_leaf_direct(formula, n, weight, table, square_dest):
    raw_x = [formula.new() for _ in range(n)]
    formula.at_most(raw_x, weight)
    formula.clauses.append(raw_x[:])
    inverse_x = [formula.new() for _ in range(n)]
    inverse_check = product(formula, raw_x, inverse_x, table)
    formula.clauses.extend(([bit] for bit in inverse_check))
    formula.xor_relation(raw_x + inverse_x)

    x2 = [formula.new() for _ in range(n)]
    for output, a, b in zip(x2, square_bits(raw_x, square_dest),
                            square_bits(inverse_x, square_dest)):
        formula.xor_relation((output, a, b))
    x2_squared = square_bits(x2, square_dest)
    x2_fourth = square_bits(x2_squared, square_dest)
    projected_x = [formula.new() for _ in range(n)]
    scaled = product(formula, projected_x, x2_squared, table)
    for value, fourth in zip(scaled, x2_fourth):
        formula.xor_relation((value, fourth), True)
    return raw_x, projected_x

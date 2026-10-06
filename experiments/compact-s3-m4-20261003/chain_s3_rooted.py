"""S3 chain with algebraic half-trace root circuits for early links.

The roots of S3(a,b,c) are represented by one branch bit rather than a
free n-bit c. This variant requires nonzero a, b and a+b, which holds for
nondegenerate subgroup sums with distinct input x coordinates.
"""

from chain_s3 import (Formula, field, multiplication_table, product,
                      square_destinations)
from chain_s3_factored import s3_link_factored
from chain_s3_projected_sparse import (projected_sparse_leaf, square_bits)
from s3_root_oracle import half_trace


def half_trace_columns(onb):
    return [onb.toCoords(half_trace(onb, onb.fromCoords(1 << position)))
            for position in range(onb.m)]


def s3_root_link(formula, a, b, table, square_dest, half_columns):
    """Emit both third-coordinate roots of S3(a,b,c), selected by one bit."""
    n = len(a)
    total = [formula.new() for _ in range(n)]
    for out, left, right in zip(total, a, b):
        formula.xor_relation((out, left, right))
    formula.clauses.append(total[:])  # distinct x: a+b != 0
    ab = product(formula, a, b, table)
    inverse_ab = [formula.new() for _ in range(n)]
    inverse_check = product(formula, ab, inverse_ab, table)
    formula.clauses.extend(([bit] for bit in inverse_check))
    quotient = product(formula, total, inverse_ab, table)
    e = [formula.new() for _ in range(n)]
    for out, left, right in zip(e, total, quotient):
        formula.xor_relation((out, left, right))
    d = square_bits(e, square_dest)
    formula.xor_relation(d)  # Artin-Schreier root exists iff Tr(d)=0.

    branch = formula.new()
    z = [formula.new() for _ in range(n)]
    for output_position, out in enumerate(z):
        terms = [d[source] for source, image in enumerate(half_columns)
                 if image >> output_position & 1]
        # z = H(d) + branch*1; 1 has all normal-basis bits set.
        formula.xor_relation([out, branch, *terms])

    total_squared = square_bits(total, square_dest)
    scale = [formula.new() for _ in range(n)]
    scale_check = product(formula, scale, total_squared, table)
    for left, right in zip(scale_check, ab):
        formula.xor_relation((left, right))
    root = product(formula, scale, z, table)
    return root, branch


def build_rooted_projected_chain(n, weight, target_x, rooted_links=1):
    assert n in (83, 131)
    assert rooted_links in (1, 2)
    assert 0 < target_x < (1 << n)
    onb = field.Onb(n)
    table = multiplication_table(onb)
    square_dest = square_destinations(onb)
    columns = half_trace_columns(onb)
    formula = Formula()
    raw_leaves = []
    projected_leaves = []
    for _ in range(4):
        raw, projected = projected_sparse_leaf(
            formula, n, weight, table, square_dest)
        raw_leaves.append(raw)
        projected_leaves.append(projected)
    first, first_branch = s3_root_link(
        formula, projected_leaves[0], projected_leaves[1],
        table, square_dest, columns)
    branches = [first_branch]
    if rooted_links == 2:
        second, second_branch = s3_root_link(
            formula, first, projected_leaves[2],
            table, square_dest, columns)
        branches.append(second_branch)
    else:
        second = [formula.new() for _ in range(n)]
        s3_link_factored(formula, first, projected_leaves[2], second,
                         table, square_dest)
    target = [1 if target_x >> i & 1 else -1 for i in range(n)]
    s3_link_factored(formula, second, projected_leaves[3], target,
                     table, square_dest)
    return formula, raw_leaves, projected_leaves, (first, second), branches

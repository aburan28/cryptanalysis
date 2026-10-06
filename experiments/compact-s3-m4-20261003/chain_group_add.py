"""Four-point binary-curve group addition circuit with exact y coordinates.

For E: y^2 + xy = x^3 + 1, every nondegenerate affine addition uses
lambda=(y1+y2)/(x1+x2), x3=lambda^2+lambda+x1+x2, and
y3=lambda(x1+x3)+x3+y1. The circuit requires x1 != x2 at each link;
the full curve equation fixes each leaf's two possible y lifts.
"""

from chain_s3 import (Formula, field, multiplication_table, product,
                      square_destinations)
from chain_s3_base_orbit import choose_base_orbit_x
from chain_s3_projected_sparse import projected_sparse_leaf, square_bits


def xor_vector(formula, left, right):
    out = [formula.new() for _ in left]
    for value, a, b in zip(out, left, right):
        formula.xor_relation((value, a, b))
    return out


def on_curve(formula, x, y, table, square_dest):
    y_squared = square_bits(y, square_dest)
    xy = product(formula, x, y, table)
    x_squared = square_bits(x, square_dest)
    x_cubed = product(formula, x, x_squared, table)
    for left, middle, right in zip(y_squared, xy, x_cubed):
        formula.xor_relation((left, middle, right), True)


def frobenius_bits(bits, count, square_dest):
    result = bits
    for _ in range(count):
        result = square_bits(result, square_dest)
    return result


def inverse_circuit(formula, bits, table, square_dest):
    """Forward circuit for a^(2^n-2), using O(log n) multiplications."""
    n = len(bits)
    assert n > 1
    needed = n - 1
    powers = {1: bits}
    length = 1
    while 2 * length <= needed:
        powers[2 * length] = product(
            formula, frobenius_bits(powers[length], length, square_dest),
            powers[length], table)
        length *= 2
    result = powers[length]
    for bit in reversed(range(length.bit_length() - 1)):
        part = 1 << bit
        if needed & part:
            result = product(
                formula, frobenius_bits(result, part, square_dest),
                powers[part], table)
    return square_bits(result, square_dest)


def affine_add(formula, left, right, table, square_dest):
    x1, y1 = left
    x2, y2 = right
    n = len(x1)
    denominator = xor_vector(formula, x1, x2)
    formula.clauses.append(denominator[:])
    numerator = xor_vector(formula, y1, y2)
    inverse = inverse_circuit(formula, denominator, table, square_dest)
    slope = product(formula, numerator, inverse, table)
    slope_squared = square_bits(slope, square_dest)
    x3 = [formula.new() for _ in range(n)]
    for out, a, b, c in zip(x3, slope_squared, slope, denominator):
        formula.xor_relation((out, a, b, c))
    x1_plus_x3 = xor_vector(formula, x1, x3)
    cross = product(formula, slope, x1_plus_x3, table)
    y3 = [formula.new() for _ in range(n)]
    for out, a, b, c in zip(y3, cross, x3, y1):
        formula.xor_relation((out, a, b, c))
    return (x3, y3), slope


def add_four_to_target(formula, leaf_x, target, table, square_dest):
    n = len(leaf_x[0])
    leaves = []
    for x in leaf_x:
        y = [formula.new() for _ in range(n)]
        on_curve(formula, x, y, table, square_dest)
        leaves.append((x, y))
    first, slope1 = affine_add(
        formula, leaves[0], leaves[1], table, square_dest)
    second, slope2 = affine_add(
        formula, first, leaves[2], table, square_dest)
    final, slope3 = affine_add(
        formula, second, leaves[3], table, square_dest)
    for row, field_value in zip(final, target):
        value = field_value
        for position, bit in enumerate(row):
            formula.clauses.append([
                bit if value >> position & 1 else -bit])
    return leaves, (first, second), (slope1, slope2, slope3)


def build_projected_sparse_group_chain(n, weight, public_target):
    assert n in (83, 131)
    onb = field.Onb(n)
    table = multiplication_table(onb)
    square_dest = square_destinations(onb)
    formula = Formula()
    raw_leaves = []
    projected_x = []
    for _ in range(4):
        raw, projected = projected_sparse_leaf(
            formula, n, weight, table, square_dest)
        raw_leaves.append(raw)
        projected_x.append(projected)
    target = tuple(onb.toCoords(value) for value in public_target)
    leaves, mids, slopes = add_four_to_target(
        formula, projected_x, target, table, square_dest)
    return formula, raw_leaves, leaves, mids, slopes


def build_exact_base_group_chain(n, canonical_x_keys, public_target):
    assert n == 53
    onb = field.Onb(n)
    table = multiplication_table(onb)
    square_dest = square_destinations(onb)
    formula = Formula()
    projected_x = []
    choices = []
    for _ in range(4):
        x, index, shift = choose_base_orbit_x(
            formula, n, canonical_x_keys, square_dest)
        projected_x.append(x)
        choices.append((index, shift))
    target = tuple(onb.toCoords(value) for value in public_target)
    leaves, mids, slopes = add_four_to_target(
        formula, projected_x, target, square_dest=square_dest,
        table=table)
    return formula, choices, leaves, mids, slopes

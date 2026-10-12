"""Compact S3 chain with cofactor and Frobenius target-orbit selection."""

from chain_s3 import Formula, field, multiplication_table, square_destinations
from chain_s3_factored import s3_link_factored
from chain_s3_multitarget import choose_target_x, decode_choice


def permute_by_frobenius(bits, square_dest, exponent):
    result = [None] * len(bits)
    for source, bit in enumerate(bits):
        destination = source
        for _ in range(exponent % len(bits)):
            destination = square_dest[destination]
        result[destination] = bit
    assert all(bit is not None for bit in result)
    return result


def mux(formula, selector, zero, one):
    result = formula.new()
    formula.clauses.extend(([selector, -zero, result],
                            [selector, zero, -result],
                            [-selector, -one, result],
                            [-selector, one, -result]))
    return result


def frobenius_barrel(formula, input_bits, square_dest):
    n = len(input_bits)
    width = max(1, (n - 1).bit_length())
    selector = [formula.new() for _ in range(width)]
    current = input_bits
    for position, bit in enumerate(selector):
        rotated = permute_by_frobenius(current, square_dest, 1 << position)
        current = [mux(formula, bit, left, right)
                   for left, right in zip(current, rotated)]
    for invalid in range(n, 1 << width):
        formula.clauses.append([
            -bit if invalid >> position & 1 else bit
            for position, bit in enumerate(selector)])
    return current, selector


def build_orbit(n, weight, raw_preimage_xs):
    onb = field.Onb(n)
    table = multiplication_table(onb)
    destinations = square_destinations(onb)
    formula = Formula()
    leaves = [[formula.new() for _ in range(n)] for _ in range(4)]
    intermediates = [[formula.new() for _ in range(n)] for _ in range(2)]
    for point in leaves:
        formula.at_most(point, weight)
        formula.clauses.append(point[:])
    base_target, preimage_selector = choose_target_x(
        formula, n, raw_preimage_xs)
    target, frobenius_selector = frobenius_barrel(
        formula, base_target, destinations)
    s3_link_factored(formula, leaves[0], leaves[1], intermediates[0],
                     table, destinations)
    s3_link_factored(formula, intermediates[0], leaves[2], intermediates[1],
                     table, destinations)
    s3_link_factored(formula, intermediates[1], leaves[3], target,
                     table, destinations)
    return (formula, leaves, intermediates, target,
            preimage_selector, frobenius_selector)


def decode_orbit_choice(preimage_selector, frobenius_selector, values):
    return (decode_choice(preimage_selector, values),
            decode_choice(frobenius_selector, values))

"""Factored S3 chain with a SAT-selected raw cofactor preimage target."""

from chain_s3 import Formula, field, multiplication_table, square_destinations
from chain_s3_factored import s3_link_factored


def choose_target_x(formula, n, targets):
    assert targets and all(0 <= value < (1 << n) for value in targets)
    assert len(set(targets)) == len(targets)
    width = max(1, (len(targets) - 1).bit_length())
    selector = [formula.new() for _ in range(width)]
    target = [formula.new() for _ in range(n)]
    for index in range(1 << width):
        mismatch = [(-bit if index >> position & 1 else bit)
                    for position, bit in enumerate(selector)]
        if index >= len(targets):
            formula.clauses.append(mismatch)
            continue
        value = targets[index]
        for position, bit in enumerate(target):
            formula.clauses.append(mismatch +
                                   [bit if value >> position & 1 else -bit])
    return target, selector


def build_multitarget(n, weight, target_xs):
    onb = field.Onb(n)
    table = multiplication_table(onb)
    destinations = square_destinations(onb)
    formula = Formula()
    leaves = [[formula.new() for _ in range(n)] for _ in range(4)]
    intermediates = [[formula.new() for _ in range(n)] for _ in range(2)]
    for point in leaves:
        formula.at_most(point, weight)
        formula.clauses.append(point[:])
    target, selector = choose_target_x(formula, n, target_xs)
    s3_link_factored(formula, leaves[0], leaves[1], intermediates[0],
                     table, destinations)
    s3_link_factored(formula, intermediates[0], leaves[2], intermediates[1],
                     table, destinations)
    s3_link_factored(formula, intermediates[1], leaves[3], target,
                     table, destinations)
    return formula, leaves, intermediates, target, selector


def decode_choice(selector, values):
    return sum((1 << position) for position, bit in enumerate(selector)
               if values.get(bit, False))

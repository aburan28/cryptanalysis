"""Four-summand S3 chain over exact subgroup factor-base x orbits.

Each leaf chooses a canonical signed-Frobenius x-orbit key and a shift.
The canonical key lookup uses one-hot indicators and native XOR rows, then
the compact Frobenius barrel produces the selected subgroup x coordinate.
The public target is used directly, so no raw cofactor-preimage selector is
needed. Sign choices are checked by exact group replay after a SAT model.
"""

from chain_s3 import Formula, field, multiplication_table, square_destinations
from chain_s3_factored import s3_link_factored
from chain_s3_multitarget import decode_choice
from chain_s3_orbit import frobenius_barrel
from chain_s3_ordered import less_or_equal


def choose_base_orbit_x(formula, n, canonical_x_keys, square_dest):
    count = len(canonical_x_keys)
    assert count and all(0 < key < (1 << n) for key in canonical_x_keys)
    assert len(set(canonical_x_keys)) == count
    width = max(1, (count - 1).bit_length())
    selector = [formula.new() for _ in range(width)]
    indicators = [formula.new() for _ in range(count)]
    representative_x = [formula.new() for _ in range(n)]
    for index, indicator in enumerate(indicators):
        mismatch = []
        for position, bit in enumerate(selector):
            selected = bool(index >> position & 1)
            formula.clauses.append([-indicator, bit if selected else -bit])
            mismatch.append(-bit if selected else bit)
        formula.clauses.append(mismatch + [indicator])
    for invalid in range(count, 1 << width):
        formula.clauses.append([
            -bit if invalid >> position & 1 else bit
            for position, bit in enumerate(selector)])
    # Exactly one indicator is true, so parity is the selected key bit.
    for position, output_bit in enumerate(representative_x):
        formula.xor_relation([output_bit] + [
            indicators[index] for index, key in enumerate(canonical_x_keys)
            if key >> position & 1])
    shifted_x, shift_selector = frobenius_barrel(
        formula, representative_x, square_dest)
    return shifted_x, selector, shift_selector


def build_base_orbit_chain(n, canonical_x_keys, target_x,
                           ordered_leaves=True):
    assert 0 < target_x < (1 << n)
    onb = field.Onb(n)
    table = multiplication_table(onb)
    square_dest = square_destinations(onb)
    formula = Formula()
    leaves = []
    choices = []
    for _ in range(4):
        leaf, index_selector, shift_selector = choose_base_orbit_x(
            formula, n, canonical_x_keys, square_dest)
        leaves.append(leaf)
        choices.append((index_selector, shift_selector))
    if ordered_leaves:
        for left, right in zip(choices, choices[1:]):
            less_or_equal(formula, left[1] + left[0], right[1] + right[0])
    intermediates = [[formula.new() for _ in range(n)] for _ in range(2)]
    target = [1 if target_x >> i & 1 else -1 for i in range(n)]
    s3_link_factored(formula, leaves[0], leaves[1], intermediates[0],
                     table, square_dest)
    s3_link_factored(formula, intermediates[0], leaves[2],
                     intermediates[1], table, square_dest)
    s3_link_factored(formula, intermediates[1], leaves[3], target,
                     table, square_dest)
    return formula, leaves, intermediates, choices


def decode_base_choice(choice, values):
    index_selector, shift_selector = choice
    return (decode_choice(index_selector, values),
            decode_choice(shift_selector, values))

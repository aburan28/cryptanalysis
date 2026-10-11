"""Exact GF(2^n) multiplication circuit using a verified ONB/poly bridge.

Inputs and outputs use the archived ONB coordinates. The polynomial basis is
only an internal arithmetic representation and does not change curve identity.
"""

from __future__ import annotations

from chain_s3 import Formula

Expression = tuple[bool, frozenset[int]]
ZERO: Expression = (False, frozenset())


def expression_of(literal: int) -> Expression:
    if literal == 1:
        return (True, frozenset())
    if literal == -1:
        return ZERO
    return (literal < 0, frozenset((abs(literal),)))


def xor_expression(left: Expression, right: Expression) -> Expression:
    return (left[0] ^ right[0], left[1] ^ right[1])


def materialize(formula: Formula, expression: Expression) -> int:
    return parity(formula, [*sorted(expression[1]), 1 if expression[0]
                             else -1])


def parity(formula: Formula, terms: list[int]) -> int:
    """Return one signed literal for the XOR of signed literals."""
    odd = set()
    constant = False
    for literal in terms:
        if literal == 1:
            constant = not constant
            continue
        if literal == -1:
            continue
        if literal < 0:
            constant = not constant
            literal = -literal
        if literal in odd:
            odd.remove(literal)
        else:
            odd.add(literal)
    if not odd:
        return 1 if constant else -1
    if len(odd) == 1:
        single = next(iter(odd))
        return -single if constant else single
    result = formula.new()
    formula.xor_relation([result, *sorted(odd)], constant)
    return result


def linear_map(formula: Formula, source: list[int], images: list[int]) -> list[int]:
    """Map source coefficients through a declared F2-linear basis map."""
    n = len(source)
    assert len(images) == n
    rows: list[list[int]] = [[] for _ in range(n)]
    for literal, image in zip(source, images):
        assert 0 <= image < (1 << n)
        while image:
            bit = image & -image
            rows[bit.bit_length() - 1].append(literal)
            image ^= bit
    return [parity(formula, row) for row in rows]


def karatsuba_convolution(formula: Formula, left: list[int],
                          right: list[int]) -> list[Expression]:
    """Multiply coefficient vectors, keeping output XORs symbolic."""
    size = len(left)
    assert size == len(right) and size > 0 and size & (size - 1) == 0
    if size == 1:
        return [expression_of(formula.and_gate(left[0], right[0]))]
    half = size // 2
    low = karatsuba_convolution(formula, left[:half], right[:half])
    high = karatsuba_convolution(formula, left[half:], right[half:])
    left_cross = [parity(formula, [left[i], left[half + i]])
                  for i in range(half)]
    right_cross = [parity(formula, [right[i], right[half + i]])
                   for i in range(half)]
    mixed = karatsuba_convolution(formula, left_cross, right_cross)
    out = [ZERO for _ in range(2 * size - 1)]
    for i in range(size - 1):
        out[i] = xor_expression(out[i], low[i])
        cross = xor_expression(mixed[i], xor_expression(low[i], high[i]))
        out[i + half] = xor_expression(out[i + half], cross)
        out[i + size] = xor_expression(out[i + size], high[i])
    return out


def reduce_modulus(coefficients: list[Expression], n: int,
                   low_terms: list[int]) -> list[Expression]:
    """Reduce a polynomial by x^n plus its archived sparse low terms."""
    assert low_terms and all(0 <= power < n for power in low_terms)
    rows = coefficients[:]
    for degree in range(len(rows) - 1, n - 1, -1):
        for power in low_terms:
            index = degree - n + power
            rows[index] = xor_expression(rows[index], rows[degree])
    return rows[:n]


def field_product(formula: Formula, left_onb: list[int],
                  right_onb: list[int], bridge: dict) -> list[int]:
    """Encode one ONB field product through Karatsuba and sparse reduction."""
    n = bridge["field_degree"]
    assert len(left_onb) == len(right_onb) == n
    forward = bridge["onb_to_poly_basis_images"]
    inverse = bridge["poly_to_onb_basis_images"]
    low_terms = bridge["target_implementation_basis"]["low_terms"]
    left = linear_map(formula, left_onb, forward)
    right = linear_map(formula, right_onb, forward)
    padded = 1 << (n - 1).bit_length()
    left.extend([-1] * (padded - n))
    right.extend([-1] * (padded - n))
    convolution = karatsuba_convolution(formula, left, right)
    reduced = reduce_modulus(convolution, n, low_terms)
    output = [ZERO for _ in range(n)]
    for expression, image in zip(reduced, inverse):
        while image:
            bit = image & -image
            index = bit.bit_length() - 1
            output[index] = xor_expression(output[index], expression)
            image ^= bit
    return [materialize(formula, expression) for expression in output]


def s3_link(formula: Formula, a: list[int], b: list[int], c: list[int],
            bridge: dict, square_destinations: list[int]) -> None:
    """Encode (ab+(a+b)c)^2+abc+1=0 in the original ONB coordinates."""
    n = bridge["field_degree"]
    assert len(a) == len(b) == len(c) == len(square_destinations) == n
    ab = field_product(formula, a, b, bridge)
    a_plus_b = [parity(formula, [left, right])
                for left, right in zip(a, b)]
    cross = field_product(formula, a_plus_b, c, bridge)
    abc = field_product(formula, ab, c, bridge)
    for source, dest in enumerate(square_destinations):
        formula.xor_relation([ab[source], cross[source], abc[dest]], True)


def xor_images(mask: int, images: list[int]) -> int:
    result = 0
    while mask:
        bit = mask & -mask
        result ^= images[bit.bit_length() - 1]
        mask ^= bit
    return result


def karatsuba_bits(left: int, right: int, size: int) -> int:
    """Independent bit-level reference for the recursive convolution."""
    assert size > 0 and size & (size - 1) == 0
    if size == 1:
        return left & right & 1
    half = size // 2
    mask = (1 << half) - 1
    low_left, high_left = left & mask, left >> half
    low_right, high_right = right & mask, right >> half
    low = karatsuba_bits(low_left, low_right, half)
    high = karatsuba_bits(high_left, high_right, half)
    mixed = karatsuba_bits(low_left ^ high_left,
                           low_right ^ high_right, half)
    return low ^ ((mixed ^ low ^ high) << half) ^ (high << size)


def reduce_bits(value: int, n: int, low_terms: list[int]) -> int:
    modulus = (1 << n) | sum(1 << power for power in low_terms)
    while value.bit_length() > n:
        value ^= modulus << (value.bit_length() - n - 1)
    return value

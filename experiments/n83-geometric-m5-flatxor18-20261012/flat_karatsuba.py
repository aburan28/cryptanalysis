#!/usr/bin/env python3
"""Screen flattened Karatsuba output XORs on the frozen N83 target."""

import json
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "n83-geometric-m5-karatsuba18-20261012"
sys.path.insert(0, str(PARENT))
import base_run as runner


N = 83


def parity(value):
    return value.bit_count() & 1


def power_basis(onb):
    generator = onb.gamma(1)
    powers = []
    value = onb.one()
    for _ in range(2 * N - 1):
        powers.append(onb.toCoords(value))
        value = onb.mul(value, generator)
    rows = []
    for bit in range(N):
        left = sum(((powers[column] >> bit) & 1) << column
                   for column in range(N))
        rows.append(left | (1 << (N + bit)))
    for column in range(N):
        pivot = next(row for row in range(column, N)
                     if rows[row] >> column & 1)
        rows[column], rows[pivot] = rows[pivot], rows[column]
        for row in range(N):
            if row != column and (rows[row] >> column & 1):
                rows[row] ^= rows[column]
    assert all((row & ((1 << N) - 1)) == 1 << bit
               for bit, row in enumerate(rows))
    inverse_rows = [row >> N for row in rows]
    monomial_reductions = [sum(parity(mask & value) << bit
                               for bit, mask in enumerate(inverse_rows))
                           for value in powers]
    assert monomial_reductions[:N] == [1 << bit for bit in range(N)]
    return powers, inverse_rows, monomial_reductions


def selfcheck(onb):
    powers, inverse_rows, reductions = power_basis(onb)
    rng = random.Random(20261012)
    for _ in range(32):
        a = rng.getrandbits(N)
        b = rng.getrandbits(N)
        pa = sum(parity(row & a) << bit
                 for bit, row in enumerate(inverse_rows))
        pb = sum(parity(row & b) << bit
                 for bit, row in enumerate(inverse_rows))
        for onb_value, pb_value in ((a, pa), (b, pb)):
            reconstructed = 0
            for bit, value in enumerate(powers[:N]):
                if pb_value >> bit & 1:
                    reconstructed ^= value
            assert reconstructed == onb_value
        convolution = 0
        for bit in range(N):
            if pa >> bit & 1:
                convolution ^= pb << bit
        product = 0
        for bit, value in enumerate(reductions):
            if convolution >> bit & 1:
                product ^= value
        expected = onb.toCoords(onb.mul(onb.fromCoords(a),
                                        onb.fromCoords(b)))
        actual = 0
        for bit, value in enumerate(powers[:N]):
            if product >> bit & 1:
                actual ^= value
        assert actual == expected
    return {"status": "PASS", "random_pairs": 32,
            "basis_degree": N, "reduction_weight": sum(
                value.bit_count() for value in reductions)}


def from_onb(formula, vector, inverse_rows):
    return [runner.symbolic_xor_many(formula,
            [vector[bit] for bit in range(N) if row >> bit & 1])
            for row in inverse_rows]


def literal_expression(literal):
    if literal == -1:
        return 0
    if literal == 1:
        return 1
    if literal < 0:
        return 1 ^ (1 << -literal)
    return 1 << literal


def materialize_expression(formula, expression):
    constant = expression & 1
    variables = expression >> 1
    if not variables:
        return 1 if constant else -1
    if variables.bit_count() == 1:
        literal = variables.bit_length()
        return -literal if constant else literal
    output = formula.new()
    literals = []
    while variables:
        low = variables & -variables
        literals.append(low.bit_length())
        variables ^= low
    formula.xor_relation([output, *literals], bool(constant))
    return output


def karatsuba(formula, left, right):
    length = len(left)
    assert len(right) == length
    if length == 1:
        return [literal_expression(formula.and_gate(left[0], right[0]))]
    half = (length + 1) // 2
    a0 = left[:half]
    a1 = left[half:] + [-1] * (2 * half - length)
    b0 = right[:half]
    b1 = right[half:] + [-1] * (2 * half - length)
    low = karatsuba(formula, a0, b0)
    high = karatsuba(formula, a1, b1)
    middle = karatsuba(
        formula,
        [runner.symbolic_xor(formula, a, b) for a, b in zip(a0, a1)],
        [runner.symbolic_xor(formula, a, b) for a, b in zip(b0, b1)])
    result = [0] * (2 * length - 1)
    for index, value in enumerate(low):
        result[index] ^= value
    for index, value in enumerate(high):
        position = 2 * half + index
        if position < len(result):
            result[position] ^= value
    for index in range(2 * half - 1):
        value = middle[index] ^ low[index] ^ high[index]
        position = half + index
        if position < len(result):
            result[position] ^= value
    return result


def product_pb(formula, left, right, reductions):
    convolution = karatsuba(formula, left, right)
    output = []
    for bit in range(N):
        expression = 0
        for index, mask in enumerate(reductions):
            if mask >> bit & 1:
                expression ^= convolution[index]
        output.append(materialize_expression(formula, expression))
    return output


def square_rows(onb, powers, inverse_rows):
    return [sum(parity(mask & onb.toCoords(onb.sqr(onb.fromCoords(value))))
                << bit for bit, mask in enumerate(inverse_rows))
            for value in powers[:N]]


def s3_link_pb(formula, left, right, output, reductions, squares, one):
    pair = product_pb(formula, left, right, reductions)
    sum_lr = [runner.symbolic_xor(formula, a, b)
              for a, b in zip(left, right)]
    cross = product_pb(formula, sum_lr, output, reductions)
    triple = product_pb(formula, pair, output, reductions)
    pair_cross = [runner.symbolic_xor(formula, a, b)
                  for a, b in zip(pair, cross)]
    for bit in range(N):
        terms = [pair_cross[column] for column, mask in enumerate(squares)
                 if mask >> bit & 1]
        formula.xor_relation([*terms, triple[bit]], bool(one >> bit & 1))


def build(onb, target_x, target_choice=0):
    powers, inverse_rows, reductions = power_basis(onb)
    squares = square_rows(onb, powers, inverse_rows)
    one = sum(parity(row & onb.toCoords(onb.one())) << bit
              for bit, row in enumerate(inverse_rows))
    calls = []
    original = runner.s3_link_folded

    def defer(formula, left, right, output, multiplication, square_dest):
        calls.append((left, right, output))
        if len(calls) < 4:
            return
        p0, p1 = calls[0][:2]
        p2, p3 = calls[1][:2]
        p4 = calls[3][1]
        target = calls[3][2]
        leaf_pb = [from_onb(formula, leaf, inverse_rows)
                   for leaf in (p0, p1, p2, p3, p4)]
        target_pb = from_onb(formula, target, inverse_rows)
        i0, i1, i2 = [call[2] for call in calls[:3]]
        for a, b, c in (
            (leaf_pb[0], leaf_pb[1], i0),
            (leaf_pb[2], leaf_pb[3], i1),
            (i0, i1, i2),
            (i2, leaf_pb[4], target_pb),
        ):
            s3_link_pb(formula, a, b, c, reductions, squares, one)

    runner.s3_link_folded = defer
    try:
        formula, leaves, selector = runner.build_affine_formula(
            18, 1 << 81, [target_x] * 332, onb,
            target_choice=target_choice)
    finally:
        runner.s3_link_folded = original
    assert len(calls) == 4
    return formula, leaves, selector, inverse_rows


def main():
    parent = json.loads((PARENT / "width18_ordinary.json").read_text())
    onb = runner.field.Onb(N)
    correctness = selfcheck(onb)
    formula, _, _, _ = build(onb, parent["formula_target_x"])
    print(json.dumps({"karatsuba": runner.stats(formula),
                      "reference": parent["formula_shape"],
                      "selfcheck": correctness}, sort_keys=True))


if __name__ == "__main__":
    main()

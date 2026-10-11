"""Compile the public three-block quartic with shared factored coefficients."""

import hashlib
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
OLD = ROOT / "n41_single_branch_joint_sat_20261011" / "circuit.py"
COEFFICIENTS = ROOT / "n41_single_branch_joint_sat_20261011" / "coefficient_result.json"
NORM = ROOT / "n41_quartic_joint_public_20261010" / "norm_result.json"

spec = importlib.util.spec_from_file_location("n41_single_branch_old_circuit", OLD)
old = importlib.util.module_from_spec(spec)
spec.loader.exec_module(old)
Field = old.Field
source_columns = old.source_columns


def compile_quartic(circuit, values, norm):
    data = json.loads(COEFFICIENTS.read_text())
    assert data["status"] == "PASS_EXACT_PQ_COEFFICIENT_FACTORIZATION"
    assert data["source_sha256"] == hashlib.sha256(NORM.read_bytes()).hexdigest()
    a, s, z, P, Q = values
    one = circuit.constant(1)
    zero = circuit.constant(0)
    muls = 0
    squares = 0
    power_cache = {(axis, 0): one for axis in range(5)}
    for axis, value in enumerate(values):
        power_cache[axis, 1] = value

    def product(left, right):
        nonlocal muls
        if left == one:
            return right
        if right == one:
            return left
        if left == zero or right == zero:
            return zero
        muls += 1
        return circuit.mul(left, right)

    def square(value):
        nonlocal squares
        squares += 1
        return circuit.square(value)

    def power(axis, exponent):
        key = axis, exponent
        if key in power_cache:
            return power_cache[key]
        if exponent & 1:
            result = product(power(axis, exponent - 1), values[axis])
        else:
            result = square(power(axis, exponent // 2))
        power_cache[key] = result
        return result

    monomials = {(0, 0, 0): one,
                 (1, 0, 0): a, (0, 1, 0): s, (0, 0, 1): z}
    priority = (0, 1, 2)

    def monomial(exponents):
        if exponents in monomials:
            return monomials[exponents]
        if all(e % 2 == 0 for e in exponents):
            result = square(monomial(tuple(e // 2 for e in exponents)))
        else:
            axis = next(i for i in priority if exponents[i] & 1)
            prior = list(exponents)
            prior[axis] -= 1
            result = product(monomial(tuple(prior)), values[axis])
        monomials[exponents] = result
        return result

    factor_cache = {}
    coefficient_cache = {}
    pq_cache = {(0, 0): one}
    term_cache = {}

    def factor_value(factor):
        key = tuple(tuple(term[:3]) for term in factor["terms"])
        if key not in factor_cache:
            factor_cache[key] = old.add_many(circuit, [monomial(term) for term in key])
        result = factor_cache[key]
        multiplicity = factor["multiplicity"]
        if multiplicity == 2:
            result = square(result)
        elif multiplicity != 1:
            result = power_value(result, multiplicity)
        return result

    def power_value(value, exponent):
        result = one
        current = value
        while exponent:
            if exponent & 1:
                result = product(result, current)
            exponent >>= 1
            if exponent:
                current = square(current)
        return result

    def coefficient(row):
        key = tuple((factor["multiplicity"],
                     tuple(tuple(term) for term in factor["terms"]))
                    for factor in row["factors"])
        if key not in coefficient_cache:
            result = one
            for factor in row["factors"]:
                result = product(result, factor_value(factor))
            coefficient_cache[key] = result
        return coefficient_cache[key]

    def pq(exponents):
        if exponents not in pq_cache:
            ep, eq = exponents
            pq_cache[exponents] = product(power(3, ep), power(4, eq))
        return pq_cache[exponents]

    def term(row):
        key = (tuple(row["P_Q_exponents"]),
               tuple((f["multiplicity"], tuple(tuple(t) for t in f["terms"]))
                     for f in row["factors"]))
        if key not in term_cache:
            term_cache[key] = product(coefficient(row), pq(tuple(row["P_Q_exponents"])))
        return term_cache[key]

    A = old.add_many(circuit, [term(row) for row in data["records"]["A"]])
    B = old.add_many(circuit, [term(row) for row in data["records"]["B"]])
    return A, B, muls, squares


old.compile_quartic = compile_quartic


def build(circuit, field, columns, target_reciprocals):
    return old.build(circuit, field, columns, target_reciprocals)

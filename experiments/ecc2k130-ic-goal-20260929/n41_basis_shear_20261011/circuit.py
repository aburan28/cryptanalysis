"""Three public-linked quartics with rank-aware source field arithmetic."""

import importlib.util
import json
from pathlib import Path

from sparse import Algebra

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
HORNER = ROOT / "n41_single_branch_horner_20261011" / "circuit.py"
NORM = ROOT / "n41_quartic_joint_public_20261010" / "norm_result.json"

spec = importlib.util.spec_from_file_location("frozen_shared_horner", HORNER)
old = importlib.util.module_from_spec(spec)
spec.loader.exec_module(old)
Field = old.Field
source_columns = old.source_columns


def pair(circuit, field, algebra, left_mask, right_mask, rotation):
    source_basis = [1 << (j + 1) for j in range(6)]
    seed = [circuit.xor((a, b)) for a, b in zip(left_mask, right_mask)]
    a = algebra.expression((wire, field.frob(value, rotation))
                           for wire, value in zip(seed, source_basis))
    product_terms = []
    for diagonal in range(11):
        gates = [circuit.and_(left_mask[i], right_mask[j])
                 for i in range(6) for j in range(6) if i + j == diagonal]
        wire = circuit.xor(gates)
        product_terms.append((wire, field.frob(1 << (diagonal + 2), rotation)))
    product = algebra.expression(product_terms)
    return seed, a, product


def compile_quartic(algebra, values, norm):
    # For T=S+Z, replace S by T+Z exactly over GF(2). Keep source-derived
    # bases sparse while sharing the transformed coefficient subexpressions.
    values = (values[0], algebra.add(values[1], values[2]),
              values[2], values[3], values[4])
    order = (1, 4, 0, 2, 3)  # Shared sparse Horner: T, Q, a, Z, P.

    def shear(terms):
        out = set()
        for term in terms:
            exponent = term[1]
            for degree in range(exponent + 1):
                if degree & exponent != degree:
                    continue
                row = list(term)
                row[1] = degree
                row[2] += exponent - degree
                row = tuple(row)
                if row in out:
                    out.remove(row)
                else:
                    out.add(row)
        return frozenset(out)

    A_terms = shear(norm["A_terms"])
    B_terms = shear(norm["B_terms"])
    assert len(A_terms) == 40 and len(B_terms) == 16
    coefficient_cache = {}
    power_cache = {(axis, 0): algebra.one for axis in range(5)}
    power_cache.update({(axis, 1): value for axis, value in enumerate(values)})

    def power(axis, exponent):
        key = (axis, exponent)
        if key not in power_cache:
            half = power(axis, exponent // 2)
            result = algebra.square(half)
            if exponent & 1:
                result = algebra.mul(result, values[axis])
            power_cache[key] = result
        return power_cache[key]

    def coefficient(terms, depth):
        key = terms, depth
        if key in coefficient_cache:
            return coefficient_cache[key]
        if depth == len(order):
            assert terms == frozenset({(0, 0, 0, 0, 0)})
            result = algebra.one
        else:
            axis = order[depth]
            groups = {}
            for term in terms:
                exponent = term[axis]
                reduced = term[:axis] + (0,) + term[axis + 1:]
                groups.setdefault(exponent, set()).add(reduced)
            exponents = sorted(groups, reverse=True)
            current = exponents[0]
            result = coefficient(frozenset(groups[current]), depth + 1)
            for exponent in exponents[1:]:
                result = algebra.mul(result, power(axis, current - exponent))
                lower = coefficient(frozenset(groups[exponent]), depth + 1)
                result = algebra.add(result, lower)
                current = exponent
            if current:
                result = algebra.mul(result, power(axis, current))
        coefficient_cache[key] = result
        return result

    A = coefficient(A_terms, 0)
    B = coefficient(B_terms, 0)
    return A, B


def build(circuit, field, columns, target_reciprocals):
    norm = json.loads(NORM.read_text())
    assert circuit.n == 41 and len(columns) == 12 and len(target_reciprocals) == 2
    algebra = Algebra(circuit, field)
    masks = [[circuit.variable() for _ in range(6)] for _ in range(12)]
    output_z = [[circuit.variable() for _ in range(41)] for _ in range(3)]
    branch_w = [[circuit.variable() for _ in range(41)] for _ in range(3)]
    intermediate = [circuit.variable() for _ in range(41)]
    target_flag = circuit.variable()
    primary_variables = [*sum(masks, []), *sum(output_z, []),
                         *sum(branch_w, []), *intermediate, target_flag]
    for wires, table in zip(masks, columns):
        for code in range(64):
            if code not in table:
                old.clause(circuit, old.forbid(code, wires))
    column_forbids = 0
    for i in range(12):
        for j in range(i + 1, 12):
            for left, col_left in columns[i].items():
                for right, col_right in columns[j].items():
                    if col_left == col_right or (j == i + 1 and i % 2 == 0 and left >= right):
                        old.clause(circuit, old.forbid(left, masks[i]) +
                                   old.forbid(right, masks[j]))
                        column_forbids += 1
    pairs = [pair(circuit, field, algebra, masks[2*i], masks[2*i + 1], 5*i)
             for i in range(6)]
    for i, j in ((2, 3), (4, 5)):
        for bit in range(6):
            circuit.require_zero([circuit.xor((pairs[i][0][bit], pairs[j][0][bit]))])
    for bit in range(3, 6):
        circuit.require_zero([circuit.xor((pairs[2][0][bit], pairs[4][0][bit]))])
    quartic_start_ands = circuit.and_count
    for block in range(3):
        _, a, P = pairs[2 * block]
        _, b, Q = pairs[2 * block + 1]
        z_bits, w_bits = output_z[block], branch_w[block]
        z = algebra.from_bits(z_bits)
        w = algebra.from_bits(w_bits)
        S = algebra.add(a, b)
        circuit.require_zero(old.add_many(circuit, (circuit.square(w_bits),
                                                    w_bits, z_bits, S.bits())))
        A, B = compile_quartic(algebra, (a, S, z, P, Q), norm)
        circuit.require_zero(algebra.add(A, algebra.mul(w, B)).bits())
        old.nonzero(circuit, z_bits)
    quartic_ands = circuit.and_count - quartic_start_ands
    target = circuit.linear_element([target_flag],
                                    [target_reciprocals[0] ^ target_reciprocals[1]],
                                    target_reciprocals[0])
    old.s3(circuit, output_z[0], output_z[1], intermediate)
    old.s3(circuit, intermediate, output_z[2], target)
    old.nonzero(circuit, intermediate)
    return {"masks": masks, "output_z": output_z, "branch_w": branch_w,
            "intermediate": intermediate, "target_flag": target_flag,
            "primary_variables": primary_variables,
            "quartic_field_multiplications": algebra.sparse_mul_calls + algebra.generic_mul_calls,
            "quartic_field_squares": algebra.linear_squares,
            "quartic_sparse_multiplications": algebra.sparse_mul_calls,
            "quartic_generic_multiplications": algebra.generic_mul_calls,
            "quartic_sparse_pair_products": algebra.sparse_pair_products,
            "quartic_and_gates": quartic_ands,
            "column_and_order_forbids": column_forbids}

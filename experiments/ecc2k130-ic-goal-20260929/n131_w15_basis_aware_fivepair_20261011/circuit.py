"""Two source-aware quartics, one W15 pair, and a public-target S3 chain."""

import importlib.util
import json
import sys
from pathlib import Path

from arith_control import frob, mul, square, trace

HERE = Path(__file__).resolve().parent
GOAL = HERE.parent
N41 = GOAL / "n41_basis_aware_quartic_20261011"
W15 = GOAL / "n131_w15_coupled_sixpair_20261010/w15_circuit.py"
NORM = GOAL / "n41_quartic_joint_public_20261010/norm_result.json"
SUPPORT = GOAL / "n131_w15_coupled_sixpair_20261010/support_w15.tsv"
sys.path.insert(0, str(N41))
from sparse import Algebra  # noqa: E402


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


quartic = load("basis_aware_n41_quartic_compiler", N41 / "circuit.py")
original = load("basis_aware_n131_w15_circuit", W15)
N = 131
WIDTH = 15
ROTATIONS = (13, 26, 39, 52, 65)


class Field:
    def mul(self, a, b):
        return mul(a, b)

    def square(self, a):
        return square(a)


def columns():
    table = {int(a): int(b) for a, b in
             (line.split() for line in SUPPORT.read_text().splitlines())}
    assert len(table) == 16441 and len(set(table.values())) == 16381
    return table


def source_pair(circuit, algebra, left, right, rotation):
    seed = [circuit.xor((a, b)) for a, b in zip(left, right)]
    a = algebra.expression((wire, frob(1 << (j + 1), rotation))
                           for j, wire in enumerate(seed))
    product = []
    for diagonal in range(2 * WIDTH - 1):
        gates = [circuit.and_(left[i], right[j])
                 for i in range(WIDTH) for j in range(WIDTH)
                 if i + j == diagonal]
        product.append((circuit.xor(gates), frob(1 << (diagonal + 2), rotation)))
    return a, algebra.expression(product)


def build(circuit, target_reciprocals, fixed_columns):
    if circuit.n != N or len(target_reciprocals) != 4 or len(fixed_columns) != 2:
        raise ValueError("invalid N131 W15 five-pair quartic configuration")
    field = Field()
    table = columns()
    norm = json.loads(NORM.read_text())
    algebra = Algebra(circuit, field, dense_and_threshold=5000)
    masks = [[circuit.variable() for _ in range(WIDTH)] for _ in range(10)]
    flags = [circuit.variable() for _ in range(4)]
    original.nonzero(circuit, flags)
    for i in range(4):
        for j in range(i + 1, 4):
            circuit.clauses.append(f"-{flags[i]} -{flags[j]} 0")
    valid = set(table)
    for row in masks:
        for code in range(1 << WIDTH):
            if code not in valid:
                circuit.clauses.append(original.forbid(code, row))
    aliases = {}
    for mask, column in table.items():
        aliases.setdefault(column, []).append(mask)
    fixed_forbids = 0
    for row in masks:
        for column in fixed_columns:
            for mask in aliases[column]:
                circuit.clauses.append(original.forbid(mask, row))
                fixed_forbids += 1
    alias_forbids = 0
    for i in range(10):
        for j in range(i + 1, 10):
            differences = [circuit.xor((masks[i][bit], masks[j][bit]))
                           for bit in range(WIDTH)]
            original.nonzero(circuit, differences)
            for group in aliases.values():
                if len(group) > 1:
                    for a in group:
                        for b in group:
                            if a != b:
                                circuit.clauses.append(original.forbid(a, masks[i])[:-2] +
                                                       " " + original.forbid(b, masks[j]))
                                alias_forbids += 1
    output_z = [[circuit.variable() for _ in range(N)] for _ in range(2)]
    branch_w = [[circuit.variable() for _ in range(N)] for _ in range(2)]
    pair_z = [circuit.variable() for _ in range(N)]
    intermediate = [circuit.variable() for _ in range(N)]
    primary = [*sum(masks, []), *flags, *sum(output_z, []),
               *sum(branch_w, []), *pair_z, *intermediate]
    for row in (*output_z, pair_z, intermediate):
        original.nonzero(circuit, row)
        circuit.require_zero([circuit.xor((row[0], row[129]))])
    for flag, value in zip(flags, target_reciprocals):
        if trace(value):
            circuit.clauses.append(f"-{flag} 0")
    quartic_start = circuit.and_count
    for block in range(2):
        pair_index = 2 * block
        a, P = source_pair(circuit, algebra, masks[2 * pair_index],
                           masks[2 * pair_index + 1], ROTATIONS[pair_index])
        b, Q = source_pair(circuit, algebra, masks[2 * pair_index + 2],
                           masks[2 * pair_index + 3], ROTATIONS[pair_index + 1])
        z_bits, w_bits = output_z[block], branch_w[block]
        z, w = algebra.from_bits(z_bits), algebra.from_bits(w_bits)
        S = algebra.add(a, b)
        circuit.require_zero(quartic.old.add_many(circuit, (
            circuit.square(w_bits), w_bits, z_bits, S.bits())))
        A, B = quartic.compile_quartic(algebra, (a, S, z, P, Q), norm)
        circuit.require_zero(algebra.add(A, algebra.mul(w, B)).bits())
    quartic_ands = circuit.and_count - quartic_start
    source_basis = [frob(1 << (j + 1), ROTATIONS[4]) for j in range(WIDTH)]
    left_bits, right_bits = masks[8], masks[9]
    left = circuit.linear_element(left_bits, source_basis)
    right = circuit.linear_element(right_bits, source_basis)
    product_basis = [frob(1 << (j + 2), ROTATIONS[4])
                     for j in range(2 * WIDTH - 1)]
    pair_ands = original.bilinear_pair_constraint(
        circuit, field, left_bits, right_bits, left, right, pair_z, product_basis)
    original.reciprocal_s3(circuit, output_z[0], output_z[1], intermediate)
    target = circuit.linear_element(flags, target_reciprocals)
    target_ands = original.target_linear_s3(
        circuit, field, intermediate, pair_z, flags, target_reciprocals, target)
    return {"masks": masks, "flags": flags, "output_z": output_z,
            "branch_w": branch_w, "pair_z": pair_z,
            "intermediate": intermediate, "primary_variables": primary,
            "quartic_and_gates": quartic_ands,
            "quartic_sparse_multiplications": algebra.sparse_mul_calls,
            "quartic_generic_multiplications": algebra.generic_mul_calls,
            "quartic_sparse_pair_products": algebra.sparse_pair_products,
            "last_pair_bilinear_ands": pair_ands,
            "target_linear_ands": target_ands,
            "fixed_column_forbids": fixed_forbids,
            "alias_forbids": alias_forbids}

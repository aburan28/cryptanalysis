"""Exact N41 public relation circuit with halftrace-cubic S3 links."""

import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
BASE = ROOT / "n41_basis_aware_quartic_20261011"
sys.path.insert(0, str(BASE))
from sparse import Algebra  # noqa: E402
spec = importlib.util.spec_from_file_location("frozen_basis_circuit", BASE / "circuit.py")
old = importlib.util.module_from_spec(spec)
spec.loader.exec_module(old)
Field = old.Field
source_columns = old.source_columns


def halftrace(field, value):
    result = 0
    for _ in range((field.n + 1) // 2):
        result ^= value
        value = field.square(field.square(value))
    return result


def trace(field, value):
    result = 0
    for _ in range(field.n):
        result ^= value
        value = field.square(value)
    assert result in (0, 1)
    return result


def link(circuit, field, algebra, left, right, output, branch, ht_square_basis, trace_basis):
    """S3(left,right,output), with one exact Artin--Schreier branch bit."""
    triple = algebra.mul(algebra.mul(left, right), output)
    total = algebra.add(left, right, output)
    ht = circuit.linear_element(total.bits(), ht_square_basis)
    circuit.require_zero(algebra.add(triple, algebra.from_bits(ht),
                                     algebra.expression(((branch, 1),))).bits())
    tr = circuit.xor(wire for wire, bit in zip(total.bits(), trace_basis) if bit)
    circuit.require_zero([tr])


def build(circuit, field, columns, target_reciprocals):
    assert circuit.n == 41 and len(columns) == 12 and len(target_reciprocals) == 2
    algebra = Algebra(circuit, field)
    masks = [[circuit.variable() for _ in range(6)] for _ in range(12)]
    pair_z = [[circuit.variable() for _ in range(41)] for _ in range(6)]
    output_z = [[circuit.variable() for _ in range(41)] for _ in range(3)]
    intermediate = [circuit.variable() for _ in range(41)]
    target_flag = circuit.variable()
    branch_w = [[circuit.variable()] for _ in range(11)]
    primary_variables = [*sum(masks, []), *sum(pair_z, []), *sum(output_z, []),
                         *intermediate, target_flag, *sum(branch_w, [])]
    for wires, table in zip(masks, columns):
        for code in range(64):
            if code not in table:
                old.old.clause(circuit, old.old.forbid(code, wires))
    column_forbids = 0
    for i in range(12):
        for j in range(i + 1, 12):
            for left, col_left in columns[i].items():
                for right, col_right in columns[j].items():
                    if col_left == col_right or (j == i + 1 and i % 2 == 0 and left >= right):
                        old.old.clause(circuit, old.old.forbid(left, masks[i]) +
                                       old.old.forbid(right, masks[j]))
                        column_forbids += 1
    # H(v²) is linear in the coordinate bits of v.
    ht_square_basis = [halftrace(field, field.square(1 << i)) for i in range(41)]
    trace_basis = [trace(field, 1 << i) for i in range(41)]
    pairs = [old.pair(circuit, field, algebra, masks[2*i], masks[2*i+1], 5*i)
             for i in range(6)]
    for i, j in ((2, 3), (4, 5)):
        for bit in range(6):
            circuit.require_zero([circuit.xor((pairs[i][0][bit], pairs[j][0][bit]))])
    for bit in range(3, 6):
        circuit.require_zero([circuit.xor((pairs[2][0][bit], pairs[4][0][bit]))])
    pair_start_ands = circuit.and_count
    for i, (_, seed, product) in enumerate(pairs):
        c = algebra.from_bits(pair_z[i])
        # The source sum is seed, and its product is restricted to 11 basis images.
        pc = algebra.mul(product, c)
        total = algebra.add(seed, c)
        ht = circuit.linear_element(total.bits(), ht_square_basis)
        circuit.require_zero(algebra.add(pc, algebra.from_bits(ht),
                                         algebra.expression(((branch_w[i][0], 1),))).bits())
        tr = circuit.xor(wire for wire, bit in zip(total.bits(), trace_basis) if bit)
        circuit.require_zero([tr])
        old.old.nonzero(circuit, pair_z[i])
    pair_ands = circuit.and_count - pair_start_ands
    link_start_ands = circuit.and_count
    for block in range(3):
        link(circuit, field, algebra, algebra.from_bits(pair_z[2*block]),
             algebra.from_bits(pair_z[2*block+1]), algebra.from_bits(output_z[block]),
             branch_w[6+block][0], ht_square_basis, trace_basis)
        old.old.nonzero(circuit, output_z[block])
    link(circuit, field, algebra, algebra.from_bits(output_z[0]),
         algebra.from_bits(output_z[1]), algebra.from_bits(intermediate),
         branch_w[9][0], ht_square_basis, trace_basis)
    old.old.nonzero(circuit, intermediate)
    target = circuit.linear_element([target_flag],
                                    [target_reciprocals[0] ^ target_reciprocals[1]],
                                    target_reciprocals[0])
    link(circuit, field, algebra, algebra.from_bits(intermediate),
         algebra.from_bits(output_z[2]), algebra.from_bits(target),
         branch_w[10][0], ht_square_basis, trace_basis)
    return {"masks": masks, "pair_z": pair_z, "output_z": output_z,
            "branch_w": branch_w, "intermediate": intermediate,
            "target_flag": target_flag, "primary_variables": primary_variables,
            "pair_and_gates": pair_ands,
            "joint_link_and_gates": circuit.and_count - link_start_ands,
            "column_and_order_forbids": column_forbids,
            "quartic_field_multiplications": 0, "quartic_field_squares": 0}

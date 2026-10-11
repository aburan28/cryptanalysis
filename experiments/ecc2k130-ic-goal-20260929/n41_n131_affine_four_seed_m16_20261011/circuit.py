"""Sixteen-source N41 halftrace-cubic circuit with four affine XOR seeds."""

import importlib.util
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UPSTREAM = ROOT / "n41_transport_cubic_s8_20261011" / "circuit.py"
spec = importlib.util.spec_from_file_location("upstream_n41_cubic", UPSTREAM)
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)

N = 41
D = 6
SEEDS = (32, 33, 34, 35)
ROTATIONS = (0, 5, 10, 15, 20, 25, 30, 35)
Field = base.Field


def build(circuit, field, columns, target_zs):
    assert circuit.n == N and len(columns) == 32 and len(target_zs) in (1, 4)
    algebra = base.shared.Algebra(circuit, field)
    masks = [[circuit.variable() for _ in range(D)] for _ in range(16)]
    pair_z = [[circuit.variable() for _ in range(N)] for _ in range(8)]
    middle_z = [[circuit.variable() for _ in range(N)] for _ in range(4)]
    upper_z = [[circuit.variable() for _ in range(N)] for _ in range(2)]
    branch = [circuit.variable() for _ in range(15)]
    flags = [circuit.variable() for _ in range(2)] if len(target_zs) == 4 else []
    primary = [*sum(masks, []), *sum(pair_z, []), *sum(middle_z, []),
               *sum(upper_z, []), *branch, *flags]
    root, nodes = base.shared.build_bdd(columns)
    for mask in masks:
        base.shared.emit_bdd(circuit, root, nodes, mask)
    # Seeds 32..35 have fixed high four bits and two free low bits.
    for index in range(8):
        left, right = masks[2*index:2*index+2]
        circuit.require_zero([left[5]])  # canonical orientation
        for bit in range(2, D):
            expected = int(bit == 5)
            circuit.require_zero([circuit.xor((left[bit], right[bit],
                                             -1 if expected else 0))])
    groups = defaultdict(list)
    for mask, column in columns.items():
        groups[column].append(mask)
    collisions = [tuple(sorted((a, b))) for members in groups.values()
                  for i, a in enumerate(members) for b in members[i+1:]]
    helper = base.shared.old.old.old
    for i in range(16):
        for j in range(i+1, 16):
            helper.clause(circuit, [circuit.xor((a, b))
                                    for a, b in zip(masks[i], masks[j])])
            for a, b in collisions:
                helper.clause(circuit, helper.forbid(a, masks[i]) +
                              helper.forbid(b, masks[j]))
                helper.clause(circuit, helper.forbid(b, masks[i]) +
                              helper.forbid(a, masks[j]))
    source_ands = circuit.and_count
    ht_basis = [base.shared.old.halftrace(field, field.square(1 << i))
                for i in range(N)]
    tr_basis = [base.shared.old.trace(field, 1 << i) for i in range(N)]
    source_pairs = [base.shared.pair(circuit, field, algebra,
                                     masks[2*i], masks[2*i+1], ROTATIONS[i])
                    for i in range(8)]
    product_ands = circuit.and_count - source_ands
    for i, (seed, product) in enumerate(source_pairs):
        output = algebra.from_bits(pair_z[i])
        half = circuit.linear_element(algebra.add(seed, output).bits(), ht_basis)
        circuit.require_zero(algebra.add(
            algebra.mul(product, output), algebra.from_bits(half),
            algebra.expression(((branch[i], 1),))).bits())
        trace = circuit.xor(wire for wire, bit in
                            zip(algebra.add(seed, output).bits(), tr_basis) if bit)
        circuit.require_zero([trace])
        helper.nonzero(circuit, pair_z[i])
    pair_ands = circuit.and_count - source_ands - product_ands
    for level_inputs, level_outputs, offset in (
            (pair_z, middle_z, 8), (middle_z, upper_z, 12)):
        for i, output in enumerate(level_outputs):
            base.shared.old.link(circuit, field, algebra,
                                 algebra.from_bits(level_inputs[2*i]),
                                 algebra.from_bits(level_inputs[2*i+1]),
                                 algebra.from_bits(output), branch[offset+i],
                                 ht_basis, tr_basis)
            helper.nonzero(circuit, output)
    if len(target_zs) == 1:
        target = circuit.constant(target_zs[0])
    else:
        f0, f1 = flags
        cross = circuit.and_(f0, f1)
        target = circuit.linear_element(
            (f0, f1, cross),
            (target_zs[0] ^ target_zs[1],
             target_zs[0] ^ target_zs[2],
             target_zs[0] ^ target_zs[1] ^ target_zs[2] ^ target_zs[3]),
            target_zs[0])
    base.shared.old.link(circuit, field, algebra,
                         algebra.from_bits(upper_z[0]),
                         algebra.from_bits(upper_z[1]),
                         algebra.from_bits(target), branch[14], ht_basis,
                         tr_basis)
    return {"masks": masks, "pair_z": pair_z, "middle_z": middle_z,
            "upper_z": upper_z, "branch": branch, "target_flags": flags,
            "primary_variables": primary, "source_bdd_nodes": len(nodes),
            "source_and_gates": source_ands,
            "source_product_and_gates": product_ands,
            "pair_link_and_gates": pair_ands,
            "column_collision_mask_pairs": len(collisions)}

"""Eight-slot N41 W9 halftrace-cubic circuit for the transported public point."""

import importlib.util
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
N131 = ROOT/'n131_w18_cubic_s8_20261011/circuit.py'
spec = importlib.util.spec_from_file_location('frozen_n131_cubic_builder', N131)
shared = importlib.util.module_from_spec(spec)
spec.loader.exec_module(shared)
shared.N = 41
shared.D = 9
shared.ROTATIONS = (0, 0, 10, 10, 20, 20, 30, 30)

N = 41
D = 9
ROTATIONS = shared.ROTATIONS
Field = shared.old.Field


def build(circuit, field, columns, target_zs):
    assert circuit.n == N and len(columns) == 259 and len(target_zs) in (1, 4)
    assert len(set(columns.values())) == 251
    algebra = shared.Algebra(circuit, field)
    masks = [[circuit.variable() for _ in range(D)] for _ in range(8)]
    pair_z = [[circuit.variable() for _ in range(N)] for _ in range(4)]
    middle_z = [[circuit.variable() for _ in range(N)] for _ in range(2)]
    branch = [circuit.variable() for _ in range(7)]
    target_flags = [circuit.variable() for _ in range(2)] if len(target_zs) == 4 else []
    primary = [*sum(masks, []), *sum(pair_z, []), *sum(middle_z, []),
               *branch, *target_flags]
    root, nodes = shared.build_bdd(columns)
    for mask in masks:
        shared.emit_bdd(circuit, root, nodes, mask)
    source_ands = circuit.and_count
    groups = defaultdict(list)
    for mask, column in columns.items():
        groups[column].append(mask)
    collisions = [tuple(sorted((a, b))) for members in groups.values()
                  for index, a in enumerate(members) for b in members[index+1:]]
    assert len(collisions) == 12
    for i in range(8):
        for j in range(i+1, 8):
            shared.old.old.old.clause(circuit, [circuit.xor((a, b))
                                                for a, b in zip(masks[i], masks[j])])
            for a, b in collisions:
                shared.old.old.old.clause(circuit, shared.old.old.old.forbid(a, masks[i]) +
                                          shared.old.old.old.forbid(b, masks[j]))
                shared.old.old.old.clause(circuit, shared.old.old.old.forbid(b, masks[i]) +
                                          shared.old.old.old.forbid(a, masks[j]))
    ht_basis = [shared.old.halftrace(field, field.square(1 << i)) for i in range(N)]
    tr_basis = [shared.old.trace(field, 1 << i) for i in range(N)]
    source_pairs = [shared.pair(circuit, field, algebra, masks[2*i], masks[2*i+1],
                                ROTATIONS[2*i]) for i in range(4)]
    source_product_ands = circuit.and_count-source_ands
    pair_start = circuit.and_count
    for i, (s, p) in enumerate(source_pairs):
        c = algebra.from_bits(pair_z[i])
        pc = algebra.mul(p, c)
        total = algebra.add(s, c)
        ht = circuit.linear_element(total.bits(), ht_basis)
        circuit.require_zero(algebra.add(pc, algebra.from_bits(ht),
                                         algebra.expression(((branch[i], 1),))).bits())
        tr = circuit.xor(wire for wire, bit in zip(total.bits(), tr_basis) if bit)
        circuit.require_zero([tr])
        shared.old.old.old.nonzero(circuit, pair_z[i])
    pair_ands = circuit.and_count-pair_start
    joint_start = circuit.and_count
    for i in range(2):
        shared.old.link(circuit, field, algebra, algebra.from_bits(pair_z[2*i]),
                        algebra.from_bits(pair_z[2*i+1]), algebra.from_bits(middle_z[i]),
                        branch[4+i], ht_basis, tr_basis)
        shared.old.old.old.nonzero(circuit, middle_z[i])
    if len(target_zs) == 1:
        target = circuit.constant(target_zs[0])
    else:
        f0, f1 = target_flags
        f01 = circuit.and_(f0, f1)
        target = circuit.linear_element((f0, f1, f01),
                                        (target_zs[0]^target_zs[1],
                                         target_zs[0]^target_zs[2],
                                         target_zs[0]^target_zs[1]^target_zs[2]^target_zs[3]),
                                        target_zs[0])
    shared.old.link(circuit, field, algebra, algebra.from_bits(middle_z[0]),
                    algebra.from_bits(middle_z[1]), algebra.from_bits(target),
                    branch[6], ht_basis, tr_basis)
    return {'masks': masks, 'pair_z': pair_z, 'middle_z': middle_z,
            'branch': branch, 'target_flags': target_flags,
            'primary_variables': primary, 'bdd_nodes': len(nodes),
            'source_and_gates': source_ands,
            'source_product_and_gates': source_product_ands,
            'pair_link_and_gates': pair_ands,
            'joint_link_and_gates': circuit.and_count-joint_start,
            'nontrivial_column_collision_pairs': len(collisions),
            'target_selector_cross_term':
                target_zs[0]^target_zs[1]^target_zs[2]^target_zs[3]
                if len(target_zs) == 4 else 0}

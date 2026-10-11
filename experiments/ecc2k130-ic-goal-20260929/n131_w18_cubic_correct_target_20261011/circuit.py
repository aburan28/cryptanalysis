"""Exact W18 eight-slot N131 circuit with halftrace-cubic links."""

import importlib.util
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path('/Volumes/SSD990/cryptanalysis/experiments/ecc2k130-ic-goal-20260929')
N41 = ROOT / 'n41_cubic_halftrace_public_20261011'
SPARSE = ROOT / 'n41_basis_aware_quartic_20261011'
sys.path.insert(0, str(SPARSE))
from sparse import Algebra  # noqa: E402

spec = importlib.util.spec_from_file_location('frozen_n41_cubic', N41 / 'circuit.py')
old = importlib.util.module_from_spec(spec)
spec.loader.exec_module(old)

N = 131
D = 18
ROTATIONS = (0, 0, 32, 32, 64, 64, 96, 96)


class Field(old.Field):
    n = N
    modulus = (1 << N) | (1 << 13) | (1 << 2) | (1 << 1) | 1


def build_bdd(codes):
    unique, nodes = {}, {}

    def visit(subset, depth):
        if not subset:
            return 0
        if len(subset) == 1 << (D-depth):
            return 1
        if depth == D:
            return 1
        bit = D-depth-1
        low = [x for x in subset if not (x >> bit & 1)]
        high = [x for x in subset if x >> bit & 1]
        a, b = visit(low, depth+1), visit(high, depth+1)
        if a == b:
            return a
        key = (bit, a, b)
        if key not in unique:
            number = len(unique)+2
            unique[key] = number
            nodes[number] = key
        return unique[key]

    return visit(sorted(codes), 0), nodes


def emit_bdd(circuit, root, nodes, mask):
    wires = {0: 0, 1: -1}
    for node in sorted(nodes):
        bit, low, high = nodes[node]
        a, b = wires[low], wires[high]
        wires[node] = circuit.xor((a, circuit.and_(mask[bit], circuit.xor((a, b)))))
    circuit.require_zero([circuit.xor((wires[root], -1))])


def pair(circuit, field, algebra, left, right, rotation):
    seed = [circuit.xor((a, b)) for a, b in zip(left, right)]
    basis = [1 << (i+1) for i in range(D)]
    s = algebra.expression((wire, field.frob(value, rotation))
                           for wire, value in zip(seed, basis))
    diagonals = []
    for k in range(2*D-1):
        gates = [circuit.and_(left[i], right[j])
                 for i in range(D) for j in range(D) if i+j == k]
        diagonals.append((circuit.xor(gates), field.frob(1 << (k+2), rotation)))
    return s, algebra.expression(diagonals)


def build(circuit, field, columns, target_zs):
    assert circuit.n == N and len(target_zs) in (1, 4)
    assert len(columns) == 131307 and len(set(columns.values())) == 131068
    algebra = Algebra(circuit, field)
    masks = [[circuit.variable() for _ in range(D)] for _ in range(8)]
    pair_z = [[circuit.variable() for _ in range(N)] for _ in range(4)]
    middle_z = [[circuit.variable() for _ in range(N)] for _ in range(2)]
    branch = [circuit.variable() for _ in range(7)]
    target_flags = [circuit.variable() for _ in range(2)] if len(target_zs) == 4 else []
    primary = [*sum(masks, []), *sum(pair_z, []), *sum(middle_z, []),
               *branch, *target_flags]
    root, nodes = build_bdd(columns)
    for mask in masks:
        emit_bdd(circuit, root, nodes, mask)
    source_ands = circuit.and_count
    groups = defaultdict(list)
    for mask, column in columns.items():
        groups[column].append(mask)
    collisions = [tuple(sorted((a, b))) for members in groups.values()
                  for index, a in enumerate(members) for b in members[index+1:]]
    assert len(collisions) == 243
    for i in range(8):
        for j in range(i+1, 8):
            old.old.old.clause(circuit, [circuit.xor((a, b))
                                         for a, b in zip(masks[i], masks[j])])
            for a, b in collisions:
                old.old.old.clause(circuit, old.old.old.forbid(a, masks[i]) +
                                   old.old.old.forbid(b, masks[j]))
                old.old.old.clause(circuit, old.old.old.forbid(b, masks[i]) +
                                   old.old.old.forbid(a, masks[j]))
    ht_basis = [old.halftrace(field, field.square(1 << i)) for i in range(N)]
    tr_basis = [old.trace(field, 1 << i) for i in range(N)]
    source_pairs = [pair(circuit, field, algebra, masks[2*i], masks[2*i+1],
                         ROTATIONS[2*i]) for i in range(4)]
    source_product_ands = circuit.and_count - source_ands
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
        old.old.old.nonzero(circuit, pair_z[i])
    pair_ands = circuit.and_count - pair_start
    joint_start = circuit.and_count
    for i in range(2):
        old.link(circuit, field, algebra, algebra.from_bits(pair_z[2*i]),
                 algebra.from_bits(pair_z[2*i+1]), algebra.from_bits(middle_z[i]),
                 branch[4+i], ht_basis, tr_basis)
        old.old.old.nonzero(circuit, middle_z[i])
    if len(target_zs) == 1:
        target = circuit.constant(target_zs[0])
    else:
        f0, f1 = target_flags
        cross = circuit.and_(f0, f1)
        target = circuit.linear_element(
            (f0, f1, cross),
            (target_zs[0] ^ target_zs[1],
             target_zs[0] ^ target_zs[2],
             target_zs[0] ^ target_zs[1] ^ target_zs[2] ^ target_zs[3]),
            target_zs[0])
    old.link(circuit, field, algebra, algebra.from_bits(middle_z[0]),
             algebra.from_bits(middle_z[1]), algebra.from_bits(target),
             branch[6], ht_basis, tr_basis)
    return {'masks': masks, 'pair_z': pair_z, 'middle_z': middle_z,
            'branch': branch, 'target_flags': target_flags,
            'primary_variables': primary, 'bdd_nodes': len(nodes),
            'source_and_gates': source_ands,
            'source_product_and_gates': source_product_ands,
            'pair_link_and_gates': pair_ands,
            'joint_link_and_gates': circuit.and_count-joint_start,
            'nontrivial_column_collision_pairs': len(collisions)}

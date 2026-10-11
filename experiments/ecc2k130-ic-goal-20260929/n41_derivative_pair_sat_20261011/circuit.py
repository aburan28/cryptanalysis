"""Exact free-branch N41 two-pair circuit using derivative equations."""

import importlib.util
from pathlib import Path


HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / "n41_two_pair_relaxation_20261011/circuit.py"
spec = importlib.util.spec_from_file_location("frozen_n41_two_pair", SOURCE)
old = importlib.util.module_from_spec(spec)
spec.loader.exec_module(old)

Field = old.Field
Algebra = old.Algebra
N = 41
ROTATIONS = (20, 30)


def build(circuit, field, target_z):
    assert circuit.n == N and 0 < target_z < 1 << N
    algebra = Algebra(circuit, field)
    seed_sum = [[circuit.variable() for _ in range(6)] for _ in range(2)]
    product = [[circuit.variable() for _ in range(11)] for _ in range(2)]
    pair_z = [[circuit.variable() for _ in range(N)] for _ in range(2)]
    primary = [*sum(seed_sum, []), *sum(product, []), *sum(pair_z, [])]
    pair_ands = []
    for i, rotation in enumerate(ROTATIONS):
        old.base.shared.old.old.old.nonzero(circuit, seed_sum[i])
        old.base.shared.old.old.old.nonzero(circuit, pair_z[i])
        s = algebra.expression((wire, field.frob(1 << (j + 1), rotation))
                               for j, wire in enumerate(seed_sum[i]))
        p = algebra.expression((wire, field.frob(1 << (j + 2), rotation))
                               for j, wire in enumerate(product[i]))
        z = algebra.from_bits(pair_z[i])
        v = algebra.mul(p, z)
        total = algebra.add(s, z)
        circuit.require_zero(algebra.add(algebra.square(v), v,
                                         algebra.square(total)).bits())
        pair_ands.append(circuit.and_count)
    left, right = (algebra.from_bits(bits) for bits in pair_z)
    target = algebra.from_bits(circuit.constant(target_z))
    triple = algebra.mul(algebra.mul(left, right), target)
    total = algebra.add(left, right, target)
    circuit.require_zero(algebra.add(algebra.square(triple), triple,
                                     algebra.square(total)).bits())
    return {"seed_sum": seed_sum, "product": product, "pair_z": pair_z,
            "primary_variables": primary, "pair_and_checkpoints": pair_ands,
            "relaxation": "free product-span coefficients with exact existential branch elimination"}

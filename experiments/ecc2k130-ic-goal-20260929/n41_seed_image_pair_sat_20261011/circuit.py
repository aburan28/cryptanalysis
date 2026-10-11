"""Two target-conditioned pairs with exact seed-product image constraints."""

import importlib.util
from pathlib import Path


HERE = Path(__file__).resolve().parent
BASE = HERE.parent / "n41_derivative_pair_sat_20261011/circuit.py"
spec = importlib.util.spec_from_file_location("frozen_derivative_pair", BASE)
old = importlib.util.module_from_spec(spec)
spec.loader.exec_module(old)

Field = old.Field
Algebra = old.Algebra


def nonzero(circuit, wires):
    circuit.clauses.append(" ".join(map(str, wires)) + " 0")


def build(circuit, field, target_z):
    assert circuit.n == 41 and 0 < target_z < 1 << 41
    algebra = Algebra(circuit, field)
    seed = [[circuit.variable() for _ in range(6)] for _ in range(2)]
    first = [[circuit.variable() for _ in range(6)] for _ in range(2)]
    pair_z = [[circuit.variable() for _ in range(41)] for _ in range(2)]
    primary = [*sum(seed, []), *sum(first, []), *sum(pair_z, [])]
    product_checkpoints = []
    for i, rotation in enumerate((20, 30)):
        second = [circuit.xor((a, s)) for a, s in zip(first[i], seed[i])]
        nonzero(circuit, seed[i])
        nonzero(circuit, first[i])
        nonzero(circuit, second)
        nonzero(circuit, pair_z[i])
        a = algebra.expression((wire, field.frob(1 << (j+1), rotation))
                               for j, wire in enumerate(first[i]))
        s = algebra.expression((wire, field.frob(1 << (j+1), rotation))
                               for j, wire in enumerate(seed[i]))
        p = algebra.add(algebra.square(a), algebra.mul(a, s))
        product_checkpoints.append(circuit.and_count)
        z = algebra.from_bits(pair_z[i])
        v = algebra.mul(p, z)
        total = algebra.add(s, z)
        circuit.require_zero(algebra.add(algebra.square(v), v,
                                         algebra.square(total)).bits())
    left, right = (algebra.from_bits(bits) for bits in pair_z)
    target = algebra.from_bits(circuit.constant(target_z))
    triple = algebra.mul(algebra.mul(left, right), target)
    total = algebra.add(left, right, target)
    circuit.require_zero(algebra.add(algebra.square(triple), triple,
                                     algebra.square(total)).bits())
    return {"seed": seed, "first": first, "pair_z": pair_z,
            "primary_variables": primary,
            "product_and_checkpoints": product_checkpoints,
            "source_policy": "all nonzero W6 masks; second=first xor seed; exact product image"}

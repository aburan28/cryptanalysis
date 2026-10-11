"""Implicit exact N41 two-free-pair relaxation with a target S3 link."""

import importlib.util
import sys
from pathlib import Path

ROOT = Path('/Volumes/SSD990/cryptanalysis/experiments/ecc2k130-ic-goal-20260929')
BASE = ROOT/'n41_cubic_halftrace_public_20261011'
SPARSE = ROOT/'n41_basis_aware_quartic_20261011'
sys.path.insert(0, str(SPARSE))
from sparse import Algebra  # noqa: E402

spec = importlib.util.spec_from_file_location('frozen_n41_cubic_relaxed', BASE/'circuit.py')
old = importlib.util.module_from_spec(spec)
spec.loader.exec_module(old)

N = 41
ROTATIONS = (20, 30)


def trace_basis(field):
    return [old.trace(field, 1 << i) for i in range(N)]


def build(circuit, field, target_point):
    assert circuit.n == N and len(target_point) == 2 and target_point[0]
    algebra = Algebra(circuit, field)
    seed = [[circuit.variable() for _ in range(6)] for _ in range(2)]
    product = [[circuit.variable() for _ in range(11)] for _ in range(2)]
    z = [[circuit.variable() for _ in range(N)] for _ in range(2)]
    x = [[circuit.variable() for _ in range(N)] for _ in range(2)]
    branch = [circuit.variable() for _ in range(3)]
    primary = [*sum(seed, []), *sum(product, []), *sum(z, []),
               *sum(x, []), *branch]
    ht_basis = [old.halftrace(field, field.square(1 << i)) for i in range(N)]
    tr_basis = trace_basis(field)
    for i, rotation in enumerate(ROTATIONS):
        circuit.clauses.append(' '.join(map(str, seed[i]))+' 0')
        circuit.clauses.append(' '.join(map(str, z[i]))+' 0')
        s = algebra.expression((wire, field.frob(1 << (j+1), rotation))
                               for j, wire in enumerate(seed[i]))
        p = algebra.expression((wire, field.frob(1 << (j+2), rotation))
                               for j, wire in enumerate(product[i]))
        zz = algebra.from_bits(z[i])
        xx = algebra.from_bits(x[i])
        ht = circuit.linear_element(algebra.add(s, zz).bits(), ht_basis)
        circuit.require_zero(algebra.add(algebra.mul(p, zz),
                                         algebra.from_bits(ht),
                                         algebra.expression(((branch[i], 1),))).bits())
        # The native enumerator retains exactly nonzero trace-zero reciprocals.
        circuit.require_zero([circuit.xor(w for w, bit in zip(z[i], tr_basis) if bit)])
        # x=1/z and Tr(x+z^2)=0 are precisely the rational curve-lift test.
        circuit.require_zero(algebra.add(algebra.mul(xx, zz), algebra.one).bits())
        rational = circuit.xor(w for w, bit in zip(x[i], tr_basis) if bit)
        rational = circuit.xor((rational,
                                circuit.xor(w for w, bit in zip(z[i], tr_basis) if bit)))
        circuit.require_zero([rational])
    target_z = field.inv(target_point[0])
    old.link(circuit, field, algebra, algebra.from_bits(z[0]),
             algebra.from_bits(z[1]), algebra.expression(((-1, target_z),)),
             branch[2], ht_basis, tr_basis)
    return {'seed': seed, 'product': product, 'z': z, 'x': x,
            'branch': branch, 'primary': primary, 'target_z': target_z,
            'rotations': ROTATIONS}

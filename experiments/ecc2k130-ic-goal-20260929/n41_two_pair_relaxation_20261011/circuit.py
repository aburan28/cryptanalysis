"""Target-conditioned two-pair W6 sparse-product relaxation on N41."""

import importlib.util
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
BASE=ROOT/'n41_transport_cubic_s8_20261011/circuit.py'
spec=importlib.util.spec_from_file_location('n41_transport_cubic_base',BASE)
base=importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)

Field=base.Field
Algebra=base.shared.Algebra
helper=base.shared.old
ROTATIONS=(20,30)
N=41


def build(circuit, field, target_z):
    assert circuit.n==N and 0<target_z<(1<<N)
    algebra=Algebra(circuit,field)
    seed_sum=[[circuit.variable() for _ in range(6)] for _ in range(2)]
    product=[[circuit.variable() for _ in range(11)] for _ in range(2)]
    pair_z=[[circuit.variable() for _ in range(N)] for _ in range(2)]
    branch=[circuit.variable() for _ in range(3)]
    primary=[*sum(seed_sum,[]),*sum(product,[]),*sum(pair_z,[]),*branch]
    ht_basis=[helper.halftrace(field,field.square(1<<i)) for i in range(N)]
    tr_basis=[helper.trace(field,1<<i) for i in range(N)]
    for i,rotation in enumerate(ROTATIONS):
        base.shared.old.old.old.nonzero(circuit,seed_sum[i])
        base.shared.old.old.old.nonzero(circuit,pair_z[i])
        s=algebra.expression((wire,field.frob(1<<(j+1),rotation))
                             for j,wire in enumerate(seed_sum[i]))
        p=algebra.expression((wire,field.frob(1<<(j+2),rotation))
                             for j,wire in enumerate(product[i]))
        z=algebra.from_bits(pair_z[i])
        total=algebra.add(s,z)
        half=circuit.linear_element(total.bits(),ht_basis)
        cubic=algebra.add(algebra.mul(p,z),algebra.from_bits(half),
                          algebra.expression(((branch[i],1),)))
        circuit.require_zero(cubic.bits())
        trace=circuit.xor(wire for wire,bit in zip(total.bits(),tr_basis) if bit)
        circuit.require_zero([trace])
    helper.link(circuit,field,algebra,algebra.from_bits(pair_z[0]),
                algebra.from_bits(pair_z[1]),algebra.from_bits(circuit.constant(target_z)),
                branch[2],ht_basis,tr_basis)
    return {'seed_sum':seed_sum,'product':product,'pair_z':pair_z,
            'branch':branch,'primary_variables':primary,
            'relaxation':'free product-span coefficients; no seed factorization or rational-lift test'}

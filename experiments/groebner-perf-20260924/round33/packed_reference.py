"""Independent direct-superset specialization for offline evidence audits only.

Pack residual coefficients into disjoint Python-integer fields. For each
original fixed-block monomial, XOR its vector into every containing assignment.
This does not use either native zeta transform, producer pivots, or native code.
"""
from functools import lru_cache


@lru_cache(maxsize=16)
def branch_model(x, y, equations, items):
    if any(type(v) is not int for v in (x,y,equations)) or not (1<=x<=16 and 1<=y<=10 and x+y<=24 and 1<=equations<=128):
        raise ValueError('offline model: x<=16, y<=10, x+y<=24, equations<=128')
    monomials=tuple(m for m in range(1<<y) if m.bit_count()<=2)
    feature={m:i for i,m in enumerate(monomials)}
    low=(1<<x)-1
    grouped={}
    for mask,coefficient in items:
        if type(mask) is not int or not 0<=mask<1<<(x+y) or type(coefficient) is not int or not 0<=coefficient<1<<equations:
            raise ValueError('original input outside ring')
        if not coefficient: continue
        left,right=mask&low,mask>>x
        if right not in feature: raise ValueError('nonquadratic residual')
        grouped[left]=grouped.get(left,0) ^ (coefficient << (equations*feature[right]))
    residuals=[0]*(1<<x)
    for left,vector in grouped.items():
        if not vector: continue
        free=low^left
        extension=free
        while True:
            residuals[left|extension] ^= vector
            if not extension: break
            extension=(extension-1)&free
    q=len(monomials)-1
    counts=dict(branches=1<<x,consistent=0,max_nullity=0,lifted_candidates=0,
                fallback_branches=0,fallback_assignments=0,features=q)
    equation_mask=(1<<equations)-1
    for vector in residuals:
        rows=[0]*equations
        column=0
        while vector:
            coefficient=vector&equation_mask
            while coefficient:
                bit=coefficient&-coefficient
                rows[bit.bit_length()-1] ^= 1<<column
                coefficient ^= bit
            vector >>= equations
            column += 1
        pivots={}
        consistent=True
        for row in rows:
            while row>1:
                pivot=row.bit_length()-1
                if pivot not in pivots:
                    pivots[pivot]=row
                    break
                row ^= pivots[pivot]
            if row==1: consistent=False
        nullity=q-len(pivots)
        counts['max_nullity']=max(counts['max_nullity'],nullity)
        if consistent:
            counts['consistent'] += 1
            if nullity<y: counts['lifted_candidates'] += 1<<nullity
            else:
                counts['fallback_branches'] += 1
                counts['fallback_assignments'] += 1<<y
    # Immutable return values prevent a caller changing a cached reference.
    return tuple(sorted(counts.items())),tuple(residuals),monomials


def branch_counts(x,y,equations,items):
    return dict(branch_model(x,y,equations,tuple(tuple(v) for v in items))[0])


def contradiction_count(x,y,equations,items,raw,byteorder):
    if byteorder not in ('little','big'): raise ValueError('proof byte order')
    limbs=(equations+63)//64
    assert len(raw)==(1<<x)*limbs*8
    _,residuals,monomials=branch_model(x,y,equations,tuple(tuple(v) for v in items))
    equation_mask=(1<<equations)-1
    marked=0
    for assignment,vector in enumerate(residuals):
        start=assignment*limbs*8
        u=sum(int.from_bytes(raw[start+i*8:start+(i+1)*8],byteorder)<<(64*i) for i in range(limbs))
        assert 0<=u<1<<equations
        if not u: continue
        marked += 1
        for feature in range(len(monomials)):
            assert ((vector & equation_mask & u).bit_count() & 1)==int(feature==0), 'invalid branch contradiction'
            vector >>= equations
    return marked

"""Independent direct-superset specialization and affine proof auditing only.

Pack residual coefficients into disjoint Python-integer fields. For each
original fixed-block monomial, XOR its vector into every containing assignment.
This does not use either native zeta transform, producer pivots, or native code.
"""
from functools import lru_cache


@lru_cache(maxsize=24)
def branch_model(x, y, equations, items):
    if any(type(v) is not int for v in (x,y,equations)) or not (1<=x<=18 and 1<=y<=10 and x+y<=27 and 1<=equations<=128):
        raise ValueError('offline model: x<=18, y<=10, x+y<=27, equations<=128')
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
    nullities=[]
    consistent_flags=[]
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
        nullities.append(nullity)
        consistent_flags.append(consistent)
        counts['max_nullity']=max(counts['max_nullity'],nullity)
        if consistent:
            counts['consistent'] += 1
            if nullity<y: counts['lifted_candidates'] += 1<<nullity
            else:
                counts['fallback_branches'] += 1
                counts['fallback_assignments'] += 1<<y
    # Immutable return values prevent a caller changing a cached reference.
    return tuple(sorted(counts.items())),tuple(residuals),monomials,tuple(nullities),tuple(consistent_flags)


def branch_counts(x,y,equations,items):
    return dict(branch_model(x,y,equations,tuple(tuple(v) for v in items))[0])


@lru_cache(maxsize=48)
def certify_roots(x,y,equations,items,raw,byteorder):
    """Prove every rejection and exhaust all other original assignments.

    No generator pivots, reported rank, reported roots, or native code are used.
    The certificate can reduce work; failure to find one never proves anything.
    """
    assert byteorder in ('little','big') and len(raw)%8==0 and len(raw)<=64<<20
    _,vectors,monomials,_,_=branch_model(x,y,equations,items)
    limbs=(equations+63)//64
    branches,prefix,entry=1<<x,(1<<x)*limbs,1+(y+1)*limbs
    words=tuple(int.from_bytes(raw[i:i+8],byteorder) for i in range(0,len(raw),8))
    assert len(words)>=prefix and (len(words)-prefix)%entry==0
    mask=(1<<equations)-1
    covered=bytearray(branches)
    constant_count=0
    for a,vector in enumerate(vectors):
        u=sum(words[a*limbs+l]<<(64*l) for l in range(limbs))
        assert 0<=u<=mask
        if not u:continue
        for feature in range(len(monomials)):
            assert ((vector&mask&u).bit_count()&1)==int(feature==0),'invalid constant identity'
            vector >>= equations
        covered[a]=1
        constant_count+=1
    previous=-1
    extended=[]
    for offset in range(prefix,len(words),entry):
        a=words[offset]
        assert previous<a<branches and not covered[a]
        previous=a
        coefficients=tuple((vectors[a]>>(equations*j))&mask for j in range(len(monomials)))
        identity=set()
        for slot in range(y+1):
            u=sum(words[offset+1+slot*limbs+l]<<(64*l) for l in range(limbs))
            assert 0<=u<=mask
            multiplier=0 if slot==0 else 1<<(slot-1)
            for monomial,coefficient in zip(monomials,coefficients):
                if (coefficient&u).bit_count()%2:
                    identity.symmetric_difference_update((monomial|multiplier,))
        assert identity=={0},'invalid affine identity'
        covered[a]=1
        extended.append(a)
    unresolved=branches-constant_count-len(extended)
    assert unresolved*(1<<y)<=4194304,'offline exact-enumeration budget exceeded'
    supports=tuple(tuple(j for j,m in enumerate(monomials) if b&m==m) for b in range(1<<y))
    roots=[]
    for a,vector in enumerate(vectors):
        if covered[a]:continue
        coefficients=tuple((vector>>(equations*j))&mask for j in range(len(monomials)))
        for b,features in enumerate(supports):
            value=0
            for feature in features:value ^= coefficients[feature]
            if not value:roots.append(a|(b<<x))
    roots.sort()
    assert len(roots)<=256
    return tuple(roots),constant_count,tuple(extended),unresolved*(1<<y)


@lru_cache(maxsize=24)
def producer_model(x,y,equations,items,roots,extended):
    """Replay the declared bounded policy using Python-integer row reduction.

    This is instrumentation verification, separate from certify_roots' direct
    identity proof. It never calls native code or uses producer pivots.
    """
    base,vectors,monomials,nullities,consistent=branch_model(x,y,equations,items)
    counts=dict(base)
    counts.update(lifted_candidates=0,fallback_branches=0,fallback_assignments=0)
    fields=(equations+63)//64
    cubic=tuple(m for m in range(1<<y) if m.bit_count()<=3)
    index={m:i for i,m in enumerate(cubic)}
    products=tuple(tuple(1<<index[m|(0 if slot==0 else 1<<(slot-1))]
                         if m.bit_count()<=2 else 0 for m in cubic) for slot in range(y+1))
    row_words=(len(cubic)+63)//64
    proof_fields=(y+1)*fields
    prefix=(1<<x)*fields
    entry=1+proof_fields
    proof_words,capacity=prefix,prefix
    work_limit,branch_limit,proof_limit=67108864,65536,(64<<20)//8
    stats=dict(attempts=0,certified_branches=0,failed_branches=0,budget_skips=0,
               rows=0,row_xors=0,word_xors=0,avoided_assignments=0)
    root_branches={r&((1<<x)-1) for r in roots}
    found=[]
    mask=(1<<equations)-1

    def attempt(vector):
        nonlocal proof_words,capacity
        stats['attempts']+=1
        work=0
        if proof_words+entry>proof_limit:
            stats['budget_skips']+=1
            return False
        rows=[0]*equations
        for monomial in monomials:
            coefficient=vector&mask
            vector >>= equations
            while coefficient:
                bit=coefficient&-coefficient
                coefficient ^= bit
                rows[bit.bit_length()-1] ^= 1<<index[monomial]
        pivots={}
        for product in products:
            for original in rows:
                if stats['rows']+stats['row_xors']>=work_limit or work>=branch_limit:
                    stats['budget_skips']+=1
                    return False
                work+=1
                stats['rows']+=1
                row=0
                while original:
                    bit=original&-original
                    original ^= bit
                    row ^= product[bit.bit_length()-1]
                while row:
                    pivot=row.bit_length()-1
                    if pivot==0:
                        proof_words+=entry
                        if proof_words>capacity:capacity=min(proof_limit,max(proof_words,2*capacity))
                        return True
                    if pivot not in pivots:
                        pivots[pivot]=row
                        break
                    if stats['rows']+stats['row_xors']>=work_limit or work>=branch_limit:
                        stats['budget_skips']+=1
                        return False
                    work+=1
                    stats['row_xors']+=1
                    stats['word_xors']+=row_words+proof_fields
                    row ^= pivots[pivot]
        return False

    for a,vector in enumerate(vectors):
        if not consistent[a]:continue
        if nullities[a]<y:
            counts['lifted_candidates']+=1<<nullities[a]
            if a in root_branches:continue
            proved=attempt(vector)
        else:
            proved=attempt(vector)
            if proved:stats['avoided_assignments']+=1<<y
            else:
                counts['fallback_branches']+=1
                counts['fallback_assignments']+=1<<y
        stats['certified_branches']+=proved
        stats['failed_branches']+=not proved
        if proved:found.append(a)
    assert tuple(found)==extended,'recorded affine branches do not match the bounded producer policy'
    width=4 if equations<=32 else 8 if equations<=64 else 16
    stats.update(proof_words=proof_words,proof_capacity_words=capacity,
        workspace_bytes=len(cubic)*(row_words*8+(y+1)*width+1)+((1<<y)+(y+1)*len(monomials))*4)
    return tuple(sorted(counts.items())),tuple(sorted(stats.items()))


@lru_cache(maxsize=48)
def constant_identity_count(x,y,equations,items,raw,byteorder):
    """Validate the previous algorithm's constant-only proof without enumeration."""
    assert byteorder in ('little','big')
    limbs=(equations+63)//64
    assert len(raw)==(1<<x)*limbs*8
    _,vectors,monomials,_,_=branch_model(x,y,equations,items)
    mask=(1<<equations)-1
    count=0
    for a,vector in enumerate(vectors):
        u=sum(int.from_bytes(raw[(a*limbs+l)*8:(a*limbs+l+1)*8],byteorder)<<(64*l) for l in range(limbs))
        assert 0<=u<=mask
        if not u:continue
        for feature in range(len(monomials)):
            assert ((vector&mask&u).bit_count()&1)==int(feature==0),'invalid constant identity'
            vector >>= equations
        count+=1
    return count

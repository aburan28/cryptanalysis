"""Offline direct-original-ANF instrumentation model for fresh block symmetry.

No native code, producer tables or pivots are used. Mathematical completeness
is checked separately by round34.certify_roots against the original equations.
"""
from functools import lru_cache
from deferred import HERE
from affine_reference import branch_model, branch_counts, certify_roots


@lru_cache(maxsize=24)
def deferred_model(x,y,equations,items,roots,extended,*,copy_budget=(64<<20)//8,work_limit=67108864,branch_limit=65536,reconstruction_limit=67108864):
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
    proof_limit=(64<<20)//8
    stats=dict(attempts=0,certified_branches=0,failed_branches=0,budget_skips=0,
               rows=0,row_xors=0,word_xors=0,avoided_assignments=0)
    deferred=dict(inserted_pivots=0,dependency_toggles=0,reconstruction_attempts=0,
        reconstruction_pivots=0,reconstruction_word_xors=0,reconstructed_proofs=0,
        source_toggles=0,workspace_bytes=len(cubic)*(row_words*8+4))
    root_branches={r&((1<<x)-1) for r in roots}
    found=[]
    direct=set()
    root_counts={a:sum((r&((1<<x)-1))==a for r in roots) for a in root_branches}
    symmetry=dict(enabled=0,shape_fallback=x%2,asymmetric_fallback=0,
        compared_pairs=0,compared_coefficients=0,representatives=0,aliases=0,
        constant_copies=0,affine_copies=0,affine_copy_words=0,copy_budget_skips=0,
        copied_roots=0,rootless_aliases=0,gpu_linearized_branches=0,
        workspace_bytes=0 if x%2 else ((1<<x)*2+1)*4)
    def swap(a):return ((a&((1<<(x//2))-1))<<(x//2)) | (a>>(x//2))
    if x%2==0:
        native_order=(0,)+(tuple(1<<j for j in range(y)))+tuple((1<<j)|(1<<k) for j in range(y) for k in range(j+1,y))
        locations={m:i for i,m in enumerate(monomials)}
        coefficient_mask=(1<<equations)-1
        same=True
        for a,vector in enumerate(vectors):
            b=swap(a)
            if a>=b:continue
            symmetry['compared_pairs']+=1
            if vector==vectors[b]:symmetry['compared_coefficients']+=len(monomials)
            else:
                same=False
                for monomial in native_order:
                    symmetry['compared_coefficients']+=1
                    shift=equations*locations[monomial]
                    if ((vector^vectors[b])>>shift)&coefficient_mask:break
                break
        symmetry['enabled']=int(same)
        symmetry['asymmetric_fallback']=int(not same)

    def append_proof():
        nonlocal proof_words,capacity
        proof_words+=entry
        if proof_words>capacity:capacity=min(proof_limit,max(proof_words,2*capacity))
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
        parents={}
        for slot,product in enumerate(products):
            for equation,original in enumerate(rows):
                if stats['rows']+stats['row_xors']+deferred['reconstruction_pivots']>=work_limit or work>=branch_limit:
                    stats['budget_skips']+=1
                    return False
                work+=1
                stats['rows']+=1
                row=0
                dependencies=0
                while original:
                    bit=original&-original
                    original ^= bit
                    row ^= product[bit.bit_length()-1]
                while row:
                    pivot=row.bit_length()-1
                    if pivot==0:
                        deferred['reconstruction_attempts']+=1
                        deferred['source_toggles']+=1
                        while dependencies:
                            if (deferred['reconstruction_pivots']>=reconstruction_limit or
                                stats['rows']+stats['row_xors']+deferred['reconstruction_pivots']>=work_limit or work>=branch_limit):
                                stats['budget_skips']+=1
                                return False
                            work+=1
                            bit=dependencies&-dependencies
                            used=bit.bit_length()-1
                            dependencies^=bit
                            dependencies^=parents[used]
                            deferred['reconstruction_pivots']+=1
                            deferred['reconstruction_word_xors']+=row_words-used//64
                            deferred['source_toggles']+=1
                        deferred['reconstructed_proofs']+=1
                        append_proof()
                        return True
                    if pivot not in pivots:
                        pivots[pivot]=row
                        parents[pivot]=dependencies
                        deferred['inserted_pivots']+=1
                        break
                    if stats['rows']+stats['row_xors']+deferred['reconstruction_pivots']>=work_limit or work>=branch_limit:
                        stats['budget_skips']+=1
                        return False
                    work+=1
                    stats['row_xors']+=1
                    stats['word_xors']+=row_words+1
                    deferred['dependency_toggles']+=1
                    dependencies ^= 1<<pivot
                    row ^= pivots[pivot]
        return False

    for a,vector in enumerate(vectors):
        if symmetry['enabled'] and swap(a)<a:
            representative=swap(a)
            symmetry['aliases']+=1
            symmetry['copied_roots']+=root_counts.get(a,0)
            symmetry['rootless_aliases']+=int(a not in root_branches)
            if not consistent[a]:symmetry['constant_copies']+=1
            elif representative in direct:
                if entry<=copy_budget-symmetry['affine_copy_words'] and proof_words+entry<=proof_limit:
                    append_proof()
                    symmetry['affine_copies']+=1
                    symmetry['affine_copy_words']+=entry
                    found.append(a)
                else:symmetry['copy_budget_skips']+=1
            continue
        symmetry['representatives']+=1
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
        if proved:
            found.append(a)
            direct.add(a)
    assert tuple(found)==extended,'recorded affine branches do not match the bounded producer policy'
    width=4 if equations<=32 else 8 if equations<=64 else 16
    stats.update(proof_words=proof_words,proof_capacity_words=capacity,
        workspace_bytes=len(cubic)*(row_words*8+1)+deferred['workspace_bytes']+((1<<y)+(y+1)*len(monomials))*4)
    return tuple(sorted(counts.items())),tuple(sorted(stats.items())),tuple(sorted(symmetry.items())),tuple(sorted(deferred.items()))

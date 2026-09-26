"""Deterministic algebra controls, including difficult bounded failures."""
import random


def workloads():
    out=[]
    def add(name,n,equations,kind):
        out.append({'name':name,'nvars':n,'equations':equations,'kind':kind})
    # Reproduce the reference-producer exhaustion discovered by Singular
    # qualification, rather than dropping it from the comparison.
    rng=random.Random(2026092510)
    random_cases=[]
    for n in range(1,9):
        for _ in range(16):
            random_cases.append((n,[[rng.randrange(1 << n) for _ in range(rng.randrange(1,10))]
                                    for _ in range(rng.randrange(1,n+2))]))
    n,equations=random_cases[121]
    add('random-8-budget-control',n,equations,'unconditioned random ideal; observed reference/native work exhaustion')
    for n in (12,16,21):
        rng=random.Random(2026092600+n)
        planted=rng.randrange(1 << n)
        monomials=[1 << i for i in range(n)]+[(1 << i)|(1 << j) for i in range(n) for j in range(i)]
        equations=[]
        for _ in range(n):
            row=[m for m in monomials if rng.random()<0.2]
            if sum(m & planted == m for m in row)%2:
                row.append(0)
            equations.append(row)
        add(f'planted-dense-mq-{n}',n,equations,'planted nonlinear correctness control; degree of regularity unproved')
    for n in (21,32,64):
        equations=[[3 << i,0] for i in range(0,n-1,2)]+[[1 << (n-1),0]]
        add(f'pair-products-{n}',n,equations,'structured nonlinear control; all variables used')
    add('free-variables-64',64,[[3,4]],'nonlinear control with many unconstrained variables')
    return out

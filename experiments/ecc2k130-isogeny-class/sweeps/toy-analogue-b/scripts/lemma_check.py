#!/usr/bin/env python3
"""Check the structural observation on all prime n < 2000: if l = 2n+1 is prime and splits in Q(sqrt-7)
(kronecker(-7,l) = 1), then  l | f_n  <=>  l = +-1 mod 8, and in that case lambda = t_n/2 mod l = +-1
(so E0[l] is rational over F_{q^2}).  Plain python3 (exact integers)."""
import json, math
def isprime(m):
    if m < 2: return False
    for p in [2,3,5,7,11,13,17,19,23,29,31,37]:
        if m % p == 0: return m == p
    d, s = m - 1, 0
    while d % 2 == 0: d //= 2; s += 1
    for a in [2,3,5,7,11,13,17,19,23,29,31,37]:
        x = pow(a, d, m)
        if x in (1, m - 1): continue
        for _ in range(s - 1):
            x = x * x % m
            if x == m - 1: break
        else: return False
    return True
def kron_m7(l):   # (-7/l) = (l/7) for odd l (quadratic reciprocity; -7 = 1 mod 4)
    r = l % 7
    return 0 if r == 0 else (1 if r in (1, 2, 4) else -1)
rows = []; bad = []
for n in range(3, 2000):
    if not isprime(n): continue
    l = 2 * n + 1
    if not isprime(l) or kron_m7(l) != 1: continue
    for t1 in (-1, 1):
        a, b = 2, t1                       # Lucas t_k mod l^2 (enough to test l | f and t mod l)
        M = l * l
        for i in range(n - 1): a, b = b, (t1 * b - 2 * a) % M
        t = b
        # l | f  <=>  l^2 | (t^2 - 4q)/(-7)  <=>  t^2 = 4 q mod l^2  (l != 7)
        divides = (t * t - 4 * pow(2, n, M)) % M == 0
        lam = t * pow(2, -1, l) % l
        rows.append(dict(n=n, l=l, a2=(0 if t1 == -1 else 1), l_mod_8=l % 8, l_divides_f=divides, lam=lam))
        pred = (l % 8 in (1, 7))
        if divides != pred or (divides and lam not in (1, l - 1)): bad.append(rows[-1])
json.dump(dict(rows=rows, counterexamples=bad), open('/Volumes/SSD990/ecdlp-hardness-work/toy-analogue-b/raw/lemma_check.json', 'w'), indent=0)
print('cases (n, a2):', len(rows), ' with l | f:', sum(r['l_divides_f'] for r in rows), ' counterexamples:', len(bad))
print('examples:', [(r['n'], r['l'], r['a2'], r['l_mod_8'], r['l_divides_f'], r['lam']) for r in rows[:12]])

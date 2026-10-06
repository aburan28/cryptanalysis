# Red team 2, script 2b: search Kani parameters for the ascending p-isogeny (Galbraith 2024 Thm 1).
#  dim-4 ("two squares", Galbraith's own variant with c = 1):  M = A^2 > p, m = A^2 - p = x^2 + y^2
#  dim-2 ("one square", gamma = [x]):                           M = p + x^2 = c * A^2, x even, gcd(x,p)=1
# A = product of distinct Elkies primes (eigenvector trick), guesses ~ phi(A)/2 * (cost of the c-part).
import json, itertools, math, sys
from sympy import factorint, sqrt_mod, isprime
from sympy.ntheory.modular import crt
p = 146505763881528721
elk = json.load(open('/Volumes/SSD990/ecdlp-hardness-work/redteam-2/raw/rt2_elkies.json'))
# (l, eigen-field degree, x-field degree) for Elkies primes, recomputed from the table
tab = {l: (k, kx) for l, k, kx in elk['elkies_first_40']}
L = [l for l in sorted(tab) if l < 260]
res = {'pool': L}
def phi(n):
    r = n
    for l in factorint(n): r = r // l * (l - 1)
    return r
def two_squares(m):
    for l, e in factorint(m).items():
        if l % 4 == 3 and e % 2: return False
    return True
# ---- dim 4, c = 1 ----
best4 = []
s = math.isqrt(p)
for r in range(3, 9):
    for S in itertools.combinations(L, r):
        A = math.prod(S)
        if not (s < A < 3 * s): continue
        m = A * A - p
        if m <= 0 or math.gcd(m, p) != 1: continue
        if not two_squares(m): continue
        maxkx = max(tab[l][1] for l in S); maxk = max(tab[l][0] for l in S)
        best4.append((phi(A) // 2, maxkx, maxk, A, list(S), m))
best4.sort()
res['dim4_count'] = len(best4)
res['dim4_best_by_guesses'] = [dict(guesses=g, log2_guesses=math.log2(g), max_x_deg=kx, max_pt_deg=k, A=A, primes=S, m=m) for g, kx, k, A, S, m in best4[:8]]
lowdeg = sorted(best4, key=lambda e: (e[1], e[0]))
res['dim4_best_by_field_degree'] = [dict(guesses=g, log2_guesses=math.log2(g), max_x_deg=kx, max_pt_deg=k, A=A, primes=S, m=m) for g, kx, k, A, S, m in lowdeg[:8]]
print('dim4 candidates:', len(best4))
for d in res['dim4_best_by_guesses'][:4]: print(' ', d)
for d in res['dim4_best_by_field_degree'][:4]: print(' ', d)
# ---- dim 2, gamma = [x]: p + x^2 = c A^2 ----
QR = [l for l in L if pow((-p) % l, (l - 1) // 2, l) == 1]
res['dim2_QR_pool'] = QR
hits = []
roots = {}
for l in QR:
    r0 = sqrt_mod((-p) % (l * l), l * l, all_roots=False)
    roots[l] = r0
checked = 0
for r in range(3, 8):
    for S in itertools.combinations(QR, r):
        A = math.prod(S)
        if not (2**18 < A < 2**30): continue
        A2 = A * A
        mods = [l * l for l in S]
        for signs in itertools.product([1, -1], repeat=r - 1):
            vals = [roots[S[0]]] + [sg * roots[l] % (l * l) for sg, l in zip(signs, S[1:])]
            x = int(crt(mods, vals)[0])
            for xx in (x, A2 - x):
                checked += 1
                if xx % 2: continue
                M = p + xx * xx
                c = M // A2
                assert M % A2 == 0
                if c > 10**6: continue
                fc = factorint(c)
                # c-part guess cost: square part enters M1 and M2 (sqrt cost), squarefree part fully
                sq = math.prod(l ** (e // 2) for l, e in fc.items()); sf = math.prod(l ** (e % 2) for l, e in fc.items())
                gc = phi(sq * sf) if sq * sf > 1 else 1
                guesses = phi(A) // 2 * gc
                hits.append(dict(log2_guesses=math.log2(guesses), c=c, c_factor={str(k): v for k, v in fc.items()}, A=A, primes=list(S), x=xx, M_factor_ok=True,
                                 max_x_deg_A=max(tab[l][1] for l in S)))
hits.sort(key=lambda h: h['log2_guesses'])
res['dim2_residues_checked'] = checked
res['dim2_hits_c_le_1e6'] = len(hits)
res['dim2_best'] = hits[:12]
print('dim2 residues checked', checked, 'hits with c<=1e6:', len(hits))
for h in hits[:12]: print(' ', h)
json.dump(res, open('/Volumes/SSD990/ecdlp-hardness-work/redteam-2/raw/rt2b_search.json', 'w'), indent=1)

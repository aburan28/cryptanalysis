# Red team 2, script 2c: dimension-2 Kani variant exploiting h(O_K)=1.
# gamma: E1 -> E2 is a KNOWN F_q-rational isogeny of degree m (Frobenius power * horizontal smooth steps),
# degree coprime to p. The ascending p-isogeny of E2 lands on the crater = {E0} (h0 = 1), so the
# Kani diamond closes on E3 = E0 and F: E1 x E0 -> E0 x E2 has both ends KNOWN.
# Need M = p + m = c*A^2 (MITM needs the A^2 shape), A = product of distinct Elkies primes,
# m = 2^k * m' with m' a norm from O_K whose split prime factors are <= B (inert ones to even power).
import json, itertools, math
from sympy import factorint
from sympy.ntheory import legendre_symbol
p = 146505763881528721
elk = json.load(open('/Volumes/SSD990/ecdlp-hardness-work/redteam-2/raw/rt2_elkies.json'))
tab = {l: (k, kx) for l, k, kx in elk['elkies_first_40']}
L = [l for l in sorted(tab) if l < 260]
def kron7(l):
    # kronecker(-7, l) for odd prime l != 7
    return legendre_symbol((-7) % l, l)
def phi(n):
    r = n
    for l in factorint(n): r = r // l * (l - 1)
    return r
def c_guess(c):
    # c = 3^n (3 inert): guesses on E1[3^ceil(n/2)] images commuting with pi, up to pairing: ~4*3^(ceil(n/2)-1)
    if c == 1: return 1
    n = 0; cc = c
    while cc % 3 == 0: cc //= 3; n += 1
    assert cc == 1
    return 4 * 3 ** ((n + 1) // 2 - 1)
hits = []
for n in range(0, 9):
    c = 3 ** n
    lo = math.isqrt(p // c); hi = 3 * lo
    for r in range(2, 8):
        for S in itertools.combinations(L, r):
            A = math.prod(S)
            if not (lo < A < hi): continue
            m = c * A * A - p
            if m <= 0: continue
            k2 = (m & -m).bit_length() - 1
            mp = m >> k2
            fm = factorint(mp)
            ok = True; maxsplit = 1
            for l, e in fm.items():
                if l == 7: continue
                if l == p: ok = False; break
                if kron7(l) == 1: maxsplit = max(maxsplit, l)
                elif e % 2: ok = False; break
            if not ok: continue
            G = phi(A) // 2 * c_guess(c)
            hits.append(dict(log2_guesses=round(math.log2(G), 3), c=c, A=A, primes=list(S), max_x_deg_A=max(tab[l][1] for l in S),
                             m=m, frob_power=k2, m_odd_factor={str(a): b for a, b in fm.items()}, max_split_prime_in_gamma=maxsplit))
hits.sort(key=lambda h: (h['max_split_prime_in_gamma'], h['log2_guesses']))
out = dict(n_hits=len(hits), best_by_gamma_prime=hits[:15],
           best_by_guesses=sorted(hits, key=lambda h: h['log2_guesses'])[:10])
json.dump(out, open('/Volumes/SSD990/ecdlp-hardness-work/redteam-2/raw/rt2c_dim2_search.json', 'w'), indent=1)
print('hits', len(hits))
for h in hits[:15]: print(h)

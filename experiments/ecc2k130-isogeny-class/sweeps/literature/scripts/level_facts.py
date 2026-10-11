# Number-theoretic facts that the literature statements depend on.
# Run: export TMPDIR=/Volumes/SSD990/ecdlp-hardness-work/tmp; sage -python level_facts.py
import json, sys, time
from sage.all import (ZZ, Integer, kronecker, pari, is_prime, factor, Mod, log, RR, pi,
                      sqrt, RealField, GF, PolynomialRing)
sys.path.insert(0, '/Volumes/SSD990/ecdlp-hardness-work/ground_truth')
import ecc2k
R = RealField(100)
out = {}
q = Integer(2)**131
t = Integer(ecc2k.t); N = Integer(ecc2k.N); f = Integer(ecc2k.f); p = Integer(ecc2k.p)
# Recompute t from Lucas recurrence for tau^2 + tau + 2 = 0  (t_1 = -1)
a0, a1 = Integer(2), Integer(-1)
for _ in range(130):
    a0, a1 = a1, -a1 - 2*a0
assert a1 == t, (a1, t)
assert q + 1 - t == 4*N
assert t**2 - 4*q == -7*f**2 and f == 263*p
assert N.is_prime(proof=True) and p.is_prime(proof=True) and Integer(263).is_prime()
out['t'] = str(t); out['N'] = str(N); out['p'] = str(p); out['f'] = str(f)
out['log2_N'] = float(R(N).log2()); out['log2_p'] = float(R(p).log2())
out['kron_-7_263'] = int(kronecker(-7, 263)); out['kron_-7_p'] = int(kronecker(-7, p))
# class numbers via the conductor formula h(O_c) = h(O_K) c prod(1-(dK/l)/l) / [O_K^*:O_c^*]; dK=-7, units +-1
def h_formula(c):
    c = Integer(c); h = c
    for l, e in factor(c):
        h = h * (1 - Integer(kronecker(-7, l))/l)
    return ZZ(h)
hs = {c: h_formula(c) for c in [1, 263, p, 263*p]}
out['class_numbers_formula'] = {str(k): str(v) for k, v in hs.items()}
# cross-check small ones with PARI qfbclassno
out['qfbclassno_-7'] = int(pari(-7).qfbclassno())
out['qfbclassno_-7*263^2'] = int(pari(-7*263**2).qfbclassno())
assert out['qfbclassno_-7*263^2'] == hs[263]
out['log2_h_p'] = float(R(hs[p]).log2()); out['log2_h_263p'] = float(R(hs[263*p]).log2())
total = sum(hs.values())
out['total_curves_in_isogeny_class'] = str(total)
out['log2_total'] = float(R(total).log2())
out['fraction_levels_1_263'] = float(R(1 + 262)/R(total))
out['log2_fraction_levels_1_263'] = float((R(263)/R(total)).log2())
# 131 must divide h(O_c) for c>1 (F_2-Frobenius orbits of size 131)
out['h_mod_131'] = {str(c): int(hs[c] % 131) for c in [263, p, 263*p]}
# Frobenius eigenvalue on E0[l] for l | f: pi = (t - f)/2 + f*omega  => acts as lambda = t/2 mod l
for l in [Integer(263), p]:
    lam = Mod(t, l) / 2
    assert lam**2 == Mod(q, l)
    k = lam.multiplicative_order(); k2 = (-lam).multiplicative_order()
    out[f'lambda_mod_{l}'] = str(lam.lift()); out[f'ord_lambda_mod_{l}'] = str(k)
    out[f'ord_minus_lambda_mod_{l}'] = str(k2)
    out[f'log2_ord_lambda_mod_{l}'] = float(R(k).log2())
    out[f'factor_{l}_minus_1'] = str(factor(l - 1))
    out[f'v_{l}(q+1-t)'] = int((q + 1 - t).valuation(l)); out[f'v_{l}(q+1+t)'] = int((q + 1 + t).valuation(l))
# embedding degree of N (MOV): order of q mod N
Nm1 = factor(N - 1)
out['factor_N_minus_1'] = str(Nm1)
k_emb = Mod(q, N).multiplicative_order()
out['embedding_degree_N'] = str(k_emb); out['log2_embedding_degree'] = float(R(k_emb).log2())
# order of 2 mod N (relevant to F_2-subfield structure) and ord_131(2)
out['ord_131_2'] = int(Mod(2, 131).multiplicative_order())
# rho iteration baselines
out['log2_rho_neg_frob'] = float((R(pi) * R(N) / (4 * 131)).sqrt().log2())
out['log2_rho_neg_only'] = float((R(pi) * R(N) / 4).sqrt().log2())
out['log2_rho_plain'] = float((R(pi) * R(N) / 2).sqrt().log2())
out['log2_speedup_frob'] = float(R(131).sqrt().log2())
# sqrt(p) for sqrt-Velu cost scale and naive Velu
out['log2_sqrt_p'] = float(R(p).sqrt().log2())
# smallest split primes l with (-7/l)=1 and (l/263)=-1 (cross-genus horizontal isogenies A<->B at level 263)
cross = []; same = []
from sage.all import primes
for l in primes(3, 200):
    if l == 7 or l == 263: continue
    if kronecker(-7, l) == 1:
        (cross if kronecker(l, 263) == -1 else same).append(int(l))
out['split_primes_cross_genus_lt200'] = cross; out['split_primes_same_genus_lt200'] = same
out['kron_2_263'] = int(kronecker(2, 263))
print(json.dumps(out, indent=1))
json.dump(out, open('/Volumes/SSD990/ecdlp-hardness-work/literature/raw/level_facts.json', 'w'), indent=1)

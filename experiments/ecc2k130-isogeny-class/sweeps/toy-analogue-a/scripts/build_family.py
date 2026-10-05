"""Build one toy family: E0, all l-1 floor curves of its l-volcano (Velu from E0[l] over an
extension field, one Velu per Frobenius orbit + Frobenius powers), orbit labels, and checks.

usage: sage -python build_family.py <T11|T19|T23|T59|T109> [--hd] [--count-all]
  --hd         also compare with H_{-7 l^2} mod 2 (PARI polclass); only for small l
  --count-all  PARI point count of every floor curve and its twist
Writes data/<name>_family.json and data/<name>_build_log.json.
"""
import sys, json, time, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from toylib import *
from sage.all import (set_random_seed, GF, EllipticCurve, Integer, PolynomialRing, matrix,
                      vector, pari, primitive_root, gcd, log)

name = sys.argv[1]
DO_HD = '--hd' in sys.argv
COUNT_ALL = '--count-all' in sys.argv
set_random_seed(20260923)
T0 = time.time()
LOG = []


def chk(label, cond, **info):
    LOG.append(dict(check=label, ok=bool(cond), t=round(time.time() - T0, 2), **{k: str(v) for k, v in info.items()}))
    print(('OK  ' if cond else 'FAIL'), label, info if info else '', flush=True)
    assert cond, label


fb = family_basics(name)
a, n, l, t1, t, q, N, h = (fb[k] for k in ('a', 'n', 'l', 't1', 't', 'q', 'N', 'h'))
K, tail = make_field(n)
chk('modulus irreducible', K.modulus().is_irreducible(), modulus=K.modulus())
E0 = EllipticCurve(K, [1, a, 0, 0, 1])
chk('#E0(F_2) via Lucas start', EllipticCurve(GF(2), [1, a, 0, 0, 1]).cardinality() == 3 - t1)
chk('#E0 (PARI) == q+1-t', E0.cardinality() == fb['card'], card=fb['card'])
chk('#E0 twist (PARI) == q+1+t', EllipticCurve(K, [1, 1 - a, 0, 0, 1]).cardinality() == q + 1 + t)
chk('N prime (proof)', N.is_prime(proof=True), N=N, bits=float(log(N, 2)))
chk('l prime, (-7/l)=1, l || f', Integer(l).is_prime(), f=fb['f'])
chk('l does not divide #E0', fb['card'] % l != 0)
G = h * E0.random_point()
while G == 0:
    G = h * E0.random_point()
chk('N*G == 0', N * G == 0)
s = tau_eigen(E0, G, N, t1)
chk('tau acts as s on <G>', E0(G[0]**2, G[1]**2) == s * G, s=s)
chk('s has order n mod N', pow(int(s), n, int(N)) == 1 and s != 1)

Fl = GF(l)
lam = Fl(t) / 2
ordl, ordml = lam.multiplicative_order(), (-lam).multiplicative_order()
if ordl <= ordml:
    aw, tw1, k = a, t1, ordl
else:
    aw, tw1, k = 1 - a, -t1, ordml
chk('lambda^2 == q mod l', lam**2 == Fl(q), lam=lam, ord_lam=ordl, ord_mlam=ordml, work_a2=aw, ext_degree=k)

# extension field L = F_{q^k}
tL = time.time()
L, emb, down = make_ext(K, n, k)


xk = K.random_element()
chk('embedding K->L is a ring hom', emb(xk * xk + K.gen()) == emb(xk)**2 + emb(K.gen()) and down(emb(xk)) == xk,
    L_degree=n * k, setup_s=round(time.time() - tL, 1))

C = EllipticCurve(L, [1, aw, 0, 0, 1])
cardL = Integer(2)**(n * k) + 1 - lucas_t(tw1, n * k)
vl = cardL.valuation(l)
R0 = C.random_point()
chk('#C(L) from Lucas kills a random point', cardL * R0 == 0, v_l=vl)
chk('l^2 | #C(L) (full l-torsion over L)', vl >= 2)
cof = cardL // l**vl


def order_l_point(Cv):
    while True:
        U = cof * Cv.random_point()
        if U == 0:
            continue
        while l * U != 0:
            U = l * U
        return U


def tau(P):
    return P.curve()(P[0]**2, P[1]**2)


Rl = PolynomialRing(Fl, 'X')
X = Rl.gen()
tau1, tau2 = (X**2 - tw1 * X + 2).roots(multiplicities=False)
while True:
    U = order_l_point(C)
    E1 = tau(U) - int(tau2) * U
    E2 = tau(U) - int(tau1) * U
    if E1 != 0 and E2 != 0:
        break
chk('eigenlines of tau on E0[l]', tau(E1) == int(tau1) * E1 and tau(E2) == int(tau2) * E2 and l * E1 == 0 and l * E2 == 0,
    tau1=tau1, tau2=tau2)
chk('E1, E2 independent (Weil pairing != 1)', E1.weil_pairing(E2, l) != 1)
piq = lambda P: P.curve()(P[0]**q, P[1]**q)
chk('Frobenius pi acts on E0[l] of work curve as scalar', piq(E1) == int(lam if aw == a else -lam) * E1 and piq(E2) == int(lam if aw == a else -lam) * E2)

half = (l - 1) // 2


def velu_v(T):
    """sum of x over half the kernel <T> (one of each +-pair)."""
    S = T
    v = S[0]
    for _ in range(half - 1):
        S = S + T
        v += S[0]
    return v


tv = time.time()
jh1 = 1 / (1 + down(velu_v(E1)) + down(velu_v(E1))**2)
jh2 = 1 / (1 + down(velu_v(E2)) + down(velu_v(E2))**2)
chk('both tau-eigenlines give j = 1 (horizontal isogenies)', jh1 == 1 and jh2 == 1, velu_s=round(time.time() - tv, 1))

rho = tau2 / tau1
chk('rho = tau2/tau1 has order n in F_l^*', rho.multiplicative_order() == n)
g = Fl(primitive_root(l))
m = (l - 1) // n
reps = [g**i for i in range(m)]


def floor_j(c):
    T = E1 + int(c) * E2
    v = down(velu_v(T))
    return v, 1 / (1 + v + v * v)


orbits = []
tv = time.time()
for i, c in enumerate(reps):
    v, j = floor_j(c)
    orbits.append(dict(rep_c=int(c), j0=j, v0=v))
    if i % 10 == 0:
        print(f'  orbit {i}/{m}  {time.time() - tv:.1f}s', flush=True)
chk('Velu j for all orbit representatives', True, orbits=m, secs=round(time.time() - tv, 1))
# Frobenius consistency: j(c*rho) == j(c)^2 directly
v1, j1 = floor_j(reps[0] * rho)
chk('Velu with kernel c*rho gives j(c)^2 (Frobenius = rho-translation)', j1 == orbits[0]['j0']**2)
if m > 1:
    v2, j2 = floor_j(reps[1] * rho**3)
    chk('Velu with kernel c*rho^3 gives j(c)^8', j2 == orbits[1]['j0']**8)

# orbits, labels
Y = PolynomialRing(GF(2), 'Y').gen()
allj = []
for o in orbits:
    conj = [o['j0']**(2**i) for i in range(n)]
    mp = PolynomialRing(K, 'Y')([1])
    Yk = PolynomialRing(K, 'Y').gen()
    for cj in conj:
        mp *= (Yk - cj)
    coeffs = [cc for cc in mp.list()]
    assert all(cc in (K(0), K(1)) for cc in coeffs)
    o['minpoly_int'] = sum((1 << i) for i, cc in enumerate(coeffs) if cc == 1)
    o['conj'] = conj
    allj += conj
chk('l-1 distinct floor j, none in F_2', len(set(allj)) == l - 1 and all(j not in (K(0), K(1)) for j in allj), count=len(allj))
orbits.sort(key=lambda o: o['minpoly_int'])
chk('each orbit min poly irreducible of degree n', all(PolynomialRing(GF(2), 'Y')([(o['minpoly_int'] >> i) & 1 for i in range(n + 1)]).is_irreducible() for o in orbits))

curves = {'E0': dict(label='E0', orbit='crater', frob_index=None, level=1, a2=a, b_int=1, j_int=1)}
for oi, o in enumerate(orbits):
    conj_int = sorted(o['conj'], key=fe2int)
    x0 = conj_int[0]
    for kk in range(n):
        j = x0**(2**kk)
        lab = f'O{oi:02d}-{kk:03d}'
        curves[lab] = dict(label=lab, orbit=f'O{oi:02d}', frob_index=kk, level=l, j_int=fe2int(j), b_int=fe2int(1 / j), a2=None,
                           orbit_minpoly_int=o['minpoly_int'])

# which twist is isogenous to E0 (a2 = a expected); cheap check for all when requested, else sampled
tc = time.time()
labels = [x for x in curves if x != 'E0']
sample = labels if COUNT_ALL else [x for x in labels if x.endswith('-000') or x.endswith('-001')]
twist_ok = 0
for lab in sample:
    b = int2fe(K, curves[lab]['b_int'])
    Ea = EllipticCurve(K, [1, a, 0, 0, b])
    ca = Ea.cardinality()
    cb = EllipticCurve(K, [1, 1 - a, 0, 0, b]).cardinality()
    ok = (ca == fb['card'] and cb == q + 1 + t)
    curves[lab]['a2'] = a
    curves[lab]['order_pari'] = int(ca)
    curves[lab]['twist_order_pari'] = int(cb)
    twist_ok += ok
chk('floor curves [1,a,0,0,1/j] have #E = #E0 and twist q+1+t (PARI)', twist_ok == len(sample), counted=len(sample),
    of=len(labels), secs=round(time.time() - tc, 1))
for lab in labels:
    curves[lab]['a2'] = a

if DO_HD:
    th = time.time()
    D = -7 * l * l
    H = pari(f'polclass({D})')
    Hs = PolynomialRing(GF(2), 'Y')([Integer(cc) % 2 for cc in H.Vecrev()])
    fac = Hs.factor()
    HK = PolynomialRing(K, 'Y')(Hs)
    rts = set(HK.roots(multiplicities=False))
    chk('H_{-7l^2} mod 2: squarefree, (l-1)/n factors of degree n, roots == Velu floor set',
        Hs.is_squarefree() and len(fac) == m and all(ff.degree() == n and e == 1 for ff, e in fac) and rts == set(allj),
        degree=Hs.degree(), secs=round(time.time() - th, 1))
    # Sage factor() order vs our min-poly order
    fac_ints = [sum(1 << i for i, cc in enumerate(ff.list()) if cc == 1) for ff, e in fac]
    chk('orbit order by min-poly integer == Sage factor() order', fac_ints == [o['minpoly_int'] for o in orbits])

out = dict(meta=dict(family=name, a=a, n=n, l=l, t=str(t), q=str(q), card=str(fb['card']), card_fac=fb['card_fac'],
                     N=str(N), cofactor=str(h), f=str(fb['f']), f_fac=fb['f_fac'], modulus_tail=tail,
                     modulus=str(K.modulus()), tau_eigen_s=str(s), lambda_mod_l=int(lam), ord_lambda=int(ordl),
                     ord_minus_lambda=int(ordml), velu_work_curve_a2=aw, velu_ext_degree=int(k), tau_eigen_mod_l=[int(tau1), int(tau2)],
                     rho=int(rho), n_orbits=m, orbit_label_rule='orbits sorted by integer encoding of min poly over F_2; X-000 = smallest-integer j in the orbit; X-k has j = j(X-000)^(2^k)',
                     sage_seed=20260923, build_s=round(time.time() - T0, 1)),
           curves=curves)
os.makedirs(os.path.join(WORK, 'data'), exist_ok=True)
json.dump(out, open(os.path.join(WORK, 'data', f'{name}_family.json'), 'w'), indent=1, default=str)
json.dump(LOG, open(os.path.join(WORK, 'data', f'{name}_build_log.json'), 'w'), indent=1)
print('done', name, round(time.time() - T0, 1), 's')

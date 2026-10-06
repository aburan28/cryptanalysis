#!/usr/bin/env sage -python
"""G4: reconcile the disputed B2 (levels p and 263p) numbers in ONE script.

Recomputes, from scratch:
  (A) the constants (t, N, f = 263 p, class numbers, c = pi mod p, r = ord_p(c), pi-orders on small torsion);
  (B) the random-search construction cost of a level-p / level-263p curve under four candidate spaces,
      with the prefilter lemma (a2 = 0, Tr(b) = 1) re-verified by brute force on small fields and by PARI
      point counts over F_{2^131}, and the per-candidate test cost counted by EXECUTING an x-only
      Lopez-Dahab ladder with a multiplication counter;
  (C) the cofactor kernel-point bound (x-only over F_{q^{r/2}} vs full points over F_{q^r});
  (D) the Phi_p / CM routes;
  (E) the Kani transport cost (Galbraith 2024/924 Thm 1/2) in dims 2, 4, 8 under the 'descended' and
      'compositum' cost models, reproducing the three on-disk figures first (redteam-2 rt4 proposer model,
      RT2-01-1 compositum/descended, RT15-1 per-guess model) and then running fresh parameter searches;
  (F) effective hardness per level with break-even constants.
Nothing here is a measured timing of a higher-dimensional isogeny: no characteristic-2 (l,...,l)-isogeny
implementation exists in this work tree; the per-step constant C is kept symbolic and scanned.

Run: export TMPDIR=/Volumes/SSD990/ecdlp-hardness-work/tmp
     timeout 2400 sage -python reconcile.py
"""
import json, math, itertools, functools, time, sys, os, heapq, random
from math import log2, gcd, prod, isqrt
import numpy as np
from sage.all import (ZZ, Integer, GF, EllipticCurve, factor, is_prime, kronecker, pari, PolynomialRing,
                      set_random_seed, prime_range, Integers)

OUT = '/Volumes/SSD990/ecdlp-hardness-work/gaps/G4-reconcile-B2-levels-and-literature'
T0 = time.time()
RES = {}
LOG = open(os.path.join(OUT, 'reconcile.log'), 'w')
def rec(sec, key, val):
    RES.setdefault(sec, {})[key] = val
    s = f"[{sec}] {key} = {val}"
    print(s, flush=True); LOG.write(s + "\n"); LOG.flush()
def lcm(a, b): return a // gcd(a, b) * b
def r2(x, k=2): return round(float(x), k)
set_random_seed(20260924); random.seed(20260924)

# =====================================================================================================
# (A) constants
# =====================================================================================================
q = 2 ** 131
ts = [2, -1]                      # t_0 = 2, t_1 = 2 + 1 - #E0(F_2) = -1  (#E0(F_2) = 4)
for k in range(2, 132): ts.append(-ts[-1] - 2 * ts[-2])
t = ts[131]
assert t == -22283658519494248867
CARD = q + 1 - t; assert CARD % 4 == 0
N = CARD // 4
assert is_prime(N)
DISC = t * t - 4 * q; assert (-DISC) % 7 == 0
f = isqrt(-DISC // 7); assert 7 * f * f == -DISC
assert f % 263 == 0
p = f // 263
assert is_prime(p) and p == 146505763881528721
# O_K = Z[w], w^2 = w - 2 ; pi = a + b w
bb = f if (t - f) % 2 == 0 else -f
aa = (t - bb) // 2
assert aa * aa + aa * bb + 2 * bb * bb == q
PI = (aa, bb)
c_p = aa % p
assert c_p == (t * pow(2, -1, p)) % p
r = int(Integers(p)(c_p).multiplicative_order())
r_x = r // 2 if pow(c_p, r // 2, p) == p - 1 else r
H = {'1': 1, '263': 262, 'p': p + 1, '263p': 262 * (p + 1)}
H_B2 = H['p'] + H['263p']; H_ALL = sum(H.values())
assert H_ALL == 263 * (p + 2)
rec('A', 't', str(t)); rec('A', 'N', str(N)); rec('A', 'log2 N', r2(log2(N), 3))
rec('A', 'f = 263*p', f"{f} = 263*{p}"); rec('A', 'kronecker(-7,p), kronecker(-7,263)', [int(kronecker(-7, p)), int(kronecker(-7, 263))])
rec('A', 'class numbers h(1),h(263),h(p),h(263p)', [str(H[k]) for k in ('1', '263', 'p', '263p')])
rec('A', 'log2 class numbers', [r2(log2(H[k]), 3) for k in ('1', '263', 'p', '263p')])
rec('A', 'sum h = 263(p+2), log2', [str(H_ALL), r2(log2(H_ALL), 3)])
rec('A', 'B2 = levels p + 263p: count, log2, fraction of class', [str(H_B2), r2(log2(H_B2), 3), float(H_B2 / H_ALL)])
rec('A', 'c = pi mod p (t/2 mod p)', int(c_p)); rec('A', 'r = ord_p(c), log2', [r, r2(log2(r), 3)])
rec('A', 'r_x (x-coordinate field degree of ker(pi - c)), log2', [r_x, r2(log2(r_x), 3)])

LOG2_RHO_E0 = 0.5 * log2(math.pi * N / (4 * 131))     # negation + tau
LOG2_RHO_NEG = 0.5 * log2(math.pi * N / 4)             # negation only
rec('A', 'log2 rho E0 (neg+tau), log2 rho neg-only', [r2(LOG2_RHO_E0, 3), r2(LOG2_RHO_NEG, 3)])

# ---- O_K arithmetic mod n, orders of pi on E[l^e] ----------------------------------------------
def ok_mul(x, y, n):
    return ((x[0] * y[0] - 2 * x[1] * y[1]) % n, (x[0] * y[1] + x[1] * y[0] + x[1] * y[1]) % n)
def ok_pow(x, k, n):
    res = (1 % n, 0); b_ = (x[0] % n, x[1] % n)
    while k:
        if k & 1: res = ok_mul(res, b_, n)
        b_ = ok_mul(b_, b_, n); k >>= 1
    return res
def ptype(l):
    kr = int(kronecker(-7, l))
    return {1: 'split', -1: 'inert', 0: 'ramified'}[kr]
def unit_order(l, e):
    ty = ptype(l)
    if ty == 'split': return (l - 1) ** 2 * l ** (2 * e - 2)
    if ty == 'inert': return (l * l - 1) * l ** (2 * e - 2)
    return (l - 1) * l ** (2 * e - 1)
@functools.lru_cache(None)
def pi_order(l, e):
    """order of pi in (O_K/l^e)^*: the degree of the field of definition of E[l^e] (l not | 2*263*p)."""
    n = l ** e; G = unit_order(l, e); o = G
    for rr, _ in factor(G):
        rr = int(rr)
        while o % rr == 0 and ok_pow(PI, o // rr, n) == (1, 0): o //= rr
    return int(o)
@functools.lru_cache(None)
def eig_orders(l):
    rts = [x for x in range(l) if (x * x - t * x + q) % l == 0]
    return tuple(sorted(int(Integers(l)(x).multiplicative_order()) for x in rts))
def guesses(l, e):
    ty = ptype(l)
    if ty == 'split': return (l - 1) * l ** (e - 1)
    if ty == 'inert': return (l + 1) * l ** (e - 1)
    assert l == 7 and e == 1
    return 14                                     # O_K/7 = F_7[eps]: a0^2 = deg (2 roots) x 7 choices of a1
ALLOWED_BAD = {2, 263, p}
rec('A', 'pi-order on E[3^e], e=1..5', [pi_order(3, e) for e in range(1, 6)])
rec('A', 'pi-order on E[5] (level-5 theta field for l=3 steps)', pi_order(5, 1))
rec('A', 'check: split l -> lcm(eigen-orders) == pi_order(l,1) for l < 400',
    all(lcm(*eig_orders(l)) == pi_order(l, 1) for l in prime_range(3, 400) if l not in ALLOWED_BAD and ptype(l) == 'split'))

# =====================================================================================================
# (B) construction of a level-p / level-263p curve by random search
# =====================================================================================================
# B.1 prefilter lemma, brute force over small odd-degree binary fields
lemma = {}
for m in (7, 9, 11, 13):
    F = GF(2 ** m, 'z'); ok4 = ok8 = tot = 0
    for bb_ in F:
        if bb_ == 0: continue
        for a2 in (0, 1):
            E = EllipticCurve(F, [1, a2, 0, 0, bb_]); n_ = int(E.cardinality()); tot += 1
            ok4 += ((n_ % 4 == 0) == (a2 == 0))              # Tr(a2) = a2 * m mod 2 = a2 (m odd)
            if a2 == 0: ok8 += ((n_ % 8 == 0) == (int(bb_.trace()) == 0))
    lemma[m] = dict(curves=tot, four_divides_iff_a2_0=ok4 == tot, eight_divides_iff_Tr_b_0_given_a2_0=ok8 == tot // 2)
rec('B', 'prefilter lemma brute force (m odd): 4|#E <=> a2=0 ; given a2=0: 8|#E <=> Tr(b)=0', lemma)
# B.2 the same on F_{2^131} (ECC2K-130 polynomial basis) with PARI point counts
Rz = PolynomialRing(GF(2), 'z'); zz = Rz.gen()
K131 = GF(2 ** 131, 'z', modulus=zz ** 131 + zz ** 13 + zz ** 2 + zz + 1)
chk = []
for _ in range(12):
    b_ = K131.random_element()
    E = EllipticCurve(K131, [1, 0, 0, 0, b_]); n_ = int(E.cardinality())
    chk.append((n_ % 4 == 0) and ((n_ % 8 == 0) == (int(b_.trace()) == 0)))
rec('B', 'F_2^131: 12 random b, a2=0: 4|#E and (8|#E <=> Tr b = 0)', all(chk))
rec('B', '4N mod 8 (so every curve of order 4N has a2=0 model and Tr(b)=1)', int((4 * N) % 8))
# B.3 candidate spaces and trial counts
spaces = {
    'uniform (b,a2) over 2(q-1) classes (p-levels/conclusions.json)': 2 * (q - 1),
    'random j, both twists tested as one trial': (q - 1),
    'a2=0 only (q-1 candidates)': (q - 1),
    'a2=0 and Tr(b)=1 prefilter (q/2 candidates)': q // 2,
}
trials = {}
for name, sz in spaces.items():
    trials[name] = dict(log2_trials_level_p_or_263p=r2(log2(sz) - log2(H_B2), 3),
                        log2_trials_level_p_only=r2(log2(sz) - log2(H['p']), 3))
rec('B', 'expected trials per hit', trials)
LOG2_TRIALS = log2(q // 2) - log2(H_B2)
rec('B', 'Galbraith 2024 Thm 4 figure log2 q^(1/2) (O~, constants and logs hidden)', 65.5)
rec('B', 'class size vs q^(1/2): log2(263(p+2)) - 65.5', r2(log2(H_ALL) - 65.5, 3))

# B.4 per-candidate test: execute an x-only Lopez-Dahab ladder with a multiplication counter
class Ctr: M = 0; S = 0
def mul(x, y): Ctr.M += 1; return x * y
def sq(x): Ctr.S += 1; return x * x
def ld_ladder(xP, k, sqrtb):
    """x-only Montgomery/Lopez-Dahab ladder on y^2+xy=x^3+b (a2=0). Returns (X, Z) of [k]P.
    Mdouble: X' = (X^2 + sqrt(b) Z^2)^2, Z' = X^2 Z^2   (2M + 3S);
    Madd:    Z3 = (X1 Z2 + X2 Z1)^2, X3 = xP*Z3 + (X1 Z2)(X2 Z1)   (3M + 1S, +1M if xP != 1)."""
    def dbl(X, Z):
        X2 = sq(X); Z2 = sq(Z)
        return sq(X2 + mul(sqrtb, Z2)), mul(X2, Z2)
    def add(X1, Z1, X2, Z2):
        u = mul(X1, Z2); v = mul(X2, Z1); Z3 = sq(u + v)
        X3 = (Z3 if xP == 1 else mul(xP, Z3)) + mul(u, v)
        return X3, Z3
    one = K131(1); zero = K131(0)
    R0 = (one, zero); R1 = (xP, one)
    for bit in bin(k)[2:]:
        if bit == '1': R0 = add(*R0, *R1); R1 = dbl(*R1)
        else: R1 = add(*R0, *R1); R0 = dbl(*R0)
    return R0
ladder = {}
for trial in range(3):
    while True:
        b_ = K131.random_element()
        if b_ != 0 and int(b_.trace()) == 1: break
    E = EllipticCurve(K131, [1, 0, 0, 0, b_])
    # x = 1 lies on E iff y^2 + y = 1 + b is solvable iff Tr(1 + b) = 0 iff Tr(b) = 1 (m odd)
    P = E.lift_x(K131(1))
    Ctr.M = Ctr.S = 0
    X, Z = ld_ladder(K131(1), 4 * N, b_.sqrt())
    M1, S1 = Ctr.M, Ctr.S
    Q = (4 * N) * P
    ok = (Z == 0) if Q.is_zero() else (Z != 0 and X / Z == Q.xy()[0])
    # generic base point
    P2 = E.random_point(); Ctr.M = Ctr.S = 0
    X2_, Z2_ = ld_ladder(P2.xy()[0], 4 * N, b_.sqrt()); M2, S2 = Ctr.M, Ctr.S
    Q2 = (4 * N) * P2
    ok2 = (Z2_ == 0) if Q2.is_zero() else (Z2_ != 0 and X2_ / Z2_ == Q2.xy()[0])
    ladder[trial] = dict(xP1_M=M1, xP1_S=S1, xP1_correct=bool(ok), generic_M=M2, generic_S=S2, generic_correct=bool(ok2),
                         group_order_is_4N=bool(Q.is_zero()))
rec('B', 'executed LD ladder for [4N]P (bits of 4N = %d)' % (4 * N).bit_length(), ladder)
TEST_M = {'floor: 1 M per candidate (no real test)': 1,
          'lower bound: 131 x-only doublings x 2M': 131 * 2,
          'ladder with x_P = 1 (valid since Tr b = 1), counted': ladder[0]['xP1_M'],
          'ladder generic base point, counted': ladder[0]['generic_M']}
C_IT = {'BBB09 5M/iteration': 5.0, 'redteam 6M/iteration': 6.0}
cons = {}
for tn, tm in TEST_M.items():
    row = dict(log2_Fq_mults=r2(LOG2_TRIALS + log2(tm), 3))
    for cn, ci in C_IT.items():
        row['log2 E0-rho equivalents (' + cn + ')'] = r2(LOG2_TRIALS + log2(tm) - (LOG2_RHO_E0 + log2(ci)), 3)
    cons[tn] = row
rec('B', 'construction cost of one B2 curve (a2=0,Tr b=1 search, 2^%.3f candidates)' % LOG2_TRIALS, cons)
rec('B', 'E0 rho cost in F_q-mults (5M / 6M per iteration), log2', [r2(LOG2_RHO_E0 + log2(5), 3), r2(LOG2_RHO_E0 + log2(6), 3)])
rec('B', 'native neg-only rho in F_q-mults (5M / 6M), log2', [r2(LOG2_RHO_NEG + log2(5), 3), r2(LOG2_RHO_NEG + log2(6), 3)])
rec('B', 'minimum construction/E0-rho ratio over all test and iteration-cost choices (log2)',
    r2(min(LOG2_TRIALS + log2(tm) for tm in TEST_M.values() if tm > 1) - (LOG2_RHO_E0 + log2(6)), 3))
rec('B', 'even with a 1-M test: construction/E0-rho (6M/it), log2', r2(LOG2_TRIALS - (LOG2_RHO_E0 + log2(6)), 3))

# =====================================================================================================
# (C) cofactor kernel-point bound and (D) Phi_p / CM routes
# =====================================================================================================
rec('C', 'full points over F_{q^r}: log2(131 * r^2) [scalar ~131 r bits x F_{q^r}-op >= r F_q-ops]', r2(log2(131 * r * r), 3))
rec('C', 'x-only over F_{q^{r/2}} (twist, c^(r/2) = -1): log2(131 * (r/2)^2)', r2(log2(131 * r_x * r_x), 3))
rec('C', 'Galbraith 2024 sec 2.2 form O~(k^2 log q) with k = r: log2(r^2 * 131)', r2(log2(r * r * 131), 3))
rec('C', 'bits of one F_{q^{r/2}} element (log2), bytes', [r2(log2(131 * r_x), 3), float(131 * r_x / 8)])
rec('C', 'kernel polynomial degree (p-1)/2 (log2), bytes at 131 bits/coeff', [r2(log2((p - 1) // 2), 3), float((p - 1) // 2 * 131 / 8)])
rec('D', 'Phi_p via Leroux / Robert / Kunzweiler-Robert O~(p^2 log q): log2 p^2, log2 p^2*131', [r2(2 * log2(p), 3), r2(2 * log2(p) + log2(131), 3)])
rec('D', 'Phi_p cubic (Gal99-era O(p^3)): log2 p^3', r2(3 * log2(p), 3))
rec('D', 'CM: log2 |D| level p = 7p^2, level 263p = 7(263p)^2', [r2(log2(7 * p * p), 3), r2(log2(7 * f * f), 3)])

# =====================================================================================================
# (E) Kani transport cost models
# =====================================================================================================
LOG2_E0_M = {ci: LOG2_RHO_E0 + log2(ci) for ci in (5.0, 6.0)}
def Mul(k, mode):
    return float(k) ** 1.585 if mode == 'kara' else float(k)
@functools.lru_cache(None)
def item(l, e):
    return (l, e, pi_order(l, e), guesses(l, e))
def theta_k(l):   # field of the level-n theta structure: level 3 (l != 3) or 5 (l = 3); both inert
    return pi_order(5, 1) if l == 3 else pi_order(3, 1)

def item_cost(x, later, Dm, model, mul, npush, C, cscale):
    l, e, K, g = x
    Cl = C * ((5 if l == 3 else 3) ** Dm if cscale else 1.0)
    if model == 'equations':                        # Robert notes CA 2.8, bullet 1: O(l^{g r}) in F_q
        u = Cl * l ** (Dm * (1 if l % 4 == 1 else 2)); Ks = 1
    else:
        u = Cl * l ** Dm; Ks = K
    if model == 'compositum+theta': Ks = lcm(K, theta_k(l))
    step = e * u * Mul(Ks, mul)
    own = (e - 1) * npush * u * Mul(K if model == 'equations' else Ks, mul)
    push = 0.0
    for (lj, ej, Kj, gj) in later:
        if model in ('descended', 'equations'): kf = Kj
        elif model == 'compositum': kf = lcm(K, Kj)
        elif model == 'compositum+theta': kf = lcm(lcm(K, Kj), lcm(theta_k(l), theta_k(lj)))
        else: raise ValueError(model)
        push += npush * Mul(kf, mul)
    return step + own + e * u * push

def tree_cost(items, Dm, model, mul, npush, C=1.0, cscale=False, root_nodes=1.0, force_first=None):
    """exact optimal ordering of a guess tree by DP over subsets. Returns (cost, order)."""
    items = tuple(items); s = len(items); full = (1 << s) - 1
    @functools.lru_cache(None)
    def dp(S):
        if S == full: return (0.0, ())
        nodesS = root_nodes * prod(items[i][3] for i in range(s) if S >> i & 1)
        best = None
        for i in range(s):
            if S >> i & 1: continue
            if force_first is not None and S == 0 and items[i][0] != force_first: continue
            later = [items[j] for j in range(s) if not (S >> j & 1) and j != i]
            cst = nodesS * items[i][3] * item_cost(items[i], later, Dm, model, mul, npush, C, cscale)
            sub = dp(S | (1 << i))
            cand = (cst + sub[0], (items[i][:2],) + sub[1])
            if best is None or cand[0] < best[0]: best = cand
        return best
    return dp(0)

def eff_iters(T_M, ci=5.0):
    """effective log2 rho-iteration equivalents: E0 rho + transport (F_q-mults / ci)."""
    return log2(2 ** LOG2_RHO_E0 + T_M / ci)
def breakevens(U, ci=5.0):
    """U = transport cost per unit C. C at which transport = E0 rho (+1 bit), and at which no gain vs native."""
    e0 = 2 ** LOG2_E0_M[ci]; nat = 2 ** (LOG2_RHO_NEG + log2(ci))
    return dict(C_transport_eq_E0rho=r2(e0 / U, 1), C_no_gain_vs_native=r2((nat - e0) / U, 1))

# ---- E.1 reproduce the on-disk figures ---------------------------------------------------------
def c_guess(c):
    if c == 1: return 1
    n = 0; cc = c
    while cc % 3 == 0: cc //= 3; n += 1
    return 4 * 3 ** ((n + 1) // 2 - 1)
def proposer_rt4(primes, c, g, C):
    """exact re-implementation of redteam-2/rt4_transport_cost.py (k = max eigen-order)."""
    ls = sorted(primes, reverse=True)
    n3 = 0; cc = c
    while cc > 1: cc //= 3; n3 += 1
    root = 4 * 3 ** ((n3 + 1) // 2 - 1) if c > 1 else 1
    total = 0.0; nodes = root / 2
    for d, l in enumerate(ls):
        nodes *= (l - 1)
        k = max(eig_orders(l))
        npush = 2 * (len(ls) - d - 1)
        total += nodes * (1 + npush) * C * l ** g * k ** 1.585
    return 2 * total
def shared_items(primes, c):
    n3 = 0; cc = c
    while cc > 1: cc //= 3; n3 += 1
    its = [item(l, 1) for l in primes]
    e3 = (n3 + 1) // 2
    if e3: its = [item(3, e3)] + its
    return its
CASES = {'dim2_c81_A=29.71.137.179 (rt2c horizontal gamma)': ([29, 71, 137, 179], 81, 2),
         'dim2_c3_A=11.23.79.107.109 (rt2c horizontal gamma)': ([11, 23, 79, 107, 109], 3, 2),
         'dim4_c1_A=23.37.53.67.137 (Galbraith two squares)': ([23, 37, 53, 67, 137], 1, 4),
         'dim8_c27_A=23.29.37.53.71 (C4-audit example, Thm 1 four squares)': ([23, 29, 37, 53, 71], 27, 8)}
repro = {}
for name, (pr, c, g) in CASES.items():
    A_ = prod(pr); M_ = c * A_ * A_; m_ = M_ - p
    row = dict(M=str(M_), log2_M=r2(log2(M_), 3), m=str(m_),
               proposer_rt4_log2_C9_100_1000=[r2(log2(proposer_rt4(pr, c, g, C)), 2) for C in (9, 100, 1000)])
    its = shared_items(pr, c)
    for model in ('descended', 'compositum', 'compositum+theta', 'equations'):
        for npm in ('2D', 'D'):
            npush = 2 * g if npm == '2D' else g
            cost, order = tree_cost(its, g, model, 'kara', npush, root_nodes=0.5, force_first=3 if c > 1 else None)
            U = 2 * cost          # F1 and F2bar
            row[f'{model}|npush={npm}|kara'] = dict(log2_U=r2(log2(U), 2), log2_T_C9_100_1000=[r2(log2(U * C), 2) for C in (9, 100, 1000)],
                                                   eff_iters_C9_100_1000=[r2(eff_iters(U * C), 3) for C in (9, 100, 1000)],
                                                   order=[list(o) for o in order])
    repro[name] = row
rec('E1', 'reproduction of disk figures (per-C costs in F_q-mults; eff with 5M/iteration)', repro)

# RT15-1's per-guess dim-2 model for its best hit a = 34154152 (no tree, no pushes; each guess pays the chain)
def rt15_pg(fac, split_mask, g=2):
    G1 = G2 = 1; C1 = C2 = 0.0
    for i, (l, e) in enumerate(fac):
        d = pi_order(l, e); gg = guesses(l, e); cst = e * l ** g * Mul(d, 'kara')
        if split_mask >> i & 1: G1 *= gg; C1 += cst
        else: G2 *= gg; C2 += cst
    return G1 * C1 + G2 * C2
a_rt15 = 34154152; M_rt15 = p + a_rt15 ** 2
fac_rt15 = [(int(l), int(e)) for l, e in factor(M_rt15)]
best_pg = min(rt15_pg(fac_rt15, s_) for s_ in range(1, (1 << len(fac_rt15)) - 1))
rec('E1', 'RT15-1 per-guess dim-2 model on a=34154152 (M=%s): log2 T (C=1)' % factor(M_rt15), r2(log2(best_pg), 2))

# ---- E.2 fresh parameter searches -------------------------------------------------------------
PRIMES_ALL = [int(l) for l in prime_range(3, 1300) if int(l) not in ALLOWED_BAD]
def admissible_item(l, e, kcap, allow_inert, allow7):
    ty = ptype(l)
    if ty == 'ramified' and (not allow7 or e > 1): return False
    if ty == 'inert' and not allow_inert: return False
    return pi_order(l, e) <= kcap

def best_split_cost(its, Dm, model, mul, npush):
    """dim-2 scalar gamma: coprime split into two independent guess trees (hash-table MITM)."""
    s = len(its); best = None
    for mask in range(1, (1 << s) - 1):
        if mask & 1 == 0: continue            # symmetry
        A1 = [its[i] for i in range(s) if mask >> i & 1]; A2 = [its[i] for i in range(s) if not mask >> i & 1]
        c1, o1 = tree_cost(A1, Dm, model, mul, npush); c2, o2 = tree_cost(A2, Dm, model, mul, npush)
        G1 = prod(x[3] for x in A1); G2 = prod(x[3] for x in A2)
        if best is None or c1 + c2 < best[0]:
            best = (c1 + c2, [list(x[:2]) for x in A1], [list(x[:2]) for x in A2], r2(log2(G1), 2), r2(log2(G2), 2))
    return best

def search_dim2_scalar(A_BITS=30, KCAP=400, allow_inert=True, allow7=True):
    """M = p + a^2, a even, a < 2^A_BITS, M smooth over admissible prime powers with field degree <= KCAP."""
    pp = []
    for l in PRIMES_ALL:
        for e in range(1, 8):
            if l ** e > 2 ** 40: break
            if not admissible_item(l, e, KCAP, allow_inert, allow7): break
            pp.append((l, e))
    roots = []
    for (l, e) in pp:
        n_ = l ** e
        try:
            rts = sorted(set(int(x) for x in Integers(n_)((-p) % n_).sqrt(all=True, extend=False)))
        except ValueError:
            rts = []
        assert all((x * x + p) % n_ == 0 for x in rts)
        for r0 in rts:
            roots.append((n_, (r0 * pow(2, -1, n_)) % n_, log2(l)))      # a = 2 i
    target = log2(p) - 0.01
    CH = 1 << 25; A_MAX = 1 << A_BITS
    cands = []
    for start in range(0, A_MAX // 2, CH):
        n_ = min(CH, A_MAX // 2 - start)
        logs = np.zeros(n_, dtype=np.float32)
        for (m_, i0, lg) in roots:
            first = (i0 - start) % m_
            logs[first::m_] += lg
        idx = np.nonzero(logs >= target)[0]
        cands.extend(int(2 * (start + j)) for j in idx)
    hits = []
    ppset = {}
    for (l, e) in pp: ppset[l] = max(ppset.get(l, 0), e)
    for a_ in cands:
        MM = p + a_ * a_; rem = MM; fac = []
        for l in sorted(ppset):
            if rem % l: continue
            e = 0
            while rem % l == 0: rem //= l; e += 1
            if e > ppset[l]: break
            fac.append((l, e))
        if rem == 1: hits.append((a_, MM, fac))
    return hits, len(cands), len(pp)

def enum_shared(cs, pool, maxlen=8):
    """M = c A^2, A a product of distinct pool primes with sqrt(p/c) < A < 3 sqrt(p/c)."""
    out = []
    for c in cs:
        lo = isqrt(p // c) + 1; hi = 3 * lo
        def recur(i, cur, pv):
            if pv >= lo:
                if pv < hi: out.append((c, tuple(cur)))
                return
            if len(cur) >= maxlen: return
            for j in range(i, len(pool)):
                l = pool[j]
                if pv * l >= hi: break
                recur(j + 1, cur + [l], pv * l)
        recur(0, [], 1)
    return out

def m_ok(m, kind, Bsplit=None):
    if m <= 0 or m % p == 0: return False, None
    if kind == 'four': return True, None
    fm = factor(ZZ(m))
    if kind == 'two':
        return all(not (int(l) % 4 == 3 and int(e) % 2) for l, e in fm), None
    # 'norm': m = 2^k m', inert primes to even powers, split primes <= Bsplit (horizontal gamma steps)
    mx = 1
    for l, e in fm:
        l = int(l); e = int(e)
        if l in (2, 7): continue
        if ptype(l) == 'inert' and e % 2: return False, None
        if ptype(l) == 'split': mx = max(mx, l)
    return (Bsplit is None or mx <= Bsplit), mx

def gamma_onetime(m, Dm=2):
    """rough one-time cost (F_q-mults) of evaluating a horizontal gamma of degree m on the needed torsion:
    per split prime l^e || m: e Velu steps from an eigen-kernel point found by a cofactor ladder over F_{q^k},
    k = min eigen-order; ~ (10*131*k + 10*l) * Mul(k)."""
    tot = 0.0
    for l, e in factor(ZZ(m)):
        l = int(l); e = int(e)
        if l in (2, 7) or ptype(l) != 'split': continue
        k = min(eig_orders(l))
        tot += e * (10 * 131 * k + 10 * l) * Mul(k, 'kara')
    return tot

MODELS = ('descended', 'compositum', 'compositum+theta', 'equations')
def eval_shared(c, S, Dm, model, mul, npush):
    its = shared_items(list(S), c)
    cost, order = tree_cost(its, Dm, model, mul, npush, root_nodes=0.5)
    return 2 * cost, order

if os.environ.get('G4_STOP') == 'E1':
    json.dump(RES, open(os.path.join(OUT, 'reconcile_numbers_E1only.json'), 'w'), indent=1, default=str); sys.exit(0)
KEEP = int(os.environ.get('G4_KEEP', '120'))
search = {}
POOL_SPLIT = [l for l in PRIMES_ALL if l <= 400 and ptype(l) == 'split']
POOL_INERT = [l for l in PRIMES_ALL if l <= 60 and ptype(l) == 'inert' and pi_order(l, 1) <= 400 and l != 3]
t_s = time.time()
shared_split = enum_shared([3 ** n for n in range(0, 9)], POOL_SPLIT)
shared_mixed = enum_shared([3 ** n for n in range(0, 7)], sorted(POOL_SPLIT + POOL_INERT), maxlen=7)
rec('E2', 'shared-guess candidate sets: split-only pool, split+inert pool', [len(shared_split), len(shared_mixed)])
def lb_shared(c, S, Dm):
    """ranking proxy: the descended/kara/2D tree cost for the fixed order 'most expensive unit first'
    (single pass, no DP); the exact DP is then run on the best KEEP admissible sets."""
    its = shared_items(list(S), c)
    its = sorted(its, key=lambda x: -(x[0] ** Dm) * Mul(x[2], 'kara'))
    tot = 0.0; nodes = 0.5
    for i, x in enumerate(its):
        nodes *= x[3]
        tot += nodes * item_cost(x, its[i + 1:], Dm, 'descended', 'kara', 2 * Dm, 1.0, False)
    return 2 * tot
for Dm, kind, label in ((2, 'norm', 'dim2 horizontal-gamma (rt2c type)'), (4, 'two', 'dim4 two squares'), (8, 'four', 'dim8 four squares (Thm 1 as proved)')):
    for poolname, cand in (('split', shared_split), ('split+inert', shared_mixed)):
        ranked = sorted(cand, key=lambda cs: lb_shared(cs[0], cs[1], Dm))
        keep = []
        for (c, S) in ranked:
            A_ = prod(S); m_ = c * A_ * A_ - p
            ok, mx = m_ok(m_, kind, Bsplit=10 ** 5)
            if ok: keep.append((c, S, m_, mx))
            if len(keep) >= KEEP: break
        for model in MODELS:
            # stage 1: rank all kept sets under the reference setting (kara, npush = 2D)
            stage1 = []
            for (c, S, m_, mx) in keep:
                U, order = eval_shared(c, S, Dm, model, 'kara', 2 * Dm)
                stage1.append((U, c, S, m_, mx))
            stage1.sort(key=lambda x: x[0])
            # stage 2: the best 6 under every (mul, npush) setting
            for mul in ('kara', 'lin'):
                for npm in ('2D', 'D'):
                    npush = 2 * Dm if npm == '2D' else Dm
                    best = None
                    for (_, c, S, m_, mx) in stage1[:6]:
                        U, order = eval_shared(c, S, Dm, model, mul, npush)
                        if best is None or U < best[0]: best = (U, c, S, m_, mx, order)
                    U, c, S, m_, mx, order = best
                    key = f'{label}|pool={poolname}|{model}|{mul}|npush={npm}'
                    search[key] = dict(log2_U=r2(log2(U), 2), c=c, A_primes=list(S), M=str(c * prod(S) ** 2), m=str(m_),
                                       max_split_prime_in_gamma=mx, order=[list(o) for o in order],
                                       log2_guesses=r2(log2(c_guess(c) * prod(guesses(l, 1) for l in S) / 2), 2),
                                       gamma_onetime_log2_Fq_mults=(r2(log2(gamma_onetime(m_)), 2) if kind == 'norm' else None),
                                       n_sets_evaluated=len(keep), **breakevens(U))
        print(f"  searched {label} pool={poolname}: {len(keep)} sets, t={time.time()-t_s:.0f}s", flush=True)
rec('E2', 'shared-guess searches done, seconds', r2(time.time() - t_s, 1))

# dim-2 scalar gamma: M = p + a^2
t_s = time.time()
hits, ncand, npp = search_dim2_scalar(A_BITS=30, KCAP=int(os.environ.get('G4_KCAP', '1200')))
rec('E2', 'dim2 scalar gamma sieve: prime powers, sieve candidates, fully factored hits', [npp, ncand, len(hits)])
scal = {}
if hits:
    # rank hits by a cheap proxy then evaluate the best few exactly under every model
    def proxy(h):   # RT15-1-style per-guess cost (no tree, no pushes), minimised over coprime splits: cheap ranking
        fac = h[2]
        return min(rt15_pg(fac, s_) for s_ in range(1, (1 << len(fac)) - 1))
    ranked = sorted(hits, key=proxy)[:12]
    for model in MODELS:
        stage1 = sorted(((best_split_cost([item(l, e) for (l, e) in fac], 2, model, 'kara', 4), a_, MM, fac)
                         for (a_, MM, fac) in ranked), key=lambda x: x[0][0])
        for mul in ('kara', 'lin'):
            for npm in ('2D', 'D'):
                npush = 4 if npm == '2D' else 2
                best = None
                for (_, a_, MM, fac) in stage1[:3]:
                    bs = best_split_cost([item(l, e) for (l, e) in fac], 2, model, mul, npush)
                    if best is None or bs[0] < best[0]: best = (bs[0], a_, MM, fac, bs)
                U, a_, MM, fac, bs = best
                scal[f'dim2 scalar gamma (M = p + a^2)|{model}|{mul}|npush={npm}'] = dict(
                    log2_U=r2(log2(U), 2), a=a_, M=str(MM), factorisation=fac, side1=bs[1], side2=bs[2],
                    log2_G1_G2=[bs[3], bs[4]], log2_table_entries=min(bs[3], bs[4]), n_hits=len(hits), **breakevens(U))
        print(f"  scalar model {model} done t={time.time()-t_s:.0f}s", flush=True)
search.update(scal)
rec('E2', 'dim2 scalar search seconds', r2(time.time() - t_s, 1))
json.dump(search, open(os.path.join(OUT, 'kani_search.json'), 'w'), indent=1)

# ---- E.3 summary table: dims x models, C scans ------------------------------------------------
def summarize():
    """per (dimension/route, model): reference setting (kara, npush = 2D, split pool) and the range over
    (mul in {kara, lin}) x (npush in {2D, D}) x (pool in {split, split+inert}). T(C) = C*U + gamma_onetime."""
    table = {}
    groups = {'dim2 (scalar gamma, M=p+a^2)': 'dim2 scalar gamma (M = p + a^2)|',
              'dim2 (horizontal gamma, rt2c)': 'dim2 horizontal-gamma (rt2c type)|',
              'dim4 (two squares)': 'dim4 two squares|',
              'dim8 (four squares, Thm 1 as proved)': 'dim8 four squares (Thm 1 as proved)|'}
    Dm_of = {'dim2 (scalar gamma, M=p+a^2)': 2, 'dim2 (horizontal gamma, rt2c)': 2, 'dim4 (two squares)': 4,
             'dim8 (four squares, Thm 1 as proved)': 8}
    for gname, pref in groups.items():
        Dm = Dm_of[gname]
        for model in MODELS:
            ks = [k for k in search if k.startswith(pref) and f'|{model}|' in k]
            if not ks: continue
            UG = {k: (2 ** search[k]['log2_U'], (2 ** search[k]['gamma_onetime_log2_Fq_mults'] if search[k].get('gamma_onetime_log2_Fq_mults') else 0.0)) for k in ks}
            T = lambda k, C: UG[k][0] * C + UG[k][1]
            ref_k = [k for k in ks if k.endswith('|kara|npush=2D') and ('pool=split|' in k or 'scalar' in k)]
            ref = ref_k[0]
            row = dict(reference_setting=ref, log2_U_reference=r2(log2(UG[ref][0]), 2),
                       log2_gamma_onetime_reference=(r2(log2(UG[ref][1]), 2) if UG[ref][1] else None),
                       log2_U_range_over_settings=[r2(log2(min(u for u, g in UG.values())), 2), r2(log2(max(u for u, g in UG.values())), 2)])
            for C in (1, 9, 100, 1000, 10 ** 4):
                effs = [eff_iters(T(k, C)) for k in ks]
                row[f'fixed C={C}: [log2 T ref, eff ref, [eff min, eff max]]'] = [r2(log2(T(ref, C)), 2), r2(eff_iters(T(ref, C)), 3), [r2(min(effs), 3), r2(max(effs), 3)]]
            for kappa in (1, 10, 100):
                C = kappa * 3 ** Dm
                effs = [eff_iters(T(k, C)) for k in ks]
                row[f'scaled C=kappa*3^D kappa={kappa} (C={C}): [log2 T ref, eff ref, [eff min, eff max]]'] = [r2(log2(T(ref, C)), 2), r2(eff_iters(T(ref, C)), 3), [r2(min(effs), 3), r2(max(effs), 3)]]
            lo_k = min(ks, key=lambda k: UG[k][0]); hi_k = max(ks, key=lambda k: UG[k][0])
            row.update({'breakeven (ref)': breakevens(UG[ref][0]), 'breakeven (cheapest setting)': breakevens(UG[lo_k][0]),
                        'breakeven (dearest setting)': breakevens(UG[hi_k][0])})
            table[f'{gname} | {model}'] = row
    return table
TABLE = summarize()
rec('E3', 'transport table', TABLE)

rec('Z', 'elapsed_s', r2(time.time() - T0, 1))
json.dump(RES, open(os.path.join(OUT, 'reconcile_numbers.json'), 'w'), indent=1, default=str)
print("DONE", flush=True)

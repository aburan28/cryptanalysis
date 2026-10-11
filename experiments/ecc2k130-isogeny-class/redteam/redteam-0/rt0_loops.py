"""Red team 0: cheapest 'horizontal-cycle' loop endomorphism acting as a primitive cube root
of unity (or any small-order root) on the N-subgroup, on E0 and on floor curves.

Loop = tau^e0 * taubar^e1 * prod_l pi_l^{a_l} pibar_l^{b_l}  (all exponents >= 0), l split in
Q(sqrt-7), l != 263, l <= B.  On a floor curve this is a closed walk of horizontal l-isogenies and
Frobenius/Verschiebung steps; it must lie in O_263 (index-262 congruence).  Cost model in
E0-affine-addition equivalents: tau step 0, taubar step 1 (a doubling), l-isogeny step (l+1)/4
(kernel polynomial of degree (l-1)/2 evaluated by Kohel/Velu: ~1.5(l-1) M + 1 I, addition ~6 M).

(1) Volume heuristic: #{e >= 0 : cost(e) <= C} ~ 131 * C^n / (n! prod c_i); need ~ (N-1)/phi(r)
    (E0) or (N-1)*262/phi(r) (floor) for one expected solution.  Report C_min(B).
(2) Exact-ish check at small scale: dlogs in F_N^* (PARI znlog) of all generator eigenvalues for
    l <= 60, then LLL/BKZ on the exponent lattice to exhibit an explicit loop with eigenvalue of
    order 3 (allowing any sign pattern is NOT allowed; we look for a nonnegative vector) -- we
    report the best nonnegative vector found and its cost.
"""
import json, math, sys, time
sys.path.insert(0, "/Volumes/SSD990/ecdlp-hardness-work/ground_truth")
import ecc2k
from sage.all import (kronecker, primes, ZZ, Integer, matrix, pari, RR, log)
from math import lgamma

N = ecc2k.N
lam = ecc2k.TAU_EIGEN
out = {}


def nm(a, b):
    return a * a - a * b + 2 * b * b


def norm_l_elements(l):
    sols = []
    bmax = int(math.isqrt(4 * l // 7)) + 1
    for b in range(-bmax, bmax + 1):
        for a in range(-2 * bmax - 2, 2 * bmax + 3):
            if nm(a, b) == l:
                sols.append((a, b))
    return sols


split = [l for l in primes(3, 20000) if l != 263 and kronecker(-7, l) == 1]


def cmin(Blim, target_log2):
    ls = [l for l in split if l <= Blim]
    costs = [1.0] + [(l + 1) / 4.0 for l in ls for _ in range(2)]  # taubar + (pi, pibar) per l
    n = len(costs)
    # log2( 131 * C^n / (n! prod c) ) = target  -> log2 C = (target - log2 131 + log2 n! + sum log2 c)/n
    lf = float(lgamma(n + 1)) / math.log(2)
    lc = sum(math.log2(c) for c in costs)
    logC = (target_log2 - math.log2(131) + lf + lc) / n
    return n, 2 ** logC


logNm1 = math.log2(N - 1)
rows = []
for Bl in (11, 30, 60, 100, 200, 400, 800, 1600, 3200, 6400):
    for which, tgt in (("E0", logNm1 - 1), ("floor", logNm1 + math.log2(262) - 1)):
        n, C = cmin(Bl, tgt)
        rows.append(dict(B=Bl, curve=which, generators=n, C_min_add_equiv=C))
out["volume_heuristic"] = rows
best = {}
for r in rows:
    k = r["curve"]
    if k not in best or r["C_min_add_equiv"] < best[k]["C_min_add_equiv"]:
        best[k] = r
out["volume_heuristic_best"] = best
print(json.dumps(best, indent=1))

# ---- (2) explicit small-scale lattice search with real dlogs
Bsmall = int(sys.argv[1]) if len(sys.argv) > 1 else 60
ls = [l for l in split if l <= Bsmall]
gens = [("taubar", (-1, -1), 1.0)]  # taubar = -1 - tau
for l in ls:
    sols = norm_l_elements(l)
    # pick one element pi_l and its conjugate (a + b tau)bar = a + b taubar = (a - b) - b tau
    a, b = sols[0]
    pib = (a - b, -b)
    assert nm(*pib) == l
    gens.append((f"pi_{l}", (a, b), (l + 1) / 4.0))
    gens.append((f"pibar_{l}", pib, (l + 1) / 4.0))
gp = pari
g = pari(f"znprimroot({N})")
t0 = time.time()
dl = []
for name, (a, b), c in gens:
    ev = (a + b * lam) % N
    d = int(pari(f"znlog(Mod({ev},{N}),{g})"))
    dl.append(d)
dlam = int(pari(f"znlog(Mod({lam},{N}),{g})"))
t_dlog = time.time() - t0
print("dlogs done", len(dl), t_dlog)
# 263-congruence: image in F_263^* of ratio (a + b*123)/(a + b*139)   (roots of x^2+x+2 mod 263)
r1, r2 = 123, 139
assert (r1 * r1 + r1 + 2) % 263 == 0 and (r2 * r2 + r2 + 2) % 263 == 0
g263 = int(pari("znprimroot(263)").lift())


def m263(a, b):
    x = (a + b * r1) % 263
    y = (a + b * r2) % 263
    return int(pari(f"znlog(Mod({x}*{pow(y, -1, 263)},263),Mod({g263},263))"))


m = [m263(a, b) for _, (a, b), _ in gens]
mlam = m263(0, 1)
M = N - 1
# target: eigenvalue zeta3 = g^(M/3) or g^(2M/3); lattice over exponents of gens (tau handled by
# trying all e0 in 0..130: subtract e0*dlam from target, and e0*mlam from 263-target)
n = len(gens)
W = [c for _, _, c in gens]
best_found = None
t0 = time.time()
# Embedding: rows = unit vectors scaled by weight, plus modular columns scaled by huge constant
S = 2 ** 200
for j in (1, 2):
    for e0 in range(131):
        tgtD = (j * (M // 3) - e0 * dlam) % M
        tgtm = (-e0 * mlam) % 262
        rowsL = []
        for i in range(n):
            row = [0] * (n + 3)
            row[i] = int(round(W[i] * 64))
            row[n] = dl[i] * S
            row[n + 1] = m[i] * S
            rowsL.append(row)
        row = [0] * (n + 3); row[n] = M * S; rowsL.append(row)
        row = [0] * (n + 3); row[n + 1] = 262 * S; rowsL.append(row)
        row = [0] * (n + 3); row[n] = -tgtD * S; row[n + 1] = -tgtm * S; row[n + 2] = 64 * 8; rowsL.append(row)
        L = matrix(ZZ, rowsL).LLL()
        for v in L.rows():
            if abs(v[n + 2]) != 64 * 8 or v[n] != 0 or v[n + 1] != 0:
                continue
            sgn = 1 if v[n + 2] > 0 else -1
            e = [sgn * v[i] // int(round(W[i] * 64)) for i in range(n)]
            if min(e) < 0:
                continue
            cost = sum(e[i] * W[i] for i in range(n))
            if best_found is None or cost < best_found[0]:
                best_found = (cost, e0, j, e)
        if e0 % 30 == 0:
            print("e0", e0, "j", j, "best", best_found[0] if best_found else None, time.time() - t0)
# verify best_found explicitly in O_K arithmetic
res = None
if best_found:
    cost, e0, j, e = best_found
    # multiply out alpha = tau^e0 * prod gens^e in Z[tau]
    def mul(u, v):
        a, b = u; c, d = v
        # (a + b t)(c + d t) = ac + (ad + bc) t + bd t^2 ;  t^2 = -t - 2
        return (a * c - 2 * b * d, a * d + b * c - b * d)
    alpha = (1, 0)
    for _ in range(e0):
        alpha = mul(alpha, (0, 1))
    for i, (name, ab, c) in enumerate(gens):
        for _ in range(e[i]):
            alpha = mul(alpha, ab)
    ev = (alpha[0] + alpha[1] * lam) % N
    res = dict(cost_add_equiv=cost, tau_exp=e0, exps={gens[i][0]: e[i] for i in range(n) if e[i]},
               eig_order=int(pari(f"znorder(Mod({ev},{N}))")),
               in_O263=(alpha[1] % 263 == 0), norm_log2=float(RR(nm(*alpha)).log(2)))
out["explicit_search"] = dict(B=Bsmall, generators=n, dlog_seconds=t_dlog, lattice_seconds=time.time() - t0,
                              best_nonneg=res)
print(out["explicit_search"])
json.dump(out, open(f"/Volumes/SSD990/ecdlp-hardness-work/redteam-0/rt0_loops_B{Bsmall}.json", "w"), indent=1, default=str)

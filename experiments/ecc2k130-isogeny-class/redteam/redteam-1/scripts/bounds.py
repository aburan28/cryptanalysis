"""Red-team quantitative bounds (Sage/PARI).
C: hypothetical curve C/F_2 whose Jacobian is isogenous to A (the 130-dim trace-zero factor
   of Res(E)): its point counts / place counts (necessary conditions), plus a naive
   dimension-count heuristic for existence at genus g in [130, 400].
D: simplicity of A over F_{2^d} (d = 1..16): irreducibility of its Frobenius polynomial.
E: factorisation of t (conductor of Z[pi^2] = f*|t|: levels that appear over F_{q^2}).
F: Petit-Quisquater first-fall-degree (optimistic, disputed) cost at n = 131.
G: Cheon (auxiliary-input) cost from N-1 and N+1 divisors (not applicable to plain ECDLP).
H: break-even genus for index calculus on Jac(C)(F_2) vs rho on E0.
I: rho class-canonicalisation break-even for a non-free endomorphism."""
import sys, json, math, time
sys.path.insert(0, "/Volumes/SSD990/ecdlp-hardness-work/ground_truth")
from sage.all import *
import ecc2k
N = Integer(ecc2k.N); t = Integer(ecc2k.t); q = Integer(2) ** 131
out = {}
RHO = float(0.5 * log(pi * N / (4 * 131), 2))
out["rho_E0_log2"] = RHO
# ---------- C ----------
def lucas(t1, qq, k):
    a, b = Integer(2), Integer(t1)
    if k == 0: return a
    for _ in range(k - 1):
        a, b = b, t1 * b - qq * a
    return b
L = {}  # tau^k + taubar^k
a0, a1 = Integer(2), Integer(-1)
L[0] = a0; L[1] = a1
for k in range(2, 1200):
    L[k] = -L[k - 1] - 2 * L[k - 2]
tj = {0: Integer(2), 1: t}
for j in range(2, 10):
    tj[j] = t * tj[j - 1] - q * tj[j - 2]
def S(k):  # sum over roots of A of alpha^k
    s = -L[k]
    if k % 131 == 0: s += 131 * tj[k // 131]
    return s
def Ccount(k): return 2 ** k + 1 - S(k)
assert Ccount(1) == 2 and Ccount(2) == 2
places = {}
minp = None; nonint = []
for d in range(1, 1049):
    tot = sum(moebius(d // e) * Ccount(e) for e in divisors(d))
    if tot % d != 0: nonint.append(d)
    a = tot // d
    places[d] = a
    if minp is None or a < minp[1]: minp = (d, a)
# #A(F_2) = N check via A(1) = P(1)/(1+1+2)
out["C_hypothetical_cover"] = dict(
    genus=130, C_F2=int(Ccount(1)), C_F4=int(Ccount(2)), C_F8=int(Ccount(3)),
    places_deg1_to_6=[int(places[d]) for d in range(1, 7)],
    places_deg131=str(places[131]), places_deg262=str(places[262]),
    min_place_count_d_le_1048=[int(minp[0]), str(minp[1])],
    all_place_counts_nonnegative=all(v >= 0 for v in places.values()),
    nonintegral_degrees=nonint,
    A_F2_order_equals_N=(Integer((1 - t + q)) // 4 == N),
    C_Fq_count=str(Ccount(131)),
    note="counts for 131 !| k equal those of the quadratic twist of E0 over F_2")
# naive dimension-count heuristic
heur = {}
for g in [130, 131, 140, 160, 200, 250, 300, 400]:
    # expected # curves of genus g whose Jacobian contains A: 2^(3g-3) * 2^{(g-130)(g-129)/4} / 2^{g(g+1)/4}
    e = (3 * g - 3) + (g - 130) * (g - 129) / 4.0 - g * (g + 1) / 4.0
    heur[g] = round(e, 1)
out["C_dimension_count_log2_expected_curves"] = heur
print("C done", out["C_hypothetical_cover"], heur, flush=True)
# ---------- D ----------
Rt = PolynomialRing(ZZ, 'T'); T = Rt.gen()
simp = {}
for d in list(range(1, 17)):
    td = tj[1] if d == 1 else None
    # trace of pi^d
    a, b = Integer(2), t
    for _ in range(d - 1):
        a, b = b, t * b - q * a
    td = b if d >= 1 else a
    Pd = T ** 262 - td * T ** 131 + q ** d
    Qd = T ** 2 - L[d] * T + 2 ** d
    Ad, r = Pd.quo_rem(Qd)
    assert r == 0
    t0 = time.time()
    irr = bool(pari(Ad).polisirreducible())
    simp[d] = dict(irreducible=irr, seconds=round(time.time() - t0, 2),
                   A_at_1=(str(Ad(1)) if d == 1 else None))
    print("D", d, irr, round(time.time() - t0, 2), flush=True)
out["D_A_simple_over_F2d"] = simp
# ---------- E ----------
out["E_factor_t"] = str(factor(abs(t)))
out["E_factor_f"] = str(factor(ecc2k.f))
# ---------- F: Petit-Quisquater optimistic ----------
def lbinom_sum(nv, D):
    return math.log2(sum(math.comb(nv, i) for i in range(0, min(D, nv) + 1)))
pq = {}
n = 131
for omega in (2.0, 2.37, 2.81):
    best = None
    for m in range(2, 12):
        D = m * m + 1
        for l in range(1, 80):
            nv = m * l
            logp = min(0.0, m * l - math.log2(math.factorial(m)) - n)
            rel = l
            calls = rel - logp
            pdp = omega * lbinom_sum(nv, D)
            la = math.log2(m) + 2 * rel
            tot = max(calls + pdp, la) + 1
            if best is None or tot < best[0]:
                best = (round(tot, 2), m, l, round(calls, 2), round(pdp, 2), round(la, 2))
    pq[str(omega)] = dict(log2_total=best[0], m=best[1], l=best[2], log2_calls=best[3],
                          log2_pdp=best[4], log2_LA=best[5])
    print("F", omega, pq[str(omega)], flush=True)
# crossover in n for the optimistic model vs Koblitz rho sqrt(pi 2^n/(4n))
def lcomb(nv, k):
    return (math.lgamma(nv + 1) - math.lgamma(k + 1) - math.lgamma(nv - k + 1)) / math.log(2)
def lsum_approx(nv, D):
    D = min(D, nv)
    if nv <= 400: return lbinom_sum(nv, D)
    return lcomb(nv, D) + 1.0   # sum_{i<=D} C(nv,i) <= 2 C(nv,D) when D <= nv/3
def pq_best(n, omega=2.0):
    b = None
    for m in range(2, 16):
        D = m * m + 1
        for l in range(max(1, n // m - 80), n // m + 6):
            logp = min(0.0, m * l - math.log2(math.factorial(m)) - n)
            tot = max(l - logp + omega * lsum_approx(m * l, D), math.log2(m) + 2 * l) + 1
            b = tot if b is None or tot < b else b
    return b
cross = None
for nn in list(range(131, 6001, 100)):
    rho_n = 0.5 * (math.log2(math.pi) + nn - math.log2(4 * nn))
    if pq_best(nn) < rho_n:
        cross = nn; break
pq["crossover_n_omega2_first_below_koblitz_rho"] = cross
out["F_petit_quisquater_optimistic"] = pq
# ---------- G: Cheon ----------
fm = factor(N - 1); fp = factor(N + 1)
bestm = min((float(0.5 * log(RR((N - 1) / dd), 2)) if dd < N else 999, dd) for dd in divisors(N - 1)
            if dd > 1)
def cheon_minus(dd): return max(0.5 * math.log2((N - 1) / dd), 0.5 * math.log2(dd))
cm = min((cheon_minus(dd), int(dd)) for dd in divisors(N - 1) if dd > 1)
def cheon_plus(dd): return max(0.5 * math.log2((N + 1) / dd), math.log2(dd))
cp = min((cheon_plus(dd), int(dd)) for dd in divisors(N + 1) if dd > 1)
out["G_cheon"] = dict(N_minus_1=str(fm), N_plus_1=str(fp),
                      best_minus=dict(log2_cost=round(cm[0], 2), d=str(cm[1]), log2_d=round(math.log2(cm[1]), 2)),
                      best_plus=dict(log2_cost=round(cp[0], 2), d=str(cp[1]), log2_d=round(math.log2(cp[1]), 2)),
                      applicable_to_plain_ECDLP=False)
print("G", out["G_cheon"], flush=True)
# ---------- H: break-even genus ----------
def Lbits(Qbits, alpha, c):
    lnQ = Qbits * math.log(2)
    return c * lnQ ** alpha * math.log(lnQ) ** (1 - alpha) / math.log(2)
H = {}
for name, alpha, c in [("L(1/2,sqrt2)", 0.5, math.sqrt(2)), ("L(1/2,1)", 0.5, 1.0),
                       ("L(1/3,1.923)", 1 / 3, (64 / 9) ** (1 / 3)), ("L(1/3,1)", 1 / 3, 1.0)]:
    g = 130
    vals = {gg: round(Lbits(gg, alpha, c), 1) for gg in (130, 200, 250, 300, 500, 1000)}
    while Lbits(g, alpha, c) < RHO and g < 10 ** 6: g += 1
    H[name] = dict(break_even_genus=g, cost_bits_at=vals)
out["H_cover_break_even"] = H
print("H", H, flush=True)
# ---------- I: rho canonicalisation ----------
I = {}
for r in (3, 11, 109, 131, 263, 2 ** 20):
    I[str(r)] = dict(max_relative_cost_for_gain=round((math.sqrt(r) - 1) / r, 4))
# psi on floor: x-map deg 11 (Horner 21 M) + 1 I + 16 sqrt/squarings, vs affine add 1I+2M+1S
for Icost in (8.0, 8.5):
    for Scost in (0.1, 1.0):
        c_psi = (21 + Icost + 16 * Scost) / (Icost + 2 + Scost)
        I[f"psi_rel_cost_I{Icost}_S{Scost}"] = round(c_psi, 2)
        I[f"psi_net_gain_r3_I{Icost}_S{Scost}"] = round(math.sqrt(3) / (1 + 3 * c_psi), 3)
out["I_rho_canonicalisation"] = I
json.dump(out, open(sys.argv[1], "w"), indent=1, default=str)
print("all done")

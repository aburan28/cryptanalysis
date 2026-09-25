"""Red team 0: endomorphism / automorphism / generic-rho tricks on the ECC2K-130 isogeny class.

Run: sage -python rt0_endos.py      (writes rt0_endos.json)

Everything here is exact integer arithmetic on the eigenvalue side (O_K -> F_N),
plus a handful of Sage checks on the real curves (E0, E0 twist).

Sections
  S1  constants, rho baselines
  S2  CVP: cheapest (min-norm) elements of O_K and O_263 whose eigenvalue on E0[N]
      is a primitive r-th root of unity, for small r | N-1; their tau-adic NAF weight
      (= cost in additions on E0, Frobenius free).  Break-even analysis for enlarging
      rho classes with such maps.
  S3  eigenvalue orders of ALL O_K elements of norm <= 2^B (direct enumeration)
  S4  loops through the floor: psi_k o tau^i o phi_k acts as -263*lambda^i; orders.
      Horizontal 263-endomorphisms of E0.
  S5  E[4]-translation classes (working in the full group)
  S6  multi-instance (Kuhn-Struik) and precomputation (Bernstein-Lange) numbers
  S7  twist (x-only implementation) numbers, recomputed on the real twist E0'
"""
import json, math, sys, time
sys.path.insert(0, "/Volumes/SSD990/ecdlp-hardness-work/ground_truth")
import ecc2k

N, t, q, p, f = ecc2k.N, ecc2k.t, ecc2k.q, ecc2k.p, ecc2k.f
lam = ecc2k.TAU_EIGEN
out = {}

# ---------------------------------------------------------------- S1
NM1_FACT = [(2, 3), (3, 1), (11, 1), (109, 1), (131, 1), (263, 1), (32326729, 1),
            (21234899465981031419669, 1)]
prod = 1
for pr, e in NM1_FACT:
    prod *= pr ** e
assert prod == N - 1
from sage.all import is_prime, ZZ, Integer
for pr, e in NM1_FACT:
    assert is_prime(pr)


def mult_order(x, n=N, fact=NM1_FACT):
    x %= n
    assert x != 0
    o = n - 1
    for pr, e in fact:
        for _ in range(e):
            if pow(x, o // pr, n) == 1:
                o //= pr
            else:
                break
    return o


assert (lam * lam + lam + 2) % N == 0
ord_lam = mult_order(lam)
ord_mlam = mult_order(-lam)
L2 = math.log2
def lg(x):
    return float(L2(x)) if x < 2**1000 else float(Integer(x).nbits())

base_E0 = 0.5 * (L2(math.pi) + lg(N) - L2(4 * 131))
base_floor = 0.5 * (L2(math.pi) + lg(N) - 2)
out["S1"] = dict(N=str(N), log2N=lg(N), ord_lambda=ord_lam, ord_minus_lambda=ord_mlam,
                 rho_E0_log2=base_E0, rho_floor_native_log2=base_floor,
                 ord_N_2_over_Nm1=str(Integer(N - 1) / mult_order(2)))
print("S1", out["S1"])

# ---------------------------------------------------------------- S2
# O_K = Z[tau], tau^2 + tau + 2 = 0, Nm(a + b tau) = a^2 - a b + 2 b^2 ; ev(a+b tau) = a + b lam mod N.
# Lattice of (a,b) with a + b*lam = 0 mod N: basis (N,0), (-lam,1).  Add 263 | b for O_263.
from sage.all import matrix, QQ, RR, sqrt as ssqrt, floor as sfloor

def nm(a, b):
    return a * a - a * b + 2 * b * b


def reduced_basis(cond):
    # lattice {(a,b): a + b lam = 0 mod N, cond | b}
    B = matrix(ZZ, [[N, 0], [-(lam * cond) % N, cond]])
    # Gram with the norm form: use embedding (a - b/2, b*sqrt7/2) scaled by 2: (2a - b, b*sqrt7)
    # LLL w.r.t. quadratic form a^2 - ab + 2b^2  == LLL on matrix with Gram G
    G = matrix(ZZ, [[2, -1], [-1, 4]])  # 2*Nm form
    R = B.LLL(delta=0.99)  # euclidean pre-reduction, then exact 2D Gauss w.r.t. G
    v1, v2 = [tuple(R[0]), tuple(R[1])]
    def Q(v):
        return nm(v[0], v[1])
    def dot(u, v):
        # bilinear form associated with Nm: B(u,v) = (Nm(u+v)-Nm(u)-Nm(v))/2
        return Integer(nm(u[0] + v[0], u[1] + v[1]) - Q(u) - Q(v)) / 2
    # Lagrange-Gauss
    if Q(v1) > Q(v2):
        v1, v2 = v2, v1
    while True:
        mu = (dot(v1, v2) / Q(v1)).round()
        v2 = (v2[0] - mu * v1[0], v2[1] - mu * v1[1])
        if Q(v2) >= Q(v1):
            break
        v1, v2 = v2, v1
    return v1, v2, dot


def cvp_min(target_ev, cond, basis):
    """min Nm over (a,b) with a + b lam = target mod N and cond | b.  Exact: enumerate
    around Babai point in the reduced basis (2D, radius small)."""
    v1, v2, dot = basis
    # a particular solution: (target, 0) works for any cond (b = 0)
    s = (target_ev % N, 0)
    # coordinates of s in basis v1,v2 over QQ
    M = matrix(QQ, [[v1[0], v1[1]], [v2[0], v2[1]]])
    c = matrix(QQ, [[s[0], s[1]]]) * M.inverse()
    c1, c2 = c[0, 0], c[0, 1]
    best = None
    for d1 in range(-3, 4):
        for d2 in range(-3, 4):
            k1 = c1.round() + d1
            k2 = c2.round() + d2
            a = s[0] - k1 * v1[0] - k2 * v2[0]
            b = s[1] - k1 * v1[1] - k2 * v2[1]
            n_ = nm(a, b)
            if best is None or n_ < best[0]:
                best = (n_, int(a), int(b))
    return best


def tnaf_weight(a, b):
    """tau-adic NAF of a + b tau (Solinas, mu = -1 for a=0 curve: tau^2 = -tau - 2 ...).
    Here tau^2 + tau + 2 = 0, i.e. tau^2 = mu*tau - 2 with mu = -1.  Returns (length, weight)."""
    mu = -1
    r0, r1 = int(a), int(b)
    L = 0; W = 0
    while r0 != 0 or r1 != 0:
        if r0 % 2 != 0:
            u = 2 - ((r0 - 2 * r1) % 4)
            r0 -= u
            W += 1
        # divide by tau: (r0 + r1 tau)/tau = (r1 + mu r0/2) - (r0/2) tau
        r0, r1 = r1 + mu * (r0 // 2), -(r0 // 2)
        L += 1
    return L, W


# sanity: TNAF of tau^k has weight 1
for k in range(1, 20):
    # tau^k as a + b tau: recurrence tau^{k+1} = tau*(a + b tau) = a tau + b(-tau - 2) = -2b + (a - b) tau
    a_, b_ = 0, 1
    for _ in range(k - 1):
        a_, b_ = -2 * b_, a_ - b_
    Lk, Wk = tnaf_weight(a_, b_)
    assert Wk == 1 and Lk == k + 1, (k, Lk, Wk)
# check eigen of tau^131 == 1 (pi acts trivially on F_q points)
a_, b_ = 0, 1
for _ in range(130):
    a_, b_ = -2 * b_, a_ - b_
assert (a_ + b_ * lam) % N == 1

bases = {1: reduced_basis(1), 263: reduced_basis(263)}
S2 = []
r_list = [3, 4, 6, 8, 11, 12, 22, 24, 109, 263, 3 * 131, 4 * 131, 11 * 131, 263 * 131]
g = None
# primitive root mod N
from sage.all import primitive_root
g = int(primitive_root(N))
for r in r_list:
    assert (N - 1) % r == 0
    z = pow(g, (N - 1) // r, N)
    assert mult_order(z) == r
    rec = {"r": r}
    for cond in (1, 263):
        best = None
        for j in range(1, r):
            if math.gcd(j, r) != 1:
                continue
            zz = pow(z, j, N)
            n_, a, b = cvp_min(zz, cond, bases[cond])
            assert (a + b * lam - zz) % N == 0 and b % cond == 0
            if best is None or n_ < best[0]:
                best = (n_, a, b, j)
        n_, a, b, j = best
        Lt, Wt = tnaf_weight(a, b)
        rec[f"cond{cond}"] = dict(min_norm_log2=lg(n_), a=str(a), b=str(b),
                                  tnaf_len=Lt, tnaf_weight=Wt,
                                  max_ab_log2=lg(max(abs(a), abs(b), 1)))
    # break-even: class size grows by factor s = r / gcd-overlap with <-1,lam> (order 262)
    s = r // math.gcd(r, 262)  # extra factor in class size
    c_star = 1.0 / (math.sqrt(s) + 1) if s > 1 else None
    # cost per extra image on E0 ~ TNAF weight additions (Frobenius free)
    c_E0 = rec["cond1"]["tnaf_weight"]
    if s > 1:
        gain = math.sqrt(s) / (1 + (s - 1) * c_E0)
        rec["class_factor"] = s
        rec["breakeven_cost_adds"] = c_star
        rec["E0_cost_per_image_adds"] = c_E0
        rec["net_log2_gain_E0"] = L2(gain)
    else:
        rec["class_factor"] = s
        rec["note"] = "root of unity already in <-1,lambda>"
    S2.append(rec)
    print("S2", r, rec.get("class_factor"), rec["cond1"]["min_norm_log2"],
          rec["cond1"]["tnaf_weight"], rec["cond263"]["min_norm_log2"], rec.get("net_log2_gain_E0"))
out["S2"] = S2

# ---------------------------------------------------------------- S3
B = int(sys.argv[1]) if len(sys.argv) > 1 else 18
X = 2 ** B
t0 = time.time()
small_orders = {}
count = 0
min_nontau_order = None
# enumerate a^2 - ab + 2b^2 <= X : 4 Nm = (2a-b)^2 + 7 b^2 -> |b| <= sqrt(4X/7)
bmax = int(math.isqrt(4 * X // 7)) + 1
taupow_ev = {pow(lam, k, N) for k in range(131)}
taupow_ev |= {(-x) % N for x in list(taupow_ev)}
for bb in range(-bmax, bmax + 1):
    rem = 4 * X - 7 * bb * bb
    if rem < 0:
        continue
    s_ = math.isqrt(rem)
    # (2a - b) in [-s_, s_]
    lo = (bb - s_ + 1) // 2 - 1
    hi = (bb + s_) // 2 + 1
    for aa in range(lo, hi + 1):
        n_ = nm(aa, bb)
        if n_ == 0 or n_ > X:
            continue
        count += 1
        ev = (aa + bb * lam) % N
        if ev in taupow_ev:
            continue
        o = mult_order(ev)
        if min_nontau_order is None or o < min_nontau_order[0]:
            min_nontau_order = (o, aa, bb, n_)
out["S3"] = dict(norm_bound_log2=B, elements=count,
                 min_order_excluding_pm_tau_powers_log2=lg(min_nontau_order[0]),
                 witness=dict(a=min_nontau_order[1], b=min_nontau_order[2], norm=min_nontau_order[3]),
                 seconds=time.time() - t0)
print("S3", out["S3"])

# ---------------------------------------------------------------- S4
ords = [mult_order((-263 * pow(lam, i, N)) % N) for i in range(131)]
# horizontal 263-endomorphisms of E0: elements of norm 263
h263 = [(a, b) for b in range(-20, 21) for a in range(-40, 41) if nm(a, b) == 263]
h_ords = sorted({mult_order((a + b * lam) % N) for a, b in h263})
out["S4"] = dict(min_log2_order_minus263_lam_i=min(lg(o) for o in ords),
                 ord_263_log2=lg(mult_order(263)),
                 norm263_elements=[(a, b) for a, b in h263],
                 norm263_eig_orders_log2=[lg(o) for o in h_ords])
print("S4", out["S4"])

# ---------------------------------------------------------------- S5
# classes in the full group Z/4N under <-1, tau, translations by E[4]> vs N-subgroup under <-1,tau>
out["S5"] = dict(classes_Nsub=str((N - 1) // 262), classes_full_with_E4=str((4 * N) // (262 * 4)),
                 ratio=float(Integer(4 * N) / (262 * 4) / ((N - 1) / 262)))

# ---------------------------------------------------------------- S6
ell = N / 262.0
rho1 = math.sqrt(math.pi * ell / 2)
def ks_total(L):
    s = 0.0; c = 1.0
    for i in range(L):
        s += c
        c *= (2 * i + 1) / (2 * i + 2)
    return rho1 * s
S6 = {"rho_one_log2": L2(rho1)}
for L in (1, 2, 131, 262, 263, 1000):
    tot = ks_total(L)
    S6[f"L{L}"] = dict(total_log2=L2(tot), per_instance_log2=L2(tot / L), naive_total_log2=L2(L * rho1))
# Bernstein-Lange: precomp ~ 1.21 sqrt(ell T) (walk length W ~ sqrt(ell/T)); per instance ~ 1.93 sqrt(ell/T)
for T in (2 ** 20, 2 ** 30, 2 ** 40):
    S6[f"BL_T2^{int(L2(T))}"] = dict(precomp_log2=L2(1.21 * math.sqrt(ell * T)),
                                     per_instance_log2=L2(1.93 * math.sqrt(ell / T)))
out["S6"] = S6
print("S6", S6)

# ---------------------------------------------------------------- S7 twist
from sage.all import EllipticCurve
K = ecc2k.field()
Et = EllipticCurve(K, [1, 1, 0, 0, 1])
tw = q + 1 + t
assert tw == ecc2k.TWIST_CARD
P114 = tw // (2 * 263 ** 2)
assert tw == 2 * 263 ** 2 * P114 and is_prime(P114)
# E0' is the a=1 Koblitz curve: #E0'(F_2)=2 -> tau'^2 - tau' + 2 = 0
from sage.all import GF, PolynomialRing
R = PolynomialRing(GF(P114), 'X'); Xv = R.gen()
roots = [int(r_) for r_, _ in (Xv ** 2 - Xv + 2).roots()]
ords_tw = [mult_order(r_, P114, [(pp, ee) for pp, ee in Integer(P114 - 1).factor()]) for r_ in roots]
# identify which root is Frobenius on a random point of order P114
Pt = Et.random_point() * (2 * 263 ** 2)
while Pt.is_zero():
    Pt = Et.random_point() * (2 * 263 ** 2)
assert (P114 * Pt).is_zero()
Fr = Et(Pt[0] ** 2, Pt[1] ** 2)
which = [r_ for r_ in roots if r_ * Pt == Fr]
assert len(which) == 1
out["S7"] = dict(P114=str(P114), P114_log2=lg(P114), tau_twist_eig_orders=ords_tw,
                 frobenius_eig=str(which[0]),
                 rho_twist_with_tau_log2=0.5 * (L2(math.pi) + lg(P114) - L2(4 * 131)),
                 rho_twist_neg_only_log2=0.5 * (L2(math.pi) + lg(P114) - 2),
                 leak_bits_small_part=L2(2 * 263 ** 2))
print("S7", out["S7"])

json.dump(out, open("/Volumes/SSD990/ecdlp-hardness-work/redteam-0/rt0_endos.json", "w"), indent=1, default=str)
print("done")

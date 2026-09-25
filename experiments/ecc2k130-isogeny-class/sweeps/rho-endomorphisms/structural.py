"""Parts (1), (2), (3a), (3b) of the rho-endomorphisms sweep.
Run: sage -python structural.py   -> structural.json
"""
import sys, json, time, math, random
sys.path.insert(0, "/Volumes/SSD990/ecdlp-hardness-work/ground_truth")
sys.path.insert(0, "/Volumes/SSD990/ecdlp-hardness-work/rho-endomorphisms")
import ecc2k
import common_rho as C
from sage.all import (GF, PolynomialRing, EllipticCurve, FractionField, Integer, ideal,
                      pari, factor, ZZ, QQ, NumberField, var)

out = {}
T0 = time.time()
N, LAM = C.N, C.LAM
rng = random.Random(20260923)

# ------------------------------------------------------------------ (1) Aut(E)
# (1a) symbolic: all (u,r,s,t) with u invertible mapping y^2+xy=x^3+a2 x^2+b to itself, char 2
R = PolynomialRing(GF(2), "u,v,r,s,tt,a2,b", order="lex")
u, v, r, s, tt, a2, b = R.gens()
F = FractionField(R)
Eg = EllipticCurve(F, [1, a2, 0, 0, b])
Et = Eg.change_weierstrass_model(u, r, s, tt)          # Sage's own transformation formulas
eqs = []
for new, old in zip(Et.a_invariants(), Eg.a_invariants()):
    num = (F(new) - F(old)).numerator()
    eqs.append(R(num))
eqs.append(u * v - 1)
Ig = R.ideal(eqs)
# b is a parameter with b != 0 ; saturate by b to drop b=0 components
Ig = Ig.saturation(R.ideal([b]))[0]
gb = Ig.groebner_basis()
out["aut_symbolic"] = {
    "equations": [str(e) for e in eqs],
    "groebner_basis_after_saturating_b": [str(g) for g in gb],
}
print("Aut symbolic GB:", gb)
# check: GB should say u=1, v=1, r=0, tt=0, s^2+s=0 -> exactly two automorphisms (s=0 id, s=1 negation)
gbset = set(str(g) for g in gb)
out["aut_symbolic"]["conclusion_two_automorphisms"] = (
    gbset == {"u + 1", "v + 1", "r", "s^2 + s", "tt"})
print("Aut symbolic ok:", out["aut_symbolic"]["conclusion_two_automorphisms"])

# (1b) per curve with Sage over F_q
K, curves = ecc2k.load()
aut_counts = {}
for lab, E in curves.items():
    assert E.j_invariant() != 0
    aut_counts[lab] = len(E.automorphisms())
out["aut_per_curve_counts_distinct"] = sorted(set(aut_counts.values()))
out["aut_per_curve_all_equal_2"] = all(c == 2 for c in aut_counts.values())
out["j_nonzero_all"] = True
print("per-curve Aut sizes:", out["aut_per_curve_counts_distinct"], time.time() - T0)

# ------------------------------------------------------------------ (2) tau on E0
E0 = curves["E0"]
lam_checks = {
    "lam": str(LAM),
    "lam^2+lam+2 == 0 mod N": (LAM * LAM + LAM + 2) % N == 0,
    "lam^131 == 1 mod N": pow(LAM, 131, N) == 1,
    "lam != 1": LAM != 1,
    "order(lam)": C.order_mod_N(LAM),
    "order(-lam)": C.order_mod_N(-LAM),
    "order(other root -1-lam)": C.order_mod_N(-1 - LAM),
}
def rand_N_point(E):
    while True:
        P = 4 * E.random_point()
        if not P.is_zero():
            assert (N * P).is_zero()
            return P
set_random = __import__("sage.all", fromlist=["set_random_seed"]).set_random_seed
set_random(20260923)
npts, ok_tau, ok_other = 20, 0, 0
for _ in range(npts):
    P = rand_N_point(E0)
    TP = E0(P[0] ** 2, P[1] ** 2)
    ok_tau += (TP == LAM * P)
    ok_other += (TP == ((-1 - LAM) % N) * P)
lam_checks["points_tested"] = npts
lam_checks["tau(P) == [lam]P count"] = ok_tau
lam_checks["tau(P) == [-1-lam]P count"] = ok_other
# class size for a few points: all +-tau^i(P), i=0..130
csz = []
for _ in range(3):
    P = rand_N_point(E0)
    cls = set()
    Q = P
    for i in range(131):
        cls.add((Q[0], Q[1])); cls.add((Q[0], Q[0] + Q[1]))   # -Q = (x, x+y)
        Q = E0(Q[0] ** 2, Q[1] ** 2)
    assert Q == P  # tau^131 = identity on E0(F_q)
    csz.append(len(cls))
lam_checks["class_sizes_of_3_random_points"] = csz
lam_checks["classes_on_N_subgroup_minus_O"] = "(N-1)/262 = %d, exact: %s" % ((N - 1) // 262, (N - 1) % 262 == 0)
lam_checks["rho_log2_classsize_262"] = C.rho_log2(262)
out["E0_tau"] = lam_checks
print("E0 tau:", lam_checks)

# ------------------------------------------------------------------ (3a) tau^k in O_263 ?
# tau^k = a_k + b_k tau with tau^2 = -tau - 2 ; element a + b tau = (a - b) + b*omega, in O_263 iff 263 | b
a_k, b_k = 1, 0
bk_mod263 = []
first_k_in_O263 = None
for k in range(1, 263):
    a_k, b_k = -2 * b_k, a_k - b_k           # (a + b tau) tau = a tau + b(-tau-2) = -2b + (a-b) tau
    if k <= 131:
        bk_mod263.append(b_k % 263)
    if b_k % 263 == 0 and first_k_in_O263 is None:
        first_k_in_O263 = k
    if k == 131:
        a131, b131 = a_k, b_k
tau_pow = {
    "k_range_checked": "1..262",
    "smallest_k>0_with_tau^k_in_O_263": first_k_in_O263,
    "num_k_in_1..130_with_263|b_k": sum(1 for x in bk_mod263[:130] if x == 0),
    "tau^131 = a + b*tau with b = ": str(b131),
    "b_131 == -f or f": b131 in (C.f, -C.f),
    "tau^131 trace check (2a - b == t)": 2 * a131 - b131 == C.t,
}
# via F_263: roots of x^2 + x + 2 mod 263 and the order of their ratio
rts = [x for x in range(263) if (x * x + x + 2) % 263 == 0]
ratio = rts[0] * pow(rts[1], -1, 263) % 263
o = 1; z = ratio
while z != 1:
    z = z * ratio % 263; o += 1
tau_pow["tau mod 263 in F_263 x F_263"] = rts
tau_pow["order of ratio in F_263^* (= order of class of p2 in Cl(O_263))"] = o
out["tau_powers_in_O263"] = tau_pow
print("tau powers:", tau_pow)

# roots of unity / units: norm-1 elements of O_K and O_263
def elements_of_norm(c, n):
    """all (x,y) with x^2 + x y + c y^2 = n (brute force over y)"""
    sols = []
    D4 = 4 * c - 1
    ymax = math.isqrt(4 * n // D4) + 1
    for y in range(-ymax, ymax + 1):
        disc = 4 * n - D4 * y * y
        if disc < 0:
            continue
        sq = math.isqrt(disc)
        if sq * sq != disc:
            continue
        for x2 in (-y + sq, -y - sq):
            if x2 % 2 == 0:
                x = x2 // 2
                if x * x + x * y + c * y * y == n and (x, y) not in sols:
                    sols.append((x, y))
    return sols
out["units"] = {"O_K norm-1 elements": elements_of_norm(2, 1),
                "O_263 norm-1 elements": elements_of_norm(C.C_O263, 1)}
print("units:", out["units"])

# elements of norm 2^k in O_263, k = 0..300 : eigenvalues must be +-2^s
ev263 = lambda x, y: (x + y * C.W_O263) % N
pow2 = {}
for s_ in range(0, 301):
    pow2[pow(2, s_, N)] = s_
    pow2[(-pow(2, s_, N)) % N] = -s_ - 1000   # marker for negative
norm2k = []
bad = []
for k in range(0, 301):
    n = 1 << k
    qf = pari("Qfb(1,1,%d)" % C.C_O263)
    sols = pari("qfbsolve(Qfb(1,1,%d), %d, 3)" % (C.C_O263, n))
    sols = [(int(v_[0]), int(v_[1])) for v_ in sols]
    for (x, y) in sols:
        assert x * x + x * y + C.C_O263 * y * y == n
        e = ev263(x, y)
        if e not in pow2:
            bad.append((k, x, y))
    ys = sorted(set(abs(y) for _, y in sols))
    norm2k.append((k, len(sols), ys[:3]))
out["O263_norm_2^k_elements"] = {
    "k_range": "0..300 (PARI qfbsolve flag 3 = all solutions, incl. non-primitive)",
    "num_solutions_per_k(first 5 and k=131,132,262)": [x for x in norm2k if x[0] < 5 or x[0] in (131, 132, 262)],
    "smallest_k_with_a_y!=0_solution": min([k for (k, c_, ys) in norm2k if any(yy != 0 for yy in ys)] or [None]),
    "solutions_with_eigenvalue_not_pm2^s": bad,
    "order_of_2_mod_N": str(C.order_mod_N(2)),
    "order_of_2_mod_N_log2": math.log2(C.order_mod_N(2)),
    "order_of_-2_mod_N_log2": math.log2(C.order_mod_N(-2)),
}
print("norm 2^k:", out["O263_norm_2^k_elements"])

# ------------------------------------------------------------------ (3b) Codex psi and friends
def tau_divisibility(x, y, c=C.C_O263):
    """for alpha = x + y*omega_263 = (x + 132 y) + 263 y tau  in Z[tau], return (v_tau, v_taubar)
    where v_tau = exponent of the Frobenius prime (tau) and v_taubar of its conjugate"""
    a, bb = x + 132 * y, 263 * y           # alpha = a + bb*tau
    def val(a, bb, which):
        # divide by tau:  (a + bb tau)/tau = (a + bb tau) * taubar / 2 ; taubar = -1 - tau
        # (a + bb tau)(-1 - tau) = -a - a tau - bb tau - bb tau^2 = -a - (a+bb) tau + bb(tau + 2)
        #                        = (2bb - a) + (-a) tau
        k = 0
        while True:
            if which == "tau":
                na, nb = 2 * bb - a, -a
            else:   # divide by taubar: multiply by tau / 2 : (a + bb tau) tau = -2bb + (a - bb) tau
                na, nb = -2 * bb, a - bb
            if na % 2 or nb % 2 or (a == 0 and bb == 0):
                return k
            a, bb = na // 2, nb // 2
            k += 1
    return val(a, bb, "tau"), val(a, bb, "taubar")

def describe(x, y, c=C.C_O263, w=C.W_O263):
    n = x * x + x * y + c * y * y
    e = (x + y * w) % N
    oe = C.order_mod_N(e)
    vt, vtb = tau_divisibility(x, y) if c == C.C_O263 else (None, None)
    return {"x": x, "y": y, "norm": n, "norm_factored": str(factor(n)), "eigenvalue": str(e),
            "order": str(oe), "order_log2": math.log2(oe), "v_tau(Frobenius)": vt, "v_taubar(Verschiebung)": vtb,
            "class_size_with_negation": str(oe if oe % 2 == 0 else 2 * oe)}

codex = {}
for (x, y) in [(775, -1), (774, 1), (-775, 1), (-774, -1)]:
    codex["%d,%d" % (x, y)] = describe(x, y)
out["codex_psi_candidates"] = codex
print("codex psi:", json.dumps(codex, indent=1))

# explicit verification on points: psi = iso o I_11 o Frob^16  on several floor curves
def frob_label(lab, k):
    return "%s%03d" % (lab[0], (int(lab[1:]) + k) % 131)
e_cand = {"774+w": (774 + C.W_O263) % N, "775-w": (775 - C.W_O263) % N}
psi_pts = {}
for lab in ["A000", "A001", "A064", "A130", "B000", "B001", "B064", "B130"]:
    t1 = time.time()
    E = curves[lab]; E16 = curves[frob_label(lab, 16)]
    assert E16.a6() == E.a6() ** (2 ** 16)
    Is = E16.isogenies_prime_degree(11)
    back = [I for I in Is if I.codomain().j_invariant() == E.j_invariant()]
    rec = {"num_Fq_rational_11_isogenies_from_E^(2^16)": len(Is), "num_back_to_E": len(back)}
    I = back[0]
    iso = I.codomain().isomorphism_to(E)
    hits = {}
    for _ in range(5):
        P = rand_N_point(E)
        P16 = E16(P[0] ** (2 ** 16), P[1] ** (2 ** 16))
        Q = iso(I(P16))
        for nm, e in e_cand.items():
            for sg in (1, -1):
                if Q == (sg * e % N) * P:
                    hits[(sg, nm)] = hits.get((sg, nm), 0) + 1
    rec["matches(sign,candidate)->count_of_5"] = {"%+d*%s" % k: v for k, v in hits.items()}
    rec["seconds"] = round(time.time() - t1, 1)
    psi_pts[lab] = rec
    print(lab, rec)
out["codex_psi_on_points"] = psi_pts

# isogeny-sandwich family 263*tau^k (= phi_hat o tau^k o phi through E0), k = 0..130
sandwich = []
for k in range(131):
    e = 263 * pow(LAM, k, N) % N
    sandwich.append(C.order_mod_N(e))
out["sandwich_263tau^k"] = {"min_order_log2": min(math.log2(o_) for o_ in sandwich),
                            "min_order": str(min(sandwich)),
                            "orders_distinct_values_log2": sorted(set(round(math.log2(o_), 3) for o_ in sandwich))}
print("sandwich:", out["sandwich_263tau^k"])

# lower bound on order r for norm n: need (n^(r/2)+1)^2 >= N  (alpha^r != 1)
def rmin(n):
    r = 1
    while (math.isqrt(n ** r) + 2) ** 2 < N:     # generous: sqrt(n^r)+2 >= |alpha|^r + 1
        r += 1
    return r
out["order_lower_bound_rmin(norm)"] = {str(n): rmin(n) for n in [2, 4, 8, 11 * 2 ** 16, C.C_O263, 2 ** 20, 2 ** 30, 2 ** 40, 2 ** 64]}
print("rmin:", out["order_lower_bound_rmin(norm)"])
out["seconds_total"] = round(time.time() - T0, 1)
json.dump(out, open("structural.json", "w"), indent=1, default=str)
print("done", out["seconds_total"])

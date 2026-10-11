"""Red-team structure checks on the real ECC2K-130 class (E0 + 262 floor curves).
A: 2-/4-torsion symmetry (FGHR/binary-Edwards-type) on all 263 curves, and the fact that the
   T2-invariant coordinate is the Verschiebung, i.e. the x-coordinate of the previous
   Frobenius conjugate (so the symmetry = working on a conjugate curve).
B: psi = Frob^e o (11-isogeny) on A000 and B000: eigenvalue on the N-part, its order, and the
   F_2-algebraic (Weil-descent) degree a psi-slot adds to S_{m+1} vs a tau-slot on E0.
J: Diem/Gaudry fixed-n factor base {x in F_2} on every curve (degenerate)."""
import sys, json, time, random as pyrandom
sys.path.insert(0, "/Volumes/SSD990/ecdlp-hardness-work/ground_truth")
from sage.all import *
import ecc2k
t0 = time.time()
K, curves = ecc2k.load()
N = ecc2k.N; s = ecc2k.TAU_EIGEN; CARD = ecc2k.CARD
R = pyrandom.Random(20260924)
set_random_seed(20260924)
out = {}
j2label = {ecc2k.dec(ecc2k.RECORDS[L]["j_int"]): L for L in ecc2k.LABELS}

def rand_pt(E):
    return E.random_point()

# ---------- A: torsion symmetry ----------
A = dict(checked=0, x_PplusT2_is_sqrtb_over_x=0, T4_ok=0, xF2_points={})
for L in ecc2k.LABELS:
    E = curves[L]; b = E.a6(); sb = b.sqrt()
    T2 = E(0, sb); assert 2 * T2 == E(0)
    ok = True
    for _ in range(3):
        P = rand_pt(E)
        if P.is_zero() or P[0] == 0: continue
        Q = P + T2
        ok &= (Q[0] == sb / P[0])
    A["x_PplusT2_is_sqrtb_over_x"] += int(ok)
    T4 = E.lift_x(b.sqrt().sqrt())
    A["T4_ok"] += int(2 * T4 == T2 and not (2 * T4).is_zero() and (4 * T4).is_zero())
    # J: points with x in F_2
    pts = [P for x in (K(0), K(1)) for P in E.lift_x(x, all=True)]
    A["xF2_points"][L] = len(pts)
    A["checked"] += 1
A["xF2_points_summary"] = {str(k): sum(1 for v in A["xF2_points"].values() if v == k)
                           for k in sorted(set(A["xF2_points"].values()))}
A["xF2_points_E0"] = A["xF2_points"]["E0"]
del A["xF2_points"]
ver = {}
for L in ["E0", "A000", "A057", "B000", "B130"]:
    E = curves[L]; T2 = E(0, E.a6().sqrt())
    phi = E.isogeny(T2)
    jc = phi.codomain().j_invariant()
    xmap = phi.rational_maps()[0]
    x = xmap.parent().gen(0) if hasattr(xmap.parent(), 'gen') else None
    lab = j2label.get(jc)
    prev = "E0" if L == "E0" else "%s%03d" % (L[0], (int(L[1:]) - 1) % 131)
    ver[L] = dict(codomain_label=lab, expected_prev_conjugate=prev, match=(lab == prev),
                  x_map=str(xmap)[:200])
A["T2_quotient_is_previous_conjugate"] = ver
out["A_torsion_symmetry"] = A
print("A done", time.time() - t0, json.dumps(A)[:1500], flush=True)

# ---------- B: psi on A000, B000 ----------
Fn = factor(N - 1)
out["N_minus_1_factorization"] = str(Fn)
def order_mod_N(mu):
    return Mod(mu, N).multiplicative_order()
Bres = {}
Rv = PolynomialRing(K, 'v'); v = Rv.gen()
for L in ["A000", "B000"]:
    E = curves[L]
    ts = time.time()
    isos = E.isogenies_prime_degree(11)
    t_iso = time.time() - ts
    recs = []
    for phi in isos:
        Ec = phi.codomain(); jc = Ec.j_invariant()
        lab = j2label.get(jc)
        kL = int(lab[1:]); k0 = int(L[1:])
        e = (k0 - kL) % 131   # Frob^e : X_kL -> X_k0
        Ecf = EllipticCurve(K, [a ** (2 ** e) for a in Ec.a_invariants()])
        isom = Ecf.isomorphism_to(E)
        def psi(P):
            Q = phi(P)
            if Q.is_zero(): return E(0)
            return isom(Ecf(Q[0] ** (2 ** e), Q[1] ** (2 ** e)))
        # point of order N
        while True:
            P = 4 * rand_pt(E)
            if not P.is_zero(): break
        assert (N * P).is_zero()
        psiP = psi(P)
        # candidate eigenvalues: +-s^a * beta(s), beta of norm 11 in O_K
        betas = {"3+2t": 3 + 2 * s, "-1+2t": -1 + 2 * s}
        found = None
        for a in [e] + [x for x in range(131) if x != e]:
            sa = power_mod(s, a, N)
            for bn, bv in betas.items():
                for sg in (1, -1):
                    mu = (sg * sa * bv) % N
                    if mu * P == psiP:
                        found = (a, bn, sg, int(mu)); break
                if found: break
            if found: break
        rec = dict(codomain=lab, frob_power=e, isogeny_time_s=round(t_iso, 2))
        if found:
            a, bn, sg, mu = found
            # check on a second point, and additivity
            P2 = 4 * rand_pt(E)
            rec.update(eig_frob_power=a, beta=bn, sign=sg, mu=str(mu),
                       second_point_ok=(psi(P2) == mu * P2),
                       additive_ok=(psi(P + P2) == psi(P) + psi(P2)))
            o = order_mod_N(mu)
            rec["mu_order"] = str(o); rec["mu_order_is_(N-1)/3"] = (o == (N - 1) // 3)
            rec["log2_mu_order"] = float(log(RR(o), 2))
        else:
            rec["eigen_found"] = False
        # descent degree of a psi-slot: x(psi P) = (Nx/Dx)^(2^e) with x(P) = v in V
        xm = phi.rational_maps()[0]
        num = Rv(xm.numerator().univariate_polynomial()) if hasattr(xm.numerator(), 'univariate_polynomial') else None
        try:
            numx = xm.numerator(); denx = xm.denominator()
            Rxy = numx.parent()
            num = Rv([c for c in numx.polynomial(Rxy.gen(0)).list()]) if numx.degree(Rxy.gen(1)) == 0 else None
        except Exception as ex:
            num = None
        # robust: evaluate as univariate via substitution
        Rx = PolynomialRing(K, 'x'); X = Rx.gen()
        xm_uni = phi.x_rational_map()
        Nn = Rv(xm_uni.numerator().list()); Dd = Rv(xm_uni.denominator().list())
        rec["x_map_deg_num_den"] = (Nn.degree(), Dd.degree())
        def maxwt(poly):
            return max(bin(i).count("1") for i, c in enumerate(poly.list()) if c != 0)
        for m in (3, 4, 5):
            M = 2 ** (m - 1)
            psi_slot = max(maxwt(Nn ** k * Dd ** (M - k)) for k in range(M + 1))
            plain = max(bin(k).count("1") for k in range(M + 1))
            rec[f"m{m}_slot_F2_degree_plain_or_tau"] = plain
            rec[f"m{m}_slot_F2_degree_psi"] = psi_slot
            rec[f"m{m}_slot_poly_degree_psi"] = 11 * M
        # cost of one psi evaluation in field ops (x only): Horner num(11)+den(10) + 1 inv + e squarings
        rec["psi_eval_cost_estimate"] = "21 M + 1 I + %d S (x-only), vs tau: 1 S" % e
        recs.append(rec)
    Bres[L] = recs
    print("B", L, json.dumps(recs, default=str)[:2500], flush=True)
out["B_psi"] = Bres
out["elapsed_s"] = time.time() - t0
json.dump(out, open(sys.argv[1], "w"), indent=1, default=str)
print("done", time.time() - t0)

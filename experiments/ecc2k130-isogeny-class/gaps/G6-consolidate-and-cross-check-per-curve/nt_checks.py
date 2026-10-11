"""G6 number-theory recomputation (run: sage -python nt_checks.py).

Recomputes, from scratch, every class-wide constant that the per-curve sweeps store
(t, #E, twist order, N, f, p, P114, embedding degrees, 263-orders, c = t/2 mod p and
its order, class numbers of the p-levels, rho log2 figures) and re-derives the
small-degree isogeny neighbours (l = 2, 11, 29) of all 263 curves from the classical
modular polynomials mod 2, so they can be compared with literature/per_curve.json.

Output: nt_checks.json (same directory).  Only reads ground_truth.json for the j list.
"""
import json, os, sys, time
from sage.all import (ZZ, QQ, GF, PolynomialRing, Integer, Mod, kronecker, is_prime,
                      RealField, factor, pari, sqrt as ssqrt)
from sage.schemes.elliptic_curves.mod_poly import classical_modular_polynomial

T0 = time.time()
HERE = os.path.dirname(os.path.abspath(__file__))
GT = "/Volumes/SSD990/ecdlp-hardness-work/ground_truth/ground_truth.json"
gt = json.load(open(GT))
out = {"script": "nt_checks.py", "sage": True}

# ---------- trace, orders, discriminant (Lucas recurrence, t1 = -1 from #E0(F_2) = 4)
q = Integer(2) ** 131
t1 = Integer(-1)
tk_prev, tk = Integer(2), t1
for k in range(2, 132):
    tk_prev, tk = tk, t1 * tk - 2 * tk_prev
t = tk
card = q + 1 - t
tw = q + 1 + t
assert card % 4 == 0
N = card // 4
D = t ** 2 - 4 * q
assert D % (-7) == 0
f2 = D // (-7)
f = f2.isqrt()
assert f * f == f2
assert f % 263 == 0
p = f // 263
assert tw % (2 * 263 ** 2) == 0
P114 = tw // (2 * 263 ** 2)
out["t"] = str(t); out["card"] = str(card); out["twist_card"] = str(tw); out["N"] = str(N)
out["f"] = str(f); out["p"] = str(p); out["P114"] = str(P114)
out["primes_proof_True"] = {"N": bool(Integer(N).is_prime(proof=True)), "p": bool(Integer(p).is_prime(proof=True)),
                            "263": bool(Integer(263).is_prime(proof=True)),
                            "P114": bool(Integer(P114).is_prime(proof=True))}
assert all(out["primes_proof_True"].values())
out["N_log2"] = float(RealField(100)(N).log2())
out["p_log2"] = float(RealField(100)(p).log2())
out["P114_log2"] = float(RealField(100)(P114).log2())
out["hasse_multiples_of_N"] = [int(m) for m in range(1, 10)
                               if abs(q + 1 - m * N) <= 2 * RealField(200)(q).sqrt()]
out["twist_factorization"] = str(factor(tw))
out["E0_twist_exponent_2*263*P114"] = str(2 * 263 * P114)

# ---------- embedding degrees
def order_mod(g, n):
    return Integer(Mod(g, n).multiplicative_order())
kN = order_mod(q, N)
out["embedding_degree_ord_N_q"] = str(kN)
out["embedding_degree_log2"] = float(RealField(100)(kN).log2())
out["embedding_degree_bits"] = int(kN.nbits())
out["ord_N_2"] = str(order_mod(2, N))
out["(N-1)/k"] = str((N - 1) // kN) if (N - 1) % kN == 0 else None
out["N_minus_1_factorization"] = str(factor(N - 1))
out["ord_P114_q"] = str(order_mod(q, P114))
out["ord_263_q"] = str(order_mod(q, 263))
out["ord_263sq_q"] = str(order_mod(q, 263 ** 2))
out["ord_263_2"] = str(order_mod(2, 263))
out["ord_131_2"] = str(order_mod(2, 131))
out["v263_card"] = int(card.valuation(263)); out["v263_twist"] = int(tw.valuation(263))

# ---------- p-level constants
c = (t * Mod(2, p) ** -1).lift()
out["c_t_over_2_mod_p"] = str(c)
r = order_mod(c, p)
out["r_ord_p_c"] = str(r)
out["r_x"] = str(r // 2) if Mod(c, p) ** (r // 2) == -1 else None
out["kronecker_-7_p"] = int(kronecker(-7, p)); out["kronecker_-7_263"] = int(kronecker(-7, 263))
# h(O_f) = h(O_K) f prod_{l|f} (1 - (d_K/l)/l) / [O_K^*:O_f^*];  h(O_K)=1, O_K^* = {+-1}
def h_order(fc):
    h = QQ(fc)
    for l, _ in factor(fc):
        h *= (1 - QQ(kronecker(-7, l)) / l)
    return ZZ(h)
out["h_O_263"] = str(h_order(263)); out["h_O_p"] = str(h_order(p)); out["h_O_263p"] = str(h_order(263 * p))
out["pari_qfbclassno_-7*263^2"] = str(pari(-7 * 263 ** 2).qfbclassno())
out["log2_h_O_p"] = float(RealField(100)(h_order(p)).log2())
out["log2_h_O_263p"] = float(RealField(100)(h_order(263 * p)).log2())
out["num_p_isogenies_p_plus_1"] = str(p + 1)

# ---------- rho figures (expected iterations, parallel rho, sqrt(pi*n/(2*classsize)))
R = RealField(200)
pi = R.pi()
def rho_log2(n, cls):
    return float((pi * R(n) / (2 * cls)).sqrt().log2())
out["rho_log2"] = {
    "E0_neg_tau_class_262": rho_log2(N, 262),
    "neg_only_class_2": rho_log2(N, 2),
    "no_speedup_class_1": rho_log2(N, 1),
    "twist_P114_neg_tau_class_262": rho_log2(P114, 262),
    "twist_P114_neg_only_class_2": rho_log2(P114, 2),
    "gap_bits_half_log2_131": float(R(131).log2() / 2),
}

# ---------- small-degree isogeny neighbours from Phi_l mod 2
Rz = PolynomialRing(GF(2), "zz")
zz = Rz.gen()
K = GF(2 ** 131, "z", modulus=zz ** 131 + zz ** 13 + zz ** 2 + zz + 1)
labels = [c_["label"] for c_ in gt["curves"]]
jint = {c_["label"]: int(c_["j_int"]) for c_ in gt["curves"]}
j_of = {lab: K.from_integer(jint[lab]) for lab in labels}
lab_of_j = {v: k for k, v in jint.items()}
RY = PolynomialRing(K, "Y")
nbrs = {}
for l in (2, 11, 29):
    Phi = classical_modular_polynomial(l)          # over ZZ, variables X, Y
    Xv, Yv = Phi.parent().gens()
    # reduce mod 2 and collect coefficients as dict (i, k) -> 1
    mono = [(e[0], e[1]) for e, cf in Phi.dict().items() if cf % 2 != 0]
    out.setdefault("phi_mod2_terms", {})[str(l)] = len(mono)
    Ygen = RY.gen()
    for lab in labels:
        j = j_of[lab]
        jp = [K(1)]
        maxe = max(e0 for e0, _ in mono)
        for _ in range(maxe):
            jp.append(jp[-1] * j)
        coeffs = {}
        for e0, e1 in mono:
            coeffs[e1] = coeffs.get(e1, K(0)) + jp[e0]
        poly = RY({k_: v for k_, v in coeffs.items() if v != 0})
        roots = poly.roots()
        lst = []
        for rt, m in roots:
            ri = rt.to_integer()
            lst.append([lab_of_j.get(ri, "notInClass:" + str(ri)), int(m)])
        lst.sort()
        nbrs.setdefault(lab, {})["l=%d" % l] = {"Fq_roots_with_mult": lst,
                                               "deg": int(poly.degree())}
out["small_isogeny_neighbours"] = nbrs
out["seconds"] = round(time.time() - T0, 1)
json.dump(out, open(os.path.join(HERE, "nt_checks.json"), "w"), indent=1)
print("nt_checks done", out["seconds"], "s")

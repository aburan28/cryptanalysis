"""Structural checks for the index-calculus sweep (ECC2K-130 class).

1. Frobenius-chart identity: sigma:(x,y)->(x^2,y^2) is a group isomorphism E_b(F_q) -> E_{b^2}(F_q)
   sending {x in W} to {x in W^2}.  Hence  C(X_{j+1}, V) = C(X_j, sqrt(V))  for the canonical V:
   the 131 conjugates of one floor curve on V are ONE curve on the 131 subspaces V^(1/2^i).
   Checked directly (Sage traces) against raw_counts.json for several j, k.
2. E0 (b = 1) is fixed by sigma, so C(E0, V) = C(E0, sqrt V).
3. Frobenius-invariant F_2-subspaces of F_{2^131}: x^131 + 1 = (x+1) * Phi_131 over F_2 with
   Phi_131 irreducible (ord_131(2) = 130), so the only invariant subspaces are 0, F_2, ker Tr
   (dim 130) and F_q (GGMP 2020 Lemma 4.1 + Schur).  Couveignes-Lercier torus / elliptic
   constructions (GGMP Sec. 4.2) need 131 | q0+1 = 3 or a multiple of 131 in the F_2 Hasse
   interval (3 - 2 sqrt 2, 3 + 2 sqrt 2): neither holds.
4. Degrees of floor j over F_2 (131: no F_2-model, so no tau endomorphism on floor curves).
5. rho baselines.
Run: export TMPDIR=/Volumes/SSD990/ecdlp-hardness-work/tmp; sage -python structure_checks.py
"""
import sys, json, math, time
sys.path.insert(0, "/Volumes/SSD990/ecdlp-hardness-work/ground_truth")
import ecc2k
from sage.all import GF, PolynomialRing, Mod, RR, pi, sqrt, log

OUT = "/Volumes/SSD990/ecdlp-hardness-work/index-calculus/"
K = ecc2k.field()
z = K.gen()
raw = json.load(open(OUT + "raw_counts_run1.json"))
C = raw["counts"]
res = {}
t0 = time.time()


def count_on(b, basis, k):
    """#{x in span(basis[:k]) : x = 0 or Tr(x + b/x^2) = 0} computed directly in Sage"""
    bb = ecc2k.dec(b)
    cnt = 0
    elems = [K(0)]
    for v in basis[:k]:
        elems = elems + [e + v for e in elems]
    for x in elems:
        if x == 0 or (x + bb / (x * x)).trace() == 0:
            cnt += 1
    return cnt


sqrt_basis = [(z ** i).sqrt() for i in range(16)]           # sqrt(V) = span(sqrt(z^i))
assert all(sqrt_basis[i] ** 2 == z ** i for i in range(16))
chart = []
for orb in "AB":
    for j in (0, 1, 57, 129, 130):
        lab = "%s%03d" % (orb, j)
        nxt = ecc2k.frobenius_next(lab)
        b = int(ecc2k.RECORDS[lab]["b_int"])
        # sanity: b(next) = b^2
        assert ecc2k.enc(ecc2k.dec(b) ** 2) == int(ecc2k.RECORDS[nxt]["b_int"])
        for k in (8, 10, 12):
            c_sqrt = count_on(b, sqrt_basis, k)
            chart.append({"curve": lab, "k": k, "C_curve_on_sqrtV": c_sqrt, "next": nxt,
                          "C_next_on_V": C[nxt]["canon"][str(k)], "match": c_sqrt == C[nxt]["canon"][str(k)]})
for k in (8, 10, 12):
    c = count_on(1, sqrt_basis, k)
    chart.append({"curve": "E0", "k": k, "C_curve_on_sqrtV": c, "next": "E0",
                  "C_next_on_V": C["E0"]["canon"][str(k)], "match": c == C["E0"]["canon"][str(k)]})
res["frobenius_chart_identity"] = chart
assert all(r["match"] for r in chart)
# overlap of V_k and sqrt(V_k): dimension (explains weak correlation of adjacent conjugates)
M = PolynomialRing(GF(2), "x")
ov = {}
from sage.all import matrix, GF as _GF
F2 = _GF(2)
for k in (8, 12, 16):
    rows = [[int(b) for b in format((z ** i).to_integer(), "0131b")] for i in range(k)] + \
           [[int(b) for b in format(sqrt_basis[i].to_integer(), "0131b")] for i in range(k)]
    r = matrix(F2, rows).rank()
    ov[str(k)] = {"dim_V_plus_sqrtV": int(r), "dim_intersection": int(2 * k - r)}
res["V_cap_sqrtV_dim"] = ov

# 3. invariant subspaces
x = M.gen()
fac = (x ** 131 + 1).factor()
res["x131_plus_1_factor_degrees"] = sorted(int(f.degree()) for f, e in fac)
res["ord_131_2"] = int(Mod(2, 131).multiplicative_order())
res["frobenius_invariant_subspace_dims"] = sorted(set([0, 1, 130, 131]))
assert res["x131_plus_1_factor_degrees"] == [1, 130]
res["couveignes_lercier_torus_condition_131_divides_3"] = (3 % 131 == 0)
lo, hi = 3 - 2 * math.sqrt(2), 3 + 2 * math.sqrt(2)
res["multiples_of_131_in_F2_hasse_interval"] = [m for m in range(1, 6) if lo < m < hi and m % 131 == 0]
# direct check that ker Tr is Frobenius-invariant and V_k (k = 2..16) is not
notinv = []
for k in range(2, 17):
    # V_k invariant iff (z^i)^2 in V_k for all i < k
    inv = all(((z ** i) ** 2).to_integer() < (1 << k) for i in range(k))
    notinv.append(inv)
res["canonical_V_k_frobenius_invariant_k2_16"] = notinv

# 4. degrees of floor j over F_2
degs = set()
for lab in ecc2k.LABELS[1:]:
    j = ecc2k.dec(ecc2k.RECORDS[lab]["j_int"])
    degs.add(int(j.minpoly().degree()))
res["floor_j_degrees_over_F2"] = sorted(degs)

# 5. rho baselines (expected iterations, van Oorschot-Wiener sqrt(pi n / (2 |class|)))
N = ecc2k.N
res["rho_log2"] = {
    "E0_neg_tau_class_262": float(RR(log(sqrt(pi * N / (4 * 131)), 2))),
    "floor_neg_only_class_2": float(RR(log(sqrt(pi * N / 4), 2))),
    "no_equivalence_class": float(RR(log(sqrt(pi * N / 2), 2))),
}
res["elapsed_s"] = time.time() - t0
json.dump(res, open(OUT + "structure_checks.json", "w"), indent=1)
print(json.dumps({k: v for k, v in res.items() if k != "frobenius_chart_identity"}, indent=1))
print("chart identity rows:", len(chart), "all match:", all(r["match"] for r in chart))

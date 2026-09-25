# Recompute every number in Codex's ecc2k130-ring-invariants.json,
# ecc2k130-ring-homomorphism-obstructions.json and ecc2k130-frobenius-subspaces.json
# from scratch (Sage/PARI), and compare field by field.
import json, sys, time
from pathlib import Path
from sage.all import (ZZ, QQ, Integer, GF, PolynomialRing, factor, is_prime, kronecker,
                      Mod, gcd, pari, isqrt, sqrt, log, RR)

W = Path("/Volumes/SSD990/ecdlp-hardness-work/codex-crosscheck")
CI = W / "codex_inputs"
out = {"script": "c01_ring_invariants.py", "checks": []}
def chk(name, codex, ours, note=""):
    ok = (codex == ours)
    out["checks"].append({"name": name, "codex": str(codex), "ours": str(ours), "agree": bool(ok), "note": note})
    print(("AGREE   " if ok else "DISAGREE"), name, "| codex:", str(codex)[:90], "| ours:", str(ours)[:90])
    return ok

ri = json.loads((CI / "ecc2k130-ring-invariants.json").read_text())
ho = json.loads((CI / "ecc2k130-ring-homomorphism-obstructions.json").read_text())
fs = json.loads((CI / "ecc2k130-frobenius-subspaces.json").read_text())

# --- F_2 points of E0: y^2 + xy = x^3 + 1 (affine points over F_2)
pts = sorted([(x, y) for x in range(2) for y in range(2) if (y*y + x*y - x**3 - 1) % 2 == 0])
chk("affine_points_over_F2", sorted(map(tuple, ri["affine_points_over_F2"])), pts)
t1 = 2 + 1 - (len(pts) + 1)          # #E(F_2) = 2 + 1 - t1
chk("base_trace", ri["base_trace"], t1)

# --- tau^131 = a + b*tau in Z[tau], tau^2 = t1*tau - 2  (i.e. tau^2 + tau + 2 = 0)
a, b = Integer(1), Integer(0)       # tau^0
for _ in range(131):
    # (a + b tau)*tau = a tau + b tau^2 = a tau + b (t1 tau - 2) = -2b + (a + t1 b) tau
    a, b = -2*b, a + t1*b
chk("tau_power_coefficients", ri["tau_power_coefficients"], [int(a), int(b)])
# trace of pi = a + b tau is 2a + b*t1
t = 2*a + b*t1
chk("extension_trace", ri["extension_trace"], int(t))
# independent: Lucas recurrence
s = [Integer(2), Integer(t1)]
for i in range(2, 132):
    s.append(t1*s[-1] - 2*s[-2])
chk("extension_trace_lucas", ri["extension_trace"], int(s[131]))
q = Integer(2)**131
N = (q + 1 - t) / 4
assert N in ZZ; N = ZZ(N)
chk("point_subgroup_order(N)", ho["point_subgroup_order"], int(N))
# Z[pi] = Z[b tau] has conductor |b| in Z[tau] = O_K
f = abs(b)
chk("frobenius_order_conductor", ri["frobenius_order_conductor"], int(f))
chk("t^2-4q == -7 f^2", True, bool(t*t - 4*q == -7*f*f))
F = factor(f)
chk("frobenius_order_conductor_factorization", {int(k): v for k, v in ri["frobenius_order_conductor_factorization"].items()},
    {int(pp): int(e) for pp, e in F})
p = Integer(146505763881528721)
chk("p prime (proof=True)", True, bool(p.is_prime(proof=True)) and bool(is_prime(Integer(263))))

# --- Lucas (Pocklington-style) certificate for p: witness 13, R-1 factors
cert = ri["large_factor_primality_certificate"]
R = p
fac_pm1 = {int(pp): int(e) for pp, e in factor(R - 1)}
chk("Lucas cert: factorization of p-1", {int(k): v for k, v in cert["R_minus_1_factors"].items()}, fac_pm1)
w = Integer(cert["witness"])
lucas_ok = (pow(w, R - 1, R) == 1) and all(pow(w, (R - 1)//pp, R) != 1 for pp in fac_pm1)
chk("Lucas cert: witness 13 valid (w^(p-1)=1, w^((p-1)/l)!=1 for all l)", True, bool(lucas_ok))
chk("Lucas cert leaves prime", True, all(Integer(pp).is_prime(proof=True) for pp in fac_pm1))

# --- orders between Z[pi] and O_K: conductors c | f, discriminant -7c^2,
#     class number via PARI qfbclassno (small) and formula h(O_c) = c * prod_{l|c}(1 - (-7/l)/l) (h(O_K)=1, w=2 -> unit index 1)
def h_formula(c):
    c = Integer(c); h = QQ(c)
    for l, _ in factor(c) if c > 1 else []:
        h *= (1 - QQ(kronecker(-7, l))/l)
    return ZZ(h)
ours_orders = []
for c in [Integer(1), Integer(263), p, 263*p]:
    D = -7*c*c
    hf = h_formula(c)
    # minimum degree of a non-integer endomorphism = min norm of an element of O_c \ Z = (1 - D)/4 for D = 1 mod 4 odd c
    # brute-check the norm form x^2 + xy + ((1-D)/4) y^2 at y=+-1: min over x of x^2 + x + (1-D)/4 is (1-D)/4 at x=0 or -1
    mind = (1 - D)/4
    rec = {"conductor": int(c), "discriminant": int(D), "class_number": int(hf),
           "minimum_noninteger_endomorphism_degree": int(mind)}
    if c < 10**6:
        hp = Integer(pari(f"qfbclassno({D})"))
        rec["qfbclassno"] = int(hp)
        assert hp == hf
    ours_orders.append(rec)
for cod, our in zip(ri["possible_orders_by_ordinary_order_classification"], ours_orders):
    for k in ["conductor", "discriminant", "class_number", "minimum_noninteger_endomorphism_degree"]:
        chk(f"order c={cod['conductor']}: {k}", int(cod[k]), int(our[k]))
chk("kronecker(-7,263)", 1, int(kronecker(-7, 263)), "263 splits in Q(sqrt-7)")
chk("kronecker(-7,p)", -1, int(kronecker(-7, p)), "p inert -> h(O_p)=p+1 (Codex's value implies -1)")
# class number of O_p also via PARI quadclassunit is infeasible to double check exactly? use qfbclassno on -7p^2 (PARI can do it, 115-bit disc)
t0 = time.time()
try:
    hp_big = Integer(pari(f"quadclassunit({-7*p*p}).no"))
    chk("h(-7p^2) via PARI quadclassunit (GRH-conditional)", int(ours_orders[2]["class_number"]), int(hp_big),
        f"{time.time()-t0:.1f}s")
except Exception as e:
    out["checks"].append({"name": "h(-7p^2) quadclassunit", "error": repr(e)})
# reduced forms of disc -484183: count
D263 = -7*263*263
cnt = 0
for aa in range(1, isqrt(-D263 // 3) + 1):
    for bb in range(-aa + 1, aa + 1):
        if (bb*bb - D263) % (4*aa): continue
        cc = (bb*bb - D263) // (4*aa)
        if cc < aa: continue
        if bb < 0 and (aa == cc): continue
        if gcd(gcd(aa, bb), cc) != 1: continue
        cnt += 1
chk("conductor_263_reduced_form_count (brute force enumeration of primitive reduced forms)", ri["conductor_263_reduced_form_count"], cnt)

# --- homomorphism obstructions: gcd(N, c) and gcd(N, h)
for cod, our in zip(ho["orders"], ours_orders):
    chk(f"gcd(N, conductor {cod['conductor']})", cod["gcd_subgroup_conductor"], int(gcd(N, our["conductor"])))
    chk(f"gcd(N, class number of c={cod['conductor']})", cod["gcd_subgroup_class_number"], int(gcd(N, our["class_number"])))
    chk(f"class number c={cod['conductor']} (obstructions file)", int(cod["class_number"]), int(our["class_number"]))

# --- Frobenius subspaces
chk("order_of_2_mod_131", fs["order_of_2_mod_131"], int(Mod(2, 131).multiplicative_order()))
chk("power_residues 2^e mod 131", {int(k): v for k, v in fs["power_residues"].items()},
    {int(e): int(pow(2, int(e), 131)) for e in fs["power_residues"]})
R2 = PolynomialRing(GF(2), "x"); x = R2.gen()
fd = sorted([[int(g.degree()), int(e)] for g, e in (x**131 - 1).factor()])
chk("x^131-1 factor degrees over F_2", sorted(fs["independent_polynomial_factor_degrees_and_multiplicities"]), fd)
# F_2[x]-submodules of F_2[x]/(x^131-1) <-> divisors: dims = sums of subsets of factor degrees
dims = sorted({0, 1, 130, 131})
chk("frobenius_invariant_F2_linear_subspace_dimensions", fs["frobenius_invariant_F2_linear_subspace_dimensions"], dims,
    "divisors of (x+1)*g130 have degrees 0,1,130,131")

out["all_agree"] = all(c.get("agree", False) for c in out["checks"])
(W / "raw" ).mkdir(exist_ok=True)
(W / "raw" / "c01_ring_invariants.json").write_text(json.dumps(out, indent=1))
print("ALL AGREE" if out["all_agree"] else "SOME DISAGREE")

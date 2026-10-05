# G2 supplementary: validate the Hess Theorem 5 / Menezes-Teske eq.(5) genus formula
#   g = 2^t - 2^(t-s1) - 2^(t-s2) + 1,  t = deg lcm(Ord_g1, Ord_g2), s_i = deg Ord_gi  (Tr(a)=0)
# and the MT Remark-2 GHS rule (gamma1 = 1, gamma2 = sqrt b), on toy fields F_{2^n}, n = 3, 5, 7.
#
# C = F(wp^{-1}(Delta_f)), f = g1/x + g2*x, F = F_{2^n}(x), [C:F] = 2^t.  Two computations:
#  (S) "subfield sum": Sage genus of each of the 2^t - 1 quadratic subextensions
#      F(w), w^2 + w = sum_{i<t} lam_i sigma^i(f), lam != 0, summed.  For an elementary abelian
#      2-extension of a rational function field, g(C) = sum of these genera (Garcia-Stichtenoth 1991 /
#      Kani-Rosen).  This checks the Ord/lcm bookkeeping and each quadratic genus directly.
#  (D) direct: Sage genus of the whole compositum (simple model of the tower), only for t <= 2
#      (a t = 3, degree-8 compositum did not finish in ~2 min in Sage 10.9, so larger t are not attempted).
# Run: export TMPDIR=/Volumes/SSD990/ecdlp-hardness-work/tmp; timeout 2400 sage toy_hess_genus.sage
import json, time, random, itertools

OUT = "/Volumes/SSD990/ecdlp-hardness-work/gaps/G2-verify-weil-descent-ghs"
P2.<X> = GF(2)[]


def ord_poly(u, n):
    """Ord_u in F_2[X] via the Krylov space of u under squaring (Sage linear algebra)."""
    if u == 0:
        return P2(1)
    V = u.parent().vector_space(map=False)
    vecs = []
    c = u
    for d in range(n + 1):
        vecs.append(V(c._vector_()))
        if matrix(GF(2), vecs).rank() < len(vecs):
            A = matrix(GF(2), vecs[:-1]).transpose()
            lam = A.solve_right(vecs[-1])
            return X**d + sum(lam[i] * X**i for i in range(d))
        c = c**2
    raise AssertionError


def hess(o1, o2):
    t = lcm(o1, o2).degree(); s1, s2 = o1.degree(), o2.degree()
    return 2**t - 2**(t - s1) - 2**(t - s2) + 1, t


def subfield_sum(k, g1, g2, t):
    F.<x> = FunctionField(k)
    R.<Y> = F[]
    total = 0
    gens = []
    for lam in itertools.product([0, 1], repeat=int(t)):
        if not any(lam):
            continue
        c1 = sum(g1**(2**i) for i in range(t) if lam[i])
        c2 = sum(g2**(2**i) for i in range(t) if lam[i])
        if c1 == 0 and c2 == 0:
            raise AssertionError("dependent combination -- t too large")
        h = c1 / x + c2 * x
        L = F.extension(Y**2 + Y + h, names='w')
        gl = int(L.genus())
        gens.append(gl)
        total += gl
    return total, gens


def direct_genus(k, g1, g2, t):
    F.<x> = FunctionField(k)
    L = F
    for i in range(t):
        e = 2**i
        fi = g1**e / x + g2**e * x
        S = PolynomialRing(L, 'Y%d' % i)
        Yv = S.gen()
        L = L.extension(Yv**2 + Yv + L(fi), names='w%d' % i)
    if t == 1:
        return int(L.genus())
    Ms = L.simple_model()
    M = Ms[0] if isinstance(Ms, tuple) else Ms
    return int(M.genus())


rng = random.Random(int(20260924))
rows = []
T0 = time.time()
for n in (3, 5, 7):
    k.<a> = GF(2**n)
    seen = set()
    cands = [(k(1), k(1))] + [(k(1), k.from_integer(rng.randrange(1, int(2**n)))) for _ in range(30)] + \
            [(k.from_integer(rng.randrange(1, int(2**n))), k.from_integer(rng.randrange(1, int(2**n)))) for _ in range(120)]
    for g1, g2 in cands:
        o1, o2 = ord_poly(g1, n), ord_poly(g2, n)
        gh, t = hess(o1, o2)
        key = (str(o1), str(o2), g1 == 1)
        if key in seen:
            continue
        seen.add(key)
        t1 = time.time()
        gs, gl = subfield_sum(k, g1, g2, t)
        row = {"n": int(n), "gamma1": str(g1), "gamma2": str(g2), "Ord1": str(o1), "Ord2": str(o2),
               "t": int(t), "hess_formula_genus": int(gh), "subfield_sum_genus": int(gs),
               "quadratic_subfield_genera_histogram": {str(v): gl.count(v) for v in sorted(set(gl))},
               "match_S": int(gh) == int(gs)}
        if t <= 2:
            gd = direct_genus(k, g1, g2, t)
            row["direct_compositum_genus"] = gd
            row["match_D"] = int(gh) == gd
        if g1 == 1:
            m = o2.degree() + (0 if o2 % (X + 1) == 0 else 1)
            rule = 2**(m - 1) if o2 % (X + 1) == 0 else 2**(m - 1) - 1
            row.update({"ghs_form": True, "m": int(m), "mt_rule_genus": int(rule), "rule_match": int(rule) == int(gs)})
        row["secs"] = round(time.time() - t1, 2)
        rows.append(row)
        print(json.dumps(row, default=int), flush=True)

summary = {"cases": len(rows), "all_match_subfield_sum": all(r["match_S"] for r in rows),
           "direct_cases": sum(1 for r in rows if "match_D" in r),
           "all_match_direct": all(r.get("match_D", True) for r in rows),
           "ghs_form_cases": sum(1 for r in rows if r.get("ghs_form")),
           "all_rule_match": all(r.get("rule_match", True) for r in rows),
           "genera_seen": sorted({r["hess_formula_genus"] for r in rows}),
           "elapsed_s": round(time.time() - T0, 1)}
print(json.dumps(summary, default=int))
json.dump({"summary": summary, "rows": rows}, open(OUT + "/toy_hess_genus.json", "w"), indent=1, default=int)

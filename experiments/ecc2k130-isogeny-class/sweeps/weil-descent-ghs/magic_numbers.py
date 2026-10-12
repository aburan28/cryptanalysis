"""GHS / generalized-GHS Weil-descent parameters for all 263 curves of the ECC2K-130 isogeny class.

Run:  export TMPDIR=/Volumes/SSD990/ecdlp-hardness-work/tmp
      sage -python magic_numbers.py

Definitions (verified against the literature, see report.md):
  * GHS magic number (Gaudry-Hess-Smart 2002; restated as eq. (1) of Jacobson-Menezes-Stein 2001):
        m(b) = dim_F2 Span_F2{ (1, b_0^(1/2)), ..., (1, b_(n-1)^(1/2)) },  b_i = sigma^i(b), sigma = Frobenius of K/F_2.
  * Ord_b = monic f in F2[x] of least degree with f(sigma)(b) = 0 (Menezes-Teske 2006, Sec. 2).
    Menezes-Teske Remark 2:  m = deg Ord_b if (x+1) | Ord_b, else deg Ord_b + 1;
                             g = 2^(m-1) if (x+1) | Ord_b, else 2^(m-1) - 1.
  * Hess-generalized GHS (Hess 2003 Thm 5; Menezes-Teske eq. (5)), b = (g1*g2)^2, Tr(a) = 0:
        t = deg lcm(Ord_g1, Ord_g2), s_i = deg Ord_gi,  g = 2^t - 2^(t-s1) - 2^(t-s2) + 1.
Everything below is computed three independent ways where possible:
  (a) rank of the 131 x 132 F2-matrix [1 | coords(sigma^i sqrt b)] (Sage matrix over GF(2)),
  (b) the same rank via a pure-Python bitmask Gaussian elimination,
  (c) the Krylov minimal polynomial Ord_b plus the Menezes-Teske formula.
"""
import sys, json, time, random, math, hashlib
sys.path.insert(0, "/Volumes/SSD990/ecdlp-hardness-work/ground_truth")
import ecc2k
from sage.all import GF, PolynomialRing, matrix, vector, EllipticCurve, cyclotomic_polynomial, gcd, lcm

OUT = "/Volumes/SSD990/ecdlp-hardness-work/weil-descent-ghs/"
n = 131
t0 = time.time()
K, curves = ecc2k.load()
R = PolynomialRing(GF(2), "x"); x = R.gen()
PHI = R(cyclotomic_polynomial(n))
XN1 = x**n + 1
assert PHI.is_irreducible() and PHI.degree() == 130 and (x + 1) * PHI == XN1
fac = XN1.factor()
assert sorted(fi.degree() for fi, e in fac) == [1, 130]


def bits(u):
    return ecc2k.enc(u)


def conj_list(u):
    """[u, u^2, u^4, ..., u^(2^(n-1))]"""
    out = [u]
    for _ in range(n - 1):
        out.append(out[-1] ** 2)
    assert out[-1] ** 2 == u
    return out


def rank_bitmask(rows):
    """rank over F2 of a list of ints (bit vectors)"""
    piv = {}
    r = 0
    for v in rows:
        while v:
            h = v.bit_length() - 1
            if h in piv:
                v ^= piv[h]
            else:
                piv[h] = v
                r += 1
                break
    return r


def krylov_ord(u):
    """Ord_u: least-degree f in F2[x] with f(sigma)(u) = 0, by finding the first linear
    dependency in the Krylov sequence u, sigma(u), sigma^2(u), ...  Returns a Sage poly."""
    piv = {}  # pivot bit -> (vector, combo)  combo = bitmask over x^j
    w = u
    for i in range(n + 1):
        v = bits(w)
        c = 1 << i
        while v:
            h = v.bit_length() - 1
            if h in piv:
                pv, pc = piv[h]
                v ^= pv
                c ^= pc
            else:
                piv[h] = (v, c)
                break
        if v == 0:
            # c encodes f with f(sigma)(u) = 0 and leading term x^i
            f = sum((R(x) ** j for j in range(i + 1) if (c >> j) & 1), R(0))
            return f
        w = w ** 2
    raise AssertionError("no dependency found (impossible: x^n+1 annihilates)")


def apply_poly_sigma(f, u):
    acc = K(0)
    w = u
    for j in range(f.degree() + 1):
        if f[j] == 1:
            acc += w
        w = w ** 2
    return acc


def gghs_genus(o1, o2):
    tt = lcm(o1, o2).degree()
    s1, s2 = o1.degree(), o2.degree()
    return 2 ** tt - 2 ** (tt - s1) - 2 ** (tt - s2) + 1


# gGHS genus for every achievable pair of Ord-types {x+1, PHI, x^131+1}
ORD_TYPES = {"x+1": x + 1, "Phi131": PHI, "x^131+1": XN1}
GGHS_TABLE = {}
for a_ in ORD_TYPES:
    for b_ in ORD_TYPES:
        GGHS_TABLE[(a_, b_)] = gghs_genus(ORD_TYPES[a_], ORD_TYPES[b_])


def ord_type(u):
    if u in (K(0),):
        return None
    if u == K(1):
        return "x+1"
    return "Phi131" if u.trace() == 0 else "x^131+1"


rng = random.Random(20260923)
results = {}
Mspace = None
for lab in ecc2k.LABELS:
    E = curves[lab]
    a1, a2, a3, a4, b = E.a_invariants()
    assert a1 == 1 and a3 == 0 and a4 == 0 and a2 == 0
    jb = (1 / E.j_invariant())
    assert jb == b
    v = b.sqrt()
    assert v * v == b
    cv = conj_list(v)
    cb = conj_list(b)
    # (a) Sage GF(2) matrices
    Mv = matrix(GF(2), [[(bits(u) >> k) & 1 for k in range(n)] for u in cv])
    Maug = matrix(GF(2), [[1] + [(bits(u) >> k) & 1 for k in range(n)] for u in cv])
    Mb = matrix(GF(2), [[(bits(u) >> k) & 1 for k in range(n)] for u in cb])
    d_span_sqrtb = Mv.rank()
    m_rank_sage = Maug.rank()
    d_span_b = Mb.rank()
    # (b) bitmask elimination
    m_rank_bitmask = rank_bitmask([(1 << n) | bits(u) for u in cv])
    d_rank_bitmask = rank_bitmask([bits(u) for u in cv])
    # (c) Krylov Ord_b, Ord_sqrt(b)
    ordb = krylov_ord(b)
    ordv = krylov_ord(v)
    assert ordb == ordv, lab
    assert apply_poly_sigma(ordb, b) == 0
    assert XN1 % ordb == 0
    xp1_divides = (ordb % (x + 1) == 0)
    m_formula = ordb.degree() if xp1_divides else ordb.degree() + 1
    g_ghs = 2 ** (m_formula - 1) if xp1_divides else 2 ** (m_formula - 1) - 1
    tr_b = int(b.trace())
    tr_v = int(v.trace())
    # Hess Cor. 6 (gamma in k, n odd => u = 1): g = 2^(m-1)-1 iff Tr_{K/F2}(beta) = 0, beta = sqrt(b)
    g_hess_cor6 = 2 ** (m_formula - 1) - 1 if tr_v == 0 else 2 ** (m_formula - 1)
    # Phi(sigma)(b) = Tr(b)
    assert apply_poly_sigma(PHI, b) == K(tr_b)
    assert m_rank_sage == m_rank_bitmask == m_formula, (lab, m_rank_sage, m_rank_bitmask, m_formula)
    assert d_span_sqrtb == d_rank_bitmask == d_span_b == ordb.degree()
    assert g_ghs == g_hess_cor6
    # generalized GHS: minimal genus over all decompositions sqrt(b) = g1*g2, g_i != 0.
    # Achievable Ord-type pairs: if b == 1 -> (x+1,x+1) possible; if b not in F2 then at least one
    # g_i not in F2.  Lower bound = min of GGHS_TABLE over pairs compatible with b.
    if b == 1:
        pairs = list(GGHS_TABLE.items())
    else:
        pairs = [(k_, g_) for k_, g_ in GGHS_TABLE.items() if k_ != ("x+1", "x+1")]
    gghs_min_bound = min(g_ for k_, g_ in pairs)
    gghs_min_pairs = sorted(set(tuple(sorted(k_)) for k_, g_ in pairs if g_ == gghs_min_bound))
    # exhibit an explicit decomposition attaining the bound (non-trivial one, g1,g2 not in F2)
    witness = None
    if b != 1:
        for _ in range(1000):
            g1 = K.random_element() if False else ecc2k.dec(rng.getrandbits(n))
            if g1 in (K(0), K(1)):
                continue
            g2 = v / g1
            if g2 in (K(0), K(1)):
                continue
            o1, o2 = krylov_ord(g1), krylov_ord(g2)
            if gghs_genus(o1, o2) == gghs_min_bound:
                assert g1 * g2 == v and (g1 * g2) ** 2 == b
                witness = {"gamma1_int": str(bits(g1)), "gamma2_int": str(bits(g2)),
                           "Ord_gamma1_deg": o1.degree(), "Ord_gamma2_deg": o2.degree(),
                           "t_lcm_deg": lcm(o1, o2).degree(), "genus": str(gghs_genus(o1, o2))}
                break
        assert witness is not None
    results[lab] = {
        "label": lab,
        "b_int": ecc2k.RECORDS[lab]["b_int"],
        "trace_b": tr_b,
        "trace_sqrt_b": tr_v,
        "b_in_F2": bool(b == 1),
        "Ord_b": str(ordb),
        "deg_Ord_b": int(ordb.degree()),
        "dim_span_conjugates_sqrt_b": int(d_span_sqrtb),
        "x_plus_1_divides_Ord_b": bool(xp1_divides),
        "magic_number_rank_sage": int(m_rank_sage),
        "magic_number_rank_bitmask": int(m_rank_bitmask),
        "magic_number_menezes_teske_formula": int(m_formula),
        "ghs_genus": str(g_ghs),
        "ghs_genus_log2": math.log2(g_ghs),
        "gghs_min_genus_over_decompositions": str(gghs_min_bound),
        "gghs_min_genus_log2": math.log2(gghs_min_bound),
        "gghs_min_pairs": gghs_min_pairs,
        "gghs_witness": witness,
    }

# E0 extra: the m = 1 descent is E0/F2 itself; the trace (conorm-norm) map kills the N-part.
E0 = curves["E0"]
N = ecc2k.N
s = ecc2k.TAU_EIGEN
geom = sum(pow(s, i, N) for i in range(n)) % N
assert pow(s, n, N) == 1 and geom == 0
E0F2 = EllipticCurve(GF(2), [1, 0, 0, 0, 1])
card_E0F2 = E0F2.cardinality()
assert card_E0F2 == 4
trace_checks = []
for trial in range(3):
    while True:
        P = E0.lift_x(ecc2k.dec(rng.getrandbits(n)), all=True)
        if P:
            P = 4 * P[0]
            if not P.is_zero():
                break
    assert (N * P).is_zero()
    S = E0(0)
    Q = P
    for i in range(n):
        S += Q
        Q = E0(Q[0] ** 2, Q[1] ** 2)
    assert Q == P
    trace_checks.append(bool(S.is_zero()))
assert all(trace_checks)

summary = {
    "n": n,
    "x^131+1_factor_degrees_over_F2": sorted(int(fi.degree()) for fi, e in fac),
    "gghs_genus_table_by_Ord_types": {f"{k_[0]},{k_[1]}": str(g_) for k_, g_ in GGHS_TABLE.items()},
    "E0_trace_map": {"sum_{i<131} s^i mod N": int(geom), "s^131 mod N": int(pow(s, n, N)),
                      "random_order_N_points_with_sum_of_131_frobenius_conjugates_zero": trace_checks,
                      "#E0(F_2)": int(card_E0F2)},
    "counts": {},
    "elapsed_s": None,
}
ms = [r["magic_number_rank_sage"] for r in results.values()]
from collections import Counter
summary["counts"]["magic_number"] = dict(Counter(map(str, ms)))
summary["counts"]["trace_b"] = dict(Counter(str(r["trace_b"]) for r in results.values()))
summary["counts"]["Ord_b"] = dict(Counter(r["Ord_b"] if r["deg_Ord_b"] < 3 else f"deg{r['deg_Ord_b']}:{'x^131+1' if r['Ord_b']==str(XN1) else r['Ord_b'][:30]}" for r in results.values()))
summary["counts"]["ghs_genus_log2"] = dict(Counter(str(r["ghs_genus_log2"]) for r in results.values()))
summary["counts"]["ghs_genus"] = dict(Counter(r["ghs_genus"] for r in results.values()))
summary["counts"]["gghs_min_genus"] = dict(Counter(r["gghs_min_genus_over_decompositions"] for r in results.values()))
summary["elapsed_s"] = round(time.time() - t0, 1)

with open(OUT + "raw_magic_numbers.json", "w") as fh:
    json.dump({"summary": summary, "curves": results}, fh, indent=1, default=lambda o: int(o))
print(json.dumps(summary, indent=1, default=lambda o: int(o)))

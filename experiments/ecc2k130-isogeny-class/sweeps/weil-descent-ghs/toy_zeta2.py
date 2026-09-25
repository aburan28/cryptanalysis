"""Genus check of the GHS function field for the n = 3 toy (ord_3(2) = 2 = n-1, the same shape as
ord_131(2) = 130) that does not use the Menezes-Teske closed formula.

F = K(x)(z_i : i in chosen), z_i^2 + z_i = x + v_i/x, v_i = sigma^i(sqrt b), K = F_8, a2 = 0.
(1) Point counts.  Degree-1 places of F over K_r = F_{8^r}:
      x in K_r^*  : 2^m places if Tr(x + v_i/x) = 0 for all chosen i, else 0 (unramified, abelian)
      x = infinity: 2^(m-1) places;  x = 0: 2^(m-d) places, d = dim span{v_i}.
    Counting walks x = u^k, 1/x = u^-k with u a primitive element (Conway modulus), in pure Python.
    For every candidate genus g <= R/2 we fit L(T) from N_1..N_g with the functional equation and test
    N_{g+1}..N_R (plus the Riemann hypothesis).  Candidates g > R/2 cannot be tested with R = 8.
(2) Kani-Rosen / Garcia-Stichtenoth: g(F) = sum of the genera of the 2^m - 1 quadratic subfields
    z^2 + z = f_c; each subfield genus is computed by Sage (simple extension, works over F_8), and the
    point counts are checked against the L-polynomial identity  q^r+1-N_r(F) = sum_c (q^r+1-N_r(F_c)).
Sanity: for b = 1 the field is E0 itself and N_r must equal #E0(F_{8^r}).
Run: sage -python toy_zeta2.py
"""
import json, time
from fractions import Fraction
from sage.all import GF, matrix, EllipticCurve, FunctionField, PolynomialRing, ComplexField

OUT = "/Volumes/SSD990/ecdlp-hardness-work/weil-descent-ghs/"
n = 3
Qb = 2 ** n
K = GF(Qb, "w")
modK = K.modulus()
R_MAX = 8


def setup(b):
    v = b.sqrt()
    conj = [v ** (2 ** i) for i in range(n)]
    vecs = [[1] + [int(c) for c in u.polynomial().padded_list(n)] for u in conj]
    chosen, rows = [], []
    for i, vec in enumerate(vecs):
        if matrix(GF(2), rows + [vec]).rank() > len(rows):
            rows.append(vec); chosen.append(i)
    d = matrix(GF(2), [vv[1:] for vv in vecs]).rank()
    return conj, chosen, d


def pattern_counts(conj, chosen, r):
    """histogram over x in K_r^* of the bit pattern (Tr(x + v_i/x))_{i in chosen}"""
    k = n * r
    Kr = GF(2 ** k, "u", modulus="conway")
    u = Kr.gen()
    modint = sum(int(c) << j for j, c in enumerate(Kr.modulus().list()))
    root = modK.change_ring(Kr).roots()[0][0]
    def emb(a):
        return sum(int(c) * root ** j for j, c in enumerate(a.polynomial().padded_list(n)))
    def tmask(a):   # y -> Tr(a*y) as parity(y & mask)
        return sum(int((a * u ** j).trace()) << j for j in range(k))
    T1 = tmask(Kr(1))
    TV = [tmask(emb(conj[i])) for i in chosen]
    top = 1 << k
    x, y = 1, 1           # x = u^e, y = u^-e
    hist = {}
    order = 2 ** k - 1
    for e in range(order):
        tx = (x & T1).bit_count() & 1
        pat = 0
        for idx, M in enumerate(TV):
            pat |= (tx ^ ((y & M).bit_count() & 1)) << idx
        hist[pat] = hist.get(pat, 0) + 1
        x <<= 1
        if x & top:
            x ^= modint
        if y & 1:
            y ^= modint
        y >>= 1
    assert x == 1 and y == 1
    return hist


def surviving_genera(Ns, q, gmax):
    Rr = len(Ns)
    S = [None] + [q ** r + 1 - Ns[r - 1] for r in range(1, Rr + 1)]
    good = []
    for g in range(0, gmax + 1):
        e = [Fraction(1)] + [Fraction(0)] * (2 * g)
        for kk in range(1, g + 1):
            e[kk] = sum((-1) ** (i - 1) * e[kk - i] * S[i] for i in range(1, kk + 1)) / kk
        for kk in range(g + 1, 2 * g + 1):
            e[kk] = Fraction(q) ** (kk - g) * e[2 * g - kk]
        if any(z.denominator != 1 for z in e):
            continue
        E = lambda kk: e[kk] if kk <= 2 * g else Fraction(0)
        ok = True
        for r in range(1, Rr + 1):
            val = sum((-1) ** (i - 1) * E(i) * S[r - i] for i in range(1, r)) + (-1) ** (r - 1) * r * E(r)
            if val != S[r]:
                ok = False; break
        if ok and g > 0:
            # exact factorisation over Z first (repeated factors are expected: sigma-conjugate
            # subfields have equal zeta functions), then RH on each distinct root
            from sage.all import ZZ
            PZ = PolynomialRing(ZZ, "T")
            Lz = PZ([(-1) ** kk * int(e[kk]) for kk in range(2 * g + 1)])
            PR = PolynomialRing(ComplexField(300), "T")
            nroots = 0
            ok = True
            for fac_, mult_ in Lz.factor():
                rts = PR(fac_).roots(multiplicities=False)
                nroots += len(rts) * mult_
                ok = ok and len(rts) == fac_.degree() and all(abs(abs(z) ** 2 * q - 1) < 1e-40 for z in rts)
            ok = ok and nroots == 2 * g
        if ok:
            good.append(g)
    return good


res = []
reps = [K(1)]
reps += [b for b in K if b not in (K(0), K(1)) and b.trace() == 0][:2]
reps += [b for b in K if b not in (K(0), K(1)) and b.trace() == 1][:2]
Fx = FunctionField(K, "x"); X = Fx.gen()
RZ = PolynomialRing(Fx, "Z"); Z = RZ.gen()
for b in reps:
    t0 = time.time()
    conj, chosen, d = setup(b)
    m = len(chosen)
    # subfields c in F2^m \ 0 : f_c = alpha x + gamma / x
    subs = []
    for c in range(1, 2 ** m):
        alpha = bin(c).count("1") & 1
        gamma = sum((conj[chosen[i]] for i in range(m) if (c >> i) & 1), K(0))
        g_c = int(Fx.extension(Z ** 2 + Z + (alpha * X + gamma / X), "zc").genus())
        subs.append((c, alpha, gamma, g_c))
    g_sum = sum(s[3] for s in subs)
    Ns, kr_ok = [], True
    for r in range(1, R_MAX + 1):
        hist = pattern_counts(conj, chosen, r)
        qr = Qb ** r
        N_F = 2 ** (m - 1) + 2 ** (m - d) + 2 ** m * hist.get(0, 0)
        Ns.append(N_F)
        # Kani-Rosen identity with subfield counts
        rhs = 0
        for (c, alpha, gamma, g_c) in subs:
            cnt = sum(v for pat, v in hist.items() if (bin(pat & c).count("1") & 1) == 0)
            N_c = 2 * cnt + (2 if alpha == 0 else 1) + (2 if gamma == 0 else 1)
            rhs += qr + 1 - N_c
        kr_ok = kr_ok and (qr + 1 - N_F == rhs)
    xp1 = (d == m)
    g_formula = 2 ** (m - 1) if xp1 else 2 ** (m - 1) - 1
    good = surviving_genera(Ns, Qb, gmax=R_MAX // 2)
    rec = {"b": str(b), "Tr_b": int(b.trace()), "m": m, "d": d, "N_r(r=1..%d)" % R_MAX: [int(z) for z in Ns],
           "genus_menezes_teske_formula": g_formula,
           "genera_<=%d_consistent_with_counts" % (R_MAX // 2): good,
           "subfield_genera_sage": [s[3] for s in subs], "kani_rosen_sum_of_subfield_genera": g_sum,
           "kani_rosen_count_identity_r1..%d" % R_MAX: kr_ok,
           "elapsed_s": round(time.time() - t0, 1)}
    if b == 1:
        E0 = EllipticCurve(K, [1, 0, 0, 0, 1])
        rec["E0_counts_match"] = all(Ns[r - 1] == E0.cardinality(extension_degree=r) for r in range(1, R_MAX + 1))
        assert rec["E0_counts_match"]
    print(json.dumps(rec, default=int), flush=True)
    res.append(rec)
    assert good == [g_formula] and g_sum == g_formula and kr_ok, rec
json.dump(res, open(OUT + "toy_zeta2.json", "w"), indent=1, default=int)
print("all toy genus checks agree with Menezes-Teske Remark 2")

"""Formula-independent genus check of the GHS function field for the n = 3 toy (ord_3(2) = 2 = n-1,
the same shape as ord_131(2) = 130), via point counting + the zeta-function functional equation.

F = K(x)(z_i : i in chosen), z_i^2 + z_i = x + v_i/x, v_i = sigma^i(sqrt b), K = F_8, a2 = 0.
Degree-1 places of F over K_r = F_{8^r}:
  x in K_r^*  : unramified; 2^m places if Tr_{K_r/F2}(x + v_i/x) = 0 for all chosen i, else none
  x = infinity: 2^(m-1) places (subfields with alpha = 0 are unramified and split, value 0)
  x = 0       : 2^(m-d) places, d = dim span{v_i}
(elementary abelian Galois group, maximal unramified subextension splits completely => D = I).
For each candidate genus g we fit L(T) from N_1..N_g with the functional equation and test all
N_1..N_R.  Exactly one g should survive; compare with Menezes-Teske Remark 2.
Sanity: for b = 1 the field is E0 itself and N_r must equal #E0(F_{8^r}).
Run: sage -python toy_zeta.py
"""
import json, time
from fractions import Fraction
from sage.all import GF, matrix, EllipticCurve

OUT = "/Volumes/SSD990/ecdlp-hardness-work/weil-descent-ghs/"
n = 3
Qb = 2 ** n
K = GF(Qb, "w")
modK = K.modulus()
R_MAX = 8


def counts_for(b):
    v = b.sqrt()
    conj = [v ** (2 ** i) for i in range(n)]
    vecs = [[1] + [int(c) for c in u.polynomial().padded_list(n)] for u in conj]
    chosen, rows = [], []
    for i, vec in enumerate(vecs):
        if matrix(GF(2), rows + [vec]).rank() > len(rows):
            rows.append(vec); chosen.append(i)
    m = len(chosen)
    d = matrix(GF(2), [vv[1:] for vv in vecs]).rank()
    Ns = []
    for r in range(1, R_MAX + 1):
        Kr = GF(2 ** (n * r), "u")
        root = modK.change_ring(Kr).roots()[0][0]      # embedding F_8 -> K_r
        def emb(u):
            return sum(int(c) * root ** k for k, c in enumerate(u.polynomial().padded_list(n)))
        vs = [emb(conj[i]) for i in chosen]
        cnt = 0
        for xx in Kr:
            if xx == 0:
                continue
            ix = 1 / xx
            trx = xx.trace()
            ok = True
            for vv in vs:
                if (trx + (vv * ix).trace()) != 0:
                    ok = False
                    break
            if ok:
                cnt += 1
        Ns.append(2 ** (m - 1) + 2 ** (m - d) + 2 ** m * cnt)
    return m, d, Ns


def surviving_genera(Ns, q, gmax):
    """candidate g for which L(T) fitted from N_1..N_g (functional equation) reproduces N_1..N_R"""
    Rr = len(Ns)
    S = [None] + [q ** r + 1 - Ns[r - 1] for r in range(1, Rr + 1)]   # power sums of the alpha_j
    good = []
    for g in range(0, gmax + 1):
        if g > Rr:
            break
        e = [Fraction(1)] + [Fraction(0)] * (2 * g)
        for k in range(1, g + 1):   # Newton: k e_k = sum_{i=1..k} (-1)^(i-1) e_{k-i} S_i
            e[k] = sum((-1) ** (i - 1) * e[k - i] * S[i] for i in range(1, k + 1)) / k
        for k in range(g + 1, 2 * g + 1):   # functional equation e_{2g-i} = q^(g-i) e_i
            e[k] = Fraction(q) ** (k - g) * e[2 * g - k]
        if any(x.denominator != 1 for x in e):
            continue
        E = lambda k: e[k] if k <= 2 * g else Fraction(0)
        Sp = [None] + [Fraction(S[i]) for i in range(1, Rr + 1)]
        ok = True
        for r in range(1, Rr + 1):
            # S_r = sum_{i=1}^{r-1} (-1)^(i-1) e_i S_{r-i} + (-1)^(r-1) r e_r
            val = sum((-1) ** (i - 1) * E(i) * Sp[r - i] for i in range(1, r)) + (-1) ** (r - 1) * r * E(r)
            if val != S[r]:
                ok = False
                break
        if ok and g > 0:
            # Riemann hypothesis filter: L(T) = sum (-1)^k e_k T^k must have all roots of |T| = q^(-1/2)
            from sage.all import PolynomialRing, CC, ComplexField
            PR = PolynomialRing(ComplexField(200), 'T')
            Lp = PR([(-1) ** k * int(e[k]) for k in range(2 * g + 1)])
            rts = Lp.roots(multiplicities=False)
            ok = len(rts) == 2 * g and all(abs(abs(z) ** 2 * q - 1) < 1e-20 for z in rts)
        if ok:
            good.append(g)
    return good


res = []
reps = [K(1)]
reps += [b for b in K if b not in (K(0), K(1)) and b.trace() == 0][:2]
reps += [b for b in K if b not in (K(0), K(1)) and b.trace() == 1][:2]
for b in reps:
    t0 = time.time()
    m, d, Ns = counts_for(b)
    xp1 = (d == m)            # (x+1) | Ord_b  <=>  (1,0) not in W  <=>  d = m
    g_formula = 2 ** (m - 1) if xp1 else 2 ** (m - 1) - 1
    good = surviving_genera(Ns, Qb, gmax=(R_MAX - 1))
    rec = {"b": str(b), "Tr_b": int(b.trace()), "m": m, "d": d, "N_r(r=1..%d)" % R_MAX: [int(z) for z in Ns],
           "genus_formula": g_formula, "genera_consistent_with_counts": good,
           "elapsed_s": round(time.time() - t0, 1)}
    if b == 1:
        E0 = EllipticCurve(K, [1, 0, 0, 0, 1])
        rec["E0_counts_match"] = all(Ns[r - 1] == E0.cardinality(extension_degree=r) for r in range(1, R_MAX + 1))
        assert rec["E0_counts_match"]
    print(json.dumps(rec, default=int), flush=True)
    res.append(rec)
    assert good == [g_formula], rec
json.dump(res, open(OUT + "toy_zeta.json", "w"), indent=1, default=int)
print("all toy zeta genus checks agree with Menezes-Teske Remark 2")

"""Independent check of the GHS genus formula on toy fields by building the GHS function field.

For E: y^2+xy = x^3 + b over K = F_{2^n} (a2 = 0), y = x z gives z^2 + z = x + b/x^2 ~ x + sqrt(b)/x
(mod Artin-Schreier equivalence).  The GHS field is F = K(x)(z_0,...,z_{n-1}) with
z_i^2 + z_i = x + sigma^i(sqrt b)/x.  We adjoin z_i for a maximal set of indices whose vectors
(1, sigma^i sqrt b) are F2-independent (the others are then rational over the compositum), convert
the tower to a simple extension of K(x) with Sage's simple_model(), and let Sage compute the genus
(maximal orders / different; independent of any GHS formula).  Compare with Menezes-Teske Remark 2:
   m = rank, g = 2^(m-1) if (x+1) | Ord_b else 2^(m-1) - 1.
Run: sage -python toy_genus.py [max_degree]
"""
import sys, json, time
from sage.all import GF, FunctionField, PolynomialRing, matrix, Mod

OUT = "/Volumes/SSD990/ecdlp-hardness-work/weil-descent-ghs/"
MAXDEG = int(sys.argv[1]) if len(sys.argv) > 1 else 16
results = []


def run_case(n, b, K):
    v = b.sqrt()
    conj = [v ** (2 ** i) for i in range(n)]
    vecs = [[1] + [int(c) for c in u.polynomial().padded_list(n)] for u in conj]
    # greedy independent subset
    chosen, rows = [], []
    for i, vec in enumerate(vecs):
        if matrix(GF(2), rows + [vec]).rank() > len(rows):
            rows.append(vec)
            chosen.append(i)
    m = len(chosen)
    # Ord_b via Krylov over b
    Rx = PolynomialRing(GF(2), "X"); X = Rx.gen()
    kr, ordb = [], None
    w = b
    for i in range(n + 1):
        kr.append([int(c) for c in w.polynomial().padded_list(n)])
        M = matrix(GF(2), kr)
        if M.rank() < len(kr):
            ker = M.left_kernel().basis()[0]
            ordb = sum((X ** j for j in range(len(kr)) if ker[j] == 1), Rx(0))
            break
        w = w ** 2
    xp1 = (ordb % (X + 1) == 0)
    m_formula = ordb.degree() if xp1 else ordb.degree() + 1
    g_formula = 2 ** (m - 1) if xp1 else 2 ** (m - 1) - 1
    if 2 ** m > MAXDEG:
        return {"n": n, "b": str(b), "m": m, "skipped_degree": 2 ** m}
    t0 = time.time()
    F = FunctionField(K, "x"); x = F.gen()
    L = F
    for k, i in enumerate(chosen):
        R = PolynomialRing(L, "Z%d" % k); Z = R.gen()
        L = L.extension(Z ** 2 + Z + (x + conj[i] / x), "z%d" % i)
    S = L.simple_model()[0] if L is not F and L.base_field() is not F else L
    g_sage = int(S.genus())
    rec = {"n": n, "b": str(b), "Tr_b": int(b.trace()), "Ord_b": str(ordb), "m_rank": m,
           "m_formula": m_formula, "degree_over_Kx": 2 ** m, "genus_sage": g_sage,
           "genus_formula": g_formula, "match": g_sage == g_formula and m == m_formula,
           "elapsed_s": round(time.time() - t0, 1)}
    return rec


for n in [3, 5, 7]:
    K = GF(2 ** n, "w")
    picks = {}
    for b in K:
        if b == 0:
            continue
        v = b.sqrt()
        # classify by (Tr b, Ord_b degree)
        key = None
        picks.setdefault("b=1", K(1))
    # pick representatives: b=1, one Tr=0 non-F2, one Tr=1 non-F2, and for n=7 small-m ones
    reps = [K(1)]
    tr0 = [b for b in K if b not in (K(0), K(1)) and b.trace() == 0]
    tr1 = [b for b in K if b not in (K(0), K(1)) and b.trace() == 1]
    reps += tr0[:1] + tr1[:1]
    if n == 7:
        # also b with small Ord (deg 3 or 4) -> m = 4
        for b in K:
            if b in (K(0), K(1)):
                continue
            if b + b ** 2 + b ** 8 == 0 or b ** 2 + b ** 4 + b ** 8 + b ** 16 == 0 or \
               (b ** 2 + b ** 4 + b ** 8 + b ** 16) == 0:
                pass
        small = []
        for b in K:
            if b in (K(0), K(1)):
                continue
            conj = [b.sqrt() ** (2 ** i) for i in range(n)]
            vecs = [[1] + [int(c) for c in u.polynomial().padded_list(n)] for u in conj]
            if matrix(GF(2), vecs).rank() == 4:
                small.append(b)
        tr0s = [b for b in small if b.trace() == 0][:1]
        tr1s = [b for b in small if b.trace() == 1][:1]
        reps += tr0s + tr1s
    for b in reps:
        rec = run_case(n, b, K)
        print(json.dumps(rec, default=int), flush=True)
        results.append(rec)
json.dump(results, open(OUT + "toy_genus_%d.json" % MAXDEG, "w"), indent=1, default=int)
bad = [r for r in results if "match" in r and not r["match"]]
print("cases computed:", sum(1 for r in results if "match" in r), "mismatches:", len(bad))
assert not bad

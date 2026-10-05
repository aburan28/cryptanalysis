"""Exhaustive toy analogues: for small prime n, enumerate EVERY b in F_{2^n}^*, compute the GHS
magic number m(b) (rank of [1 | coords(sigma^i sqrt b)]), Tr(b), and the group order of
y^2+xy=x^3+b.  Checks, for the isogeny class of the Koblitz curve y^2+xy=x^3+1 (same order):
  * every class member has Tr(b) = 1 whenever #E = 4*odd (the 8 !| #E argument),
  * if ord_n(2) = n-1 then m(b) in {1, n} and m = 1 iff b = 1,
  * negative control n = 7 (ord_7(2) = 3): small m (= 4) does occur, so the code can see it.
Run: sage -python toy_exhaustive.py
"""
import json, time
from collections import Counter
from sage.all import GF, EllipticCurve, Mod, matrix

OUT = "/Volumes/SSD990/ecdlp-hardness-work/weil-descent-ghs/"
res = {}
for n in [3, 5, 7, 11, 13]:
    t0 = time.time()
    K = GF(2 ** n, "w")
    ordn = Mod(2, n).multiplicative_order()

    def coords(u):
        return [int(c) for c in u.polynomial().padded_list(n)]

    def m_of(b):
        v = b.sqrt()
        rows = []
        w = v
        for i in range(n):
            rows.append([1] + coords(w))
            w = w ** 2
        return matrix(GF(2), rows).rank()

    E0 = EllipticCurve(K, [1, 0, 0, 0, 1])
    c0 = E0.cardinality()
    rows = []
    for b in K:
        if b == 0:
            continue
        m = m_of(b)
        E = EllipticCurve(K, [1, 0, 0, 0, b])
        c = E.cardinality()
        rows.append((b, m, int(b.trace()), int(c)))
    cls = [r for r in rows if r[3] == c0]
    mdist_all = Counter(r[1] for r in rows)
    mdist_cls = Counter(r[1] for r in cls)
    trdist_cls = Counter(r[2] for r in cls)
    odd_part = c0
    v2 = 0
    while odd_part % 2 == 0:
        odd_part //= 2
        v2 += 1
    # check: for every b (all curves with a2=0), 8 | #E  <=>  Tr(b) = 0
    eight_iff_tr0 = all(((r[3] % 8 == 0) == (r[2] == 0)) for r in rows)
    m1 = [str(r[0]) for r in rows if r[1] == 1]
    res[n] = {
        "ord_n(2)": int(ordn),
        "#E0": int(c0), "v2(#E0)": v2,
        "class_size_a2=0_models": len(cls),
        "m_distribution_all_b": {str(k): v for k, v in sorted(mdist_all.items())},
        "m_distribution_isogeny_class": {str(k): v for k, v in sorted(mdist_cls.items())},
        "trace_b_distribution_isogeny_class": {str(k): v for k, v in sorted(trdist_cls.items())},
        "b_with_m_equal_1": m1,
        "for_all_b: 8|#E iff Tr(b)=0": eight_iff_tr0,
        "elapsed_s": round(time.time() - t0, 2),
    }
    print(n, json.dumps(res[n]))
    if ordn == n - 1:
        assert set(mdist_all) <= {1, n} and m1 == ["1"]
    if v2 == 2:
        assert set(trdist_cls) == {1}
    assert eight_iff_tr0
json.dump(res, open(OUT + "toy_exhaustive.json", "w"), indent=1)

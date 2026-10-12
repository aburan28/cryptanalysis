"""Why is E0's toy (n = 19) decomposition yield at l = 5 below the random-set baseline?
Hypothesis: b = 1 puts the order-4 points (x = b^(1/4) = 1) into F_V (1 is in every V_l), so F
contains 3 of the 4 points of E[4] (T2 = (0,1) and +-T4), which creates extra coincidences among
sums.  Floor curves have x(T4) = b^(1/4), generically not in V.  Test: E0's |S_m|/#E with F_V
and with F_V minus {+-T4}, each against 20 random symmetric sets (same size, containing T2).
Also one floor curve (first of the sample) with and without its own T4 added to F_V.
Run: export TMPDIR=/Volumes/SSD990/ecdlp-hardness-work/tmp; sage -python e0_torsion_check.py"""
import json, math
import numpy as np
from sage.all import GF, PolynomialRing, EllipticCurve
OUT = "/Volumes/SSD990/ecdlp-hardness-work/index-calculus/toy/"
n = 19
R = PolynomialRing(GF(2), "z"); zz = R.gen()
K = GF(2 ** n, "z", modulus=zz ** 19 + zz ** 5 + zz ** 2 + zz + 1)
z = K.gen()
toy = json.load(open(OUT + "relprob_toy.json"))
rng = np.random.default_rng(3)


def halftrace(c):
    h, u = c, c
    for _ in range((n - 1) // 2):
        u = u ** 4
        h += u
    return h


def lift(E, b, x):
    if x == 0:
        return [E(0, b.sqrt())]
    c = x + b / (x * x)
    if c.trace() != 0:
        return []
    y = x * halftrace(c)
    return [E(x, y), E(x, y + x)]


def sumset_sizes(logs, M, mmax=4):
    base = np.zeros(M, dtype=bool); base[np.asarray(logs) % M] = True
    cur, out = base, {}
    for m in range(2, mmax + 1):
        nxt = np.zeros(M, dtype=bool)
        for f in np.flatnonzero(base):
            nxt |= np.roll(cur, int(f))
        out[m] = int(nxt.sum()); cur = nxt
    return out


def randsym(size, M):
    s = {M // 2}
    while len(s) < size:
        a = int(rng.integers(1, M))
        if a == M // 2 or a in s:
            continue
        s.add(a); s.add((-a) % M)
    return sorted(s)


res = {}
flab = sorted(k for k in toy["per_curve"] if k.startswith("F"))[0]
for lab, b in [("E0", K(1)), (flab, K.from_integer(toy["curves"][flab]["b_int"]))]:
    E = EllipticCurve(K, [1, 0, 0, 0, b])
    M = int(E.cardinality())
    while True:
        G = E.random_point()
        if G.order() == M:
            break
    x4 = b.sqrt().sqrt()
    T4 = lift(E, b, x4)
    assert all((4 * P).is_zero() and not (2 * P).is_zero() for P in T4)
    for l in (5, 6):
        V = [K(sum(((c >> i) & 1) * z ** i for i in range(l))) for c in range(1 << l)]
        F = [P for x in V for P in lift(E, b, x)]
        variants = {"F_V": F}
        if lab == "E0":
            variants["F_V_minus_T4"] = [P for P in F if P not in T4]
        else:
            variants["F_V_plus_T4"] = F + [P for P in T4 if P not in F]
        for vn, FF in variants.items():
            logs = [int(P.log(G)) for P in FF]
            s = sumset_sizes(logs, M)
            base = [sumset_sizes(randsym(len(logs), M), M) for _ in range(20)]
            res["%s_l%d_%s" % (lab, l, vn)] = {
                "size": len(FF), "contains_T4": any(P in FF for P in T4),
                "ratio_to_mean_randset": {m: s[m] / float(np.mean([bb[m] for bb in base])) for m in (2, 3, 4)},
                "randset_sd_rel": {m: float(np.std([bb[m] for bb in base]) / np.mean([bb[m] for bb in base])) for m in (2, 3, 4)}}
            print(lab, l, vn, json.dumps(res["%s_l%d_%s" % (lab, l, vn)]), flush=True)
json.dump(res, open(OUT + "e0_torsion_check.json", "w"), indent=1)

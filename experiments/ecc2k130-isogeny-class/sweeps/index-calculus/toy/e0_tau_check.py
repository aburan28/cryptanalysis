"""Second hypothesis for E0's toy (n = 19) yield dip at l = 5: tau-coincidences.  On E0 (b = 1),
tau(x, y) = (x^2, y^2) is an endomorphism with tau^2 + tau + 2 = 0, so whenever P, tau P, tau^2 P
all lie in F_V the sums tau^2 P + tau P and (-P) + (-P) coincide, etc.  The canonical V = span(1..z^(l-1))
satisfies V ∩ V^2 ⊇ span(1, z^2, z^4, ...), so it contains many x with x^2 in V; a random subspace
does not.  Test: E0 yield ratio (vs 20 random symmetric sets) on the canonical V and on 6 random
l-dim subspaces, with the number of P in F_V having tau(P) in F_V.
Run: export TMPDIR=/Volumes/SSD990/ecdlp-hardness-work/tmp; sage -python e0_tau_check.py"""
import json, random
import numpy as np
from sage.all import GF, PolynomialRing, EllipticCurve
OUT = "/Volumes/SSD990/ecdlp-hardness-work/index-calculus/toy/"
n = 19
R = PolynomialRing(GF(2), "z"); zz = R.gen()
K = GF(2 ** n, "z", modulus=zz ** 19 + zz ** 5 + zz ** 2 + zz + 1)
z = K.gen()
rng = np.random.default_rng(4)


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


b = K(1)
E = EllipticCurve(K, [1, 0, 0, 0, b])
M = int(E.cardinality())
while True:
    G = E.random_point()
    if G.order() == M:
        break
res = {}
pr = random.Random(11)
for l in (5, 6):
    spaces = {"canon": [z ** i for i in range(l)]}
    for r in range(6):
        while True:
            bas = [K.from_integer(pr.randrange(1, 2 ** n)) for _ in range(l)]
            if True:
                V = set()
                for c in range(1 << l):
                    V.add(sum((bas[i] for i in range(l) if (c >> i) & 1), K(0)).to_integer())
                if len(V) == 1 << l:
                    break
        spaces["rand%d" % r] = bas
    for name, bas in spaces.items():
        V = [sum((bas[i] for i in range(l) if (c >> i) & 1), K(0)) for c in range(1 << l)]
        Vs = set(v.to_integer() for v in V)
        F = [P for x in V for P in lift(E, b, x)]
        ntau = sum(1 for P in F if (not P.is_zero()) and (P[0] ** 2).to_integer() in Vs)
        logs = [int(P.log(G)) for P in F]
        s = sumset_sizes(logs, M)
        base = [sumset_sizes(randsym(len(logs), M), M) for _ in range(20)]
        res["l%d_%s" % (l, name)] = {"size": len(F), "points_with_tauP_in_F": ntau,
                                    "ratio": {m: s[m] / float(np.mean([bb[m] for bb in base])) for m in (2, 3, 4)}}
        print(l, name, json.dumps(res["l%d_%s" % (l, name)]), flush=True)
json.dump(res, open(OUT + "e0_tau_check.json", "w"), indent=1)

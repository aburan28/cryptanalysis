"""Exact relation yield of factor-base choices on y^2+xy=x^3+1 over F_2^n.

yield = |F+F+F| / #E, estimated on random targets with the exact oracle.
Choices: std (span 1..z^(l-1)), random l-dim subspaces, and an l-dim subspace
inside ker Tr (all factor-base points in 2E; only targets with Tr(x_R)=0 can
decompose, and odd-trace targets are rejected without solving).
"""

import random
import sys

from gf2n import Curve, GF2n


def span(basis):
    out = [0]
    for b in basis:
        out += [x ^ b for x in out]
    return out


def fb_points(E, xs):
    pts = []
    for x in xs:
        P = E.lift_x(x)
        if P is not None:
            pts += [P, E.neg(P)] if P.y != (P.x ^ P.y) else [P]
    return pts


def yield_of(E, pts, rng, trials):
    pair = set()
    for i, P in enumerate(pts):
        for Q in pts[i:]:
            S = E.add(P, Q)
            pair.add((S.x, S.y, S.inf))
    hits = 0
    for _ in range(trials):
        R = E.random_point(rng)
        for P in pts:
            T = E.add(R, E.neg(P))
            if (T.x, T.y, T.inf) in pair:
                hits += 1
                break
    return hits / trials


# usage: python3 fb_yield.py N L TRIALS
n, l, trials = int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3])
F = GF2n(n)
E = Curve(F, 1)
rng = random.Random(5)
std = span([1 << j for j in range(l)])
res = {}
res["std"] = std
for k in range(3):
    while True:
        basis = [F.random(rng) for _ in range(l)]
        V = span(basis)
        if len(set(V)) == 1 << l:
            break
    res[f"rand{k}"] = V
# l-dim subspace of ker Tr: basis vectors with trace 0
basis = []
while True:
    cand = [F.random(rng) for _ in range(l)]
    cand = [c for c in cand if F.trace(c) == 0]
    if len(cand) == l and len(set(span(cand))) == 1 << l:
        basis = cand
        break
res["kerTr"] = span(basis)
for name, V in res.items():
    pts = fb_points(E, V)
    y = yield_of(E, pts, random.Random(99), trials)
    lift = sum(1 for x in V if E.lift_x(x) is not None) / len(V)
    print(
        f"n={n} l={l} {name:6s}: liftable {lift:.3f}  |F|={len(pts)}  yield {y:.4f}  theory {2 ** (3 * l) / (6 * 2**n):.4f}"
    )

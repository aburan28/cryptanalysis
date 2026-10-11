"""Semaev summation polynomials S_3 .. S_6 for E_b : y^2 + xy = x^3 + b
over F_2, with b kept as a variable.

A polynomial over F_2 is a set of monomials; a monomial is a tuple of
exponents over the variables (x1, ..., x6, b, X), X being the scratch
variable the resultants eliminate.  S_{m+1} is the
resultant Res_X(S_3(x1, x2, X), S_m(x3, ..., x_{m+1}, X)), computed from
the Sylvester matrix by Laplace expansion.  For this curve

    S_3(x1, x2, x3) = x1^2 x2^2 + x1^2 x3^2 + x2^2 x3^2 + x1 x2 x3 + b,

and S_3 does not involve a2, so neither do the others.  `check()` verifies
S_{m+1}(x(P_1), ..., x(P_m), x(P_1 + ... + P_m)) = 0 on random points.
"""

from __future__ import annotations

import pickle
import random
from functools import cache
from pathlib import Path

from gf2n import Curve, GF2n

NV = 8  # x1..x6, b, X
NX = 6
B, X = 6, 7
Poly = frozenset  # of exponent tuples


def var(i: int) -> Poly:
    e = [0] * NV
    e[i] = 1
    return frozenset([tuple(e)])


ONE: Poly = frozenset([(0,) * NV])
ZERO: Poly = frozenset()


def add(p: Poly, q: Poly) -> Poly:
    return p ^ q


def mul(p: Poly, q: Poly) -> Poly:
    out: set[tuple[int, ...]] = set()
    for a in p:
        for b in q:
            m = tuple(x + y for x, y in zip(a, b))
            if m in out:
                out.remove(m)
            else:
                out.add(m)
    return frozenset(out)


def power(p: Poly, e: int) -> Poly:
    r = ONE
    for _ in range(e):
        r = mul(r, p)
    return r


def rename(p: Poly, perm: list[int]) -> Poly:
    """Send variable i to variable perm[i]."""
    out: set[tuple[int, ...]] = set()
    for a in p:
        e = [0] * NV
        for i, ai in enumerate(a):
            e[perm[i]] += ai
        m = tuple(e)
        if m in out:
            out.remove(m)
        else:
            out.add(m)
    return frozenset(out)


def coeffs_in(p: Poly, i: int) -> list[Poly]:
    """p as a polynomial in variable i: list of coefficients, index = degree."""
    d = max((a[i] for a in p), default=-1)
    cs: list[set[tuple[int, ...]]] = [set() for _ in range(d + 1)]
    for a in p:
        e = list(a)
        k = e[i]
        e[i] = 0
        cs[k].add(tuple(e))
    return [frozenset(c) for c in cs]


def resultant(f: Poly, g: Poly, i: int) -> Poly:
    """Res_{x_i}(f, g) over F_2 via the Sylvester matrix."""
    fc = coeffs_in(f, i)
    gc = coeffs_in(g, i)
    p, q = len(fc) - 1, len(gc) - 1
    size = p + q
    rows: list[list[Poly]] = []
    for r in range(q):
        row = [ZERO] * size
        for k, c in enumerate(reversed(fc)):
            row[r + k] = c
        rows.append(row)
    for r in range(p):
        row = [ZERO] * size
        for k, c in enumerate(reversed(gc)):
            row[r + k] = c
        rows.append(row)

    @cache
    def det(r: int, cols: int) -> Poly:
        if r == size:
            return ONE
        acc: Poly = ZERO
        for c in range(size):
            if not (cols >> c) & 1 and rows[r][c]:
                acc = add(acc, mul(rows[r][c], det(r + 1, cols | (1 << c))))
        return acc

    return det(0, 0)


def S3() -> Poly:
    x1, x2, x3, b = var(0), var(1), var(2), var(B)
    t = add(add(mul(x1, x2), mul(x1, x3)), mul(x2, x3))
    return add(add(mul(t, t), mul(mul(x1, x2), x3)), b)


def summation_polynomials(upto: int = 5) -> dict[int, Poly]:
    """{k: S_k} for k = 3..upto, S_k in variables x1..x_k and b."""
    S = {3: S3()}
    assert upto <= NX
    for k in range(4, upto + 1):
        # S_3(x1, x2, X) and S_{k-1}(x3, ..., x_k, X)
        f = rename(S[3], [0, 1, X, 3, 4, 5, B, X])
        perm = list(range(NV))
        for j in range(k - 2):
            perm[j] = j + 2
        perm[k - 2] = X
        g = rename(S[k - 1], perm)
        S[k] = resultant(f, g, X)
    return S


CACHE = Path(__file__).with_name("sumpoly_cache.pkl")


def load(upto: int = 6) -> dict[int, Poly]:
    if CACHE.exists():
        with CACHE.open("rb") as fh:
            S = pickle.load(fh)
        if max(S) >= upto:
            return S
    S = summation_polynomials(upto)
    with CACHE.open("wb") as fh:
        pickle.dump(S, fh)
    return S


def evaluate(p: Poly, F: GF2n, xs: list[int], b: int) -> int:
    vals = list(xs) + [0] * (NX - len(xs)) + [b, 0]
    powers = [{0: 1} for _ in vals]
    acc = 0
    for mono in p:
        t = 1
        for i, e in enumerate(mono):
            if e:
                if e not in powers[i]:
                    powers[i][e] = F.pow(vals[i], e)
                t = F.mul(t, powers[i][e])
        acc ^= t
    return acc


def check(n: int = 17, trials: int = 20, seed: int = 1, upto: int = 6) -> None:
    rng = random.Random(seed)
    F = GF2n(n)
    S = load(upto)
    for k, p in S.items():
        degs = [max(a[i] for a in p) for i in range(k)]
        assert degs == [2 ** (k - 2)] * k, (k, degs)
        for b in (1, F.random(rng)):
            E = Curve(F, b)
            for _ in range(trials):
                pts = [E.random_point(rng) for _ in range(k - 1)]
                R = E.sum(pts)
                if R.inf:
                    continue
                xs = [P.x for P in pts] + [R.x]
                assert evaluate(p, F, xs, b) == 0, (k, b)
                xs[-1] = E.random_point(rng).x
                assert evaluate(p, F, xs, b) != 0 or rng.random() < 0.01
    print("summation polynomials verified:", {k: len(p) for k, p in S.items()})


if __name__ == "__main__":
    check()

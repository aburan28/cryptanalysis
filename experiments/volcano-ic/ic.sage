# End-to-end index calculus on one binary curve y^2 + xy = x^3 + a x^2 + b.
#
# Factor base: rational points with x in V = span{1, z, ..., z^(k-1)} (the
# polynomial coordinate subspace), taken up to sign. Relations come from
# decomposing R = alpha*P + beta*Q as +-P1 +- P2 using the third summation
# polynomial S3(x1, x2, xR) = (x1 x2)^2 + xR^2 (x1^2 + x2^2) + xR x1 x2 + b,
# Weil-descended to n Boolean equations in 2k variables and solved with a
# PolyBoRi Groebner basis. With 2k - 2 < n, x1 x2 needs no reduction and
# squaring is linear, so each target's system is a linear combination of
# polynomials precomputed once per field.
#
# Logs live in the prime subgroup of order p = N / h. Factor-base points are
# multiplied by the cofactor h, so a relation reads
#   h*alpha + h*beta*s = s1 L(x1) + s2 L(x2)   (mod p),  L(x) = log_P(h P_x).
# The b coefficient only enters as a constant, so the top-degree part of every
# system (and hence its formal degree of regularity) depends on the target,
# never on the curve.

import json
import sys
import time
from sage.rings.polynomial.pbori.pbori import BooleanPolynomialRing


class Field:
    def __init__(self, n, modulus, k):
        R = PolynomialRing(GF(2), 'Z')
        self.F = GF(2 ** n, 'z', modulus=R(modulus))
        self.z = self.F.gen()
        self.n, self.k = n, k
        self.B = BooleanPolynomialRing(2 * k, ['u%d' % i for i in range(k)] + ['w%d' % i for i in range(k)])
        g = self.B.gens()
        u, w = g[:k], g[k:]
        # Coordinates (in 1, z, ..., z^(n-1)) of x1 x2: plain convolution.
        conv = [self.B(0)] * n
        for i in range(k):
            for j in range(k):
                conv[i + j] += u[i] * w[j]
        self.C = conv                                          # x1 x2
        self.A = self.linear(self.sqMatrix(), conv)            # (x1 x2)^2
        sq = self.sqMatrix()
        x1 = [u[i] if i < k else self.B(0) for i in range(n)]
        x2 = [w[i] if i < k else self.B(0) for i in range(n)]
        self.S = [a + c for a, c in zip(self.linear(sq, x1), self.linear(sq, x2))]  # x1^2 + x2^2
        self.u, self.w = u, w

    def vec(self, e):
        v = e.polynomial().list()
        return v + [0] * (self.n - len(v))

    def mulMatrix(self, c):
        cols = [self.vec(c * self.z ** i) for i in range(self.n)]
        return matrix(GF(2), cols).transpose()

    def sqMatrix(self):
        cols = [self.vec((self.z ** i) ** 2) for i in range(self.n)]
        return matrix(GF(2), cols).transpose()

    def linear(self, M, polys):
        out = []
        for r in range(self.n):
            s = self.B(0)
            for c in M.nonzero_positions_in_row(r):
                s += polys[c]
            out.append(s)
        return out

    def system(self, xR, b):
        # (x1x2)^2 + xR^2 (x1^2+x2^2) + xR (x1x2) + b = 0, coordinatewise.
        t1 = self.linear(self.mulMatrix(xR ** 2), self.S)
        t2 = self.linear(self.mulMatrix(xR), self.C)
        bv = self.vec(b)
        return [self.A[j] + t1[j] + t2[j] + bv[j] for j in range(self.n)]

    def fromBits(self, bits):
        return sum(self.z ** i for i in range(self.k) if bits[i])


def topDegreeDreg(fld, polys):
    """Formal degree of regularity: first degree where the Hilbert function of
    the ideal of top-degree parts plus x_i^2 vanishes (Bardet-style)."""
    P = PolynomialRing(GF(2), 2 * fld.k, 'v')
    v = P.gens()
    gens = [x ** 2 for x in v]
    for f in polys:
        d = f.deg()
        if d <= 0:
            continue
        top = sum(P.prod(v[i] for i in m.iterindex()) for m in f.terms() if m.deg() == d)
        if top != 0:
            gens.append(top)
    # The quotient is finite dimensional (x_i^2 present), so the Hilbert series
    # is a polynomial; its degree + 1 is the first vanishing degree.
    ser = P.ideal(gens).hilbert_series()
    return ZZ(ser.numerator().degree() - ser.denominator().degree() + 1)


def halfTrace(c, n):
    t, s = c, c
    for _ in range((n - 1) // 2):
        t = t ** 4
        s += t
    return s


class Curve:
    def __init__(self, fld, a, b, N, h):
        self.fld, self.a, self.b = fld, a, b
        F = fld.F
        self.E = EllipticCurve(F, [1, a, 0, 0, b])
        self.N, self.h, self.p = N, h, N // h
        # Factor base: one point per x in V with a rational lift. For x != 0,
        # y = x w with w^2 + w = x + a + b/x^2, solvable iff the trace is 0;
        # n is odd, so the half-trace gives w.
        self.fb = {}
        for c in range(1, 2 ** fld.k):
            x = fld.fromBits([(c >> i) & 1 for i in range(fld.k)])
            rhs = x + a + b / x ** 2
            if rhs.trace() != 0:
                continue
            w = halfTrace(rhs, fld.n)
            self.fb[x] = self.E(x, x * w)
        self.xs = list(self.fb)
        self.col = {x: i for i, x in enumerate(self.xs)}


def solveRelation(cur, R, stats):
    fld = cur.fld
    t0 = time.perf_counter()
    polys = [f for f in fld.system(R[0], cur.b) if f != 0]
    t1 = time.perf_counter()
    c1 = time.process_time()
    I = ideal(polys)
    gb = I.groebner_basis()
    sols = I.variety() if gb != [1] else []
    t2 = time.perf_counter()
    stats['build_s'] += t1 - t0
    stats['gb_s'] += t2 - t1
    # CPU time is insensitive to other load on the machine; wall time is not.
    stats['gb_cpu_s'] = stats.get('gb_cpu_s', 0.0) + time.process_time() - c1
    stats['gb_calls'] += 1
    if not sols:
        return None
    stats['nonempty'] += 1
    for sol in sols:
        x1 = fld.fromBits([sol[g] for g in fld.u])
        x2 = fld.fromBits([sol[g] for g in fld.w])
        if x1 not in cur.fb or x2 not in cur.fb:
            stats['spurious'] += 1
            continue
        P1, P2 = cur.fb[x1], cur.fb[x2]
        for s1 in (1, -1):
            for s2 in (1, -1):
                if s1 * P1 + s2 * P2 == R:
                    return (x1, s1, x2, s2)
        stats['spurious'] += 1
    return None


def solveDlp(cur, P, Q, rng, extra=10, maxAttempts=None):
    """Collect relations until the left kernel yields log_P(Q); return stats."""
    p, h = cur.p, cur.h
    ncol = len(cur.xs)
    stats = {'build_s': 0.0, 'gb_s': 0.0, 'gb_calls': 0, 'nonempty': 0, 'spurious': 0}
    rows, rhs = [], []
    t0 = time.perf_counter()
    c0 = time.process_time()
    target = ncol + extra
    attempts = 0
    Fp = GF(p)
    while len(rows) < target:
        if maxAttempts and attempts >= maxAttempts:
            break
        attempts += 1
        al, be = rng.randrange(1, p), rng.randrange(1, p)
        R = al * P + be * Q
        if R.is_zero():
            continue
        rel = solveRelation(cur, R, stats)
        if rel is None:
            continue
        x1, s1, x2, s2 = rel
        row = {}
        row[cur.col[x1]] = row.get(cur.col[x1], 0) + s1
        row[cur.col[x2]] = row.get(cur.col[x2], 0) + s2
        rows.append(row)
        rhs.append((h * al % p, h * be % p))
    t1 = time.perf_counter()
    # Left kernel of the relation matrix restricted to the columns used.
    used = sorted({c for r in rows for c in r})
    idx = {c: i for i, c in enumerate(used)}
    M = matrix(Fp, len(rows), len(used), sparse=True)
    for i, r in enumerate(rows):
        for c, v in r.items():
            M[i, idx[c]] += v
    K = M.left_kernel().basis()
    s = None
    for v in K:
        A = sum(Fp(v[i]) * rhs[i][0] for i in range(len(rows)))
        Bc = sum(Fp(v[i]) * rhs[i][1] for i in range(len(rows)))
        if Bc != 0:
            s = ZZ(-A / Bc)
            break
    t2 = time.perf_counter()
    stats['total_cpu_s'] = time.process_time() - c0
    ok = s is not None and s * P == Q
    stats.update({'attempts': attempts, 'relations': len(rows), 'fb_size': ncol,
                  'columns_used': len(used), 'kernel_dim': len(K),
                  'relation_s': t1 - t0, 'linalg_s': t2 - t1, 'total_s': t2 - t0,
                  'recovered': ok, 'log': int(s) if s is not None else None})
    return stats

# Index calculus on the Koblitz curve E0 with a tau-invariant factor base.
#
# tau(x, y) = (x^2, y^2) is an endomorphism of E0 (a, b in F_2) and acts on
# the order-p subgroup as multiplication by lambda, a root of
# t^2 - mu t + 2 (mu = -1 for a = 0). A factor base closed under tau
# therefore needs one unknown per Frobenius orbit:
#   L(tau^e P) = lambda^e L(P).
#
# Over F_2^19 the only squaring-stable subspaces are trivial (2 is primitive
# mod 19), and the usual weight-bounded normal-basis base leaves Groebner
# bases hopeless (38 variables plus degree-4 weight constraints). Instead
# we take the orbit closure of a small polynomial subspace:
#   F = { tau^j P : x(P) in V' = span{1, z, ..., z^(k'-1)} }.
# Squaring is F_2-linear, so x(tau^j P2) = sigma^j(x2) is linear in the bits
# of x2, and R = P1 +- tau^j P2 with P1, P2 in V' is a quadratic system in 2k'
# variables, one per shift j. A target is tried against j = 0 .. n-1 until
# one shift yields a relation.

import time
import random
from sage.rings.polynomial.pbori.pbori import BooleanPolynomialRing


class TauField:
    def __init__(self, n, modulus, k):
        R = PolynomialRing(GF(2), 'Z')
        self.F = GF(2 ** n, 'z', modulus=R(modulus))
        self.z = self.F.gen()
        self.n, self.k = n, k
        self.B = BooleanPolynomialRing(2 * k, ['u%d' % i for i in range(k)] + ['w%d' % i for i in range(k)])
        g = self.B.gens()
        self.u, self.w = g[:k], g[k:]
        z = self.z
        sq = self.matrix(lambda i: (z ** i) ** 2)
        self.pieces = []
        for j in range(n):
            # x2 = sigma^j(sum w_l z^l): coordinates are linear in w.
            x2 = [self.B(0)] * n
            for l in range(k):
                for c, bit in enumerate(self.vec((z ** l) ** (2 ** j))):
                    if bit:
                        x2[c] += self.w[l]
            x1 = [self.u[i] if i < k else self.B(0) for i in range(n)]
            prod = [self.B(0)] * n
            for i in range(k):
                for l in range(k):
                    for c, bit in enumerate(self.vec(z ** i * (z ** l) ** (2 ** j))):
                        if bit:
                            prod[c] += self.u[i] * self.w[l]
            A = self.linear(sq, prod)                                   # (x1 x2)^2
            S = [a + b for a, b in zip(self.linear(sq, x1), self.linear(sq, x2))]  # x1^2 + x2^2
            self.pieces.append((A, S, prod))

    def vec(self, e):
        v = e.polynomial().list()
        return v + [0] * (self.n - len(v))

    def matrix(self, f):
        return matrix(GF(2), [self.vec(f(i)) for i in range(self.n)]).transpose()

    def linear(self, M, polys):
        return [sum((polys[c] for c in M.nonzero_positions_in_row(r)), self.B(0)) for r in range(self.n)]

    def system(self, j, xR, b):
        A, S, C = self.pieces[j]
        t1 = self.linear(self.matrix(lambda i: xR ** 2 * self.z ** i), S)
        t2 = self.linear(self.matrix(lambda i: xR * self.z ** i), C)
        bv = self.vec(b)
        return [A[r] + t1[r] + t2[r] + bv[r] for r in range(self.n)]

    def fromBits(self, bits):
        return sum(self.z ** i for i in range(self.k) if bits[i])


def halfTraceTau(c, n):
    t, s = c, c
    for _ in range((n - 1) // 2):
        t = t ** 4
        s += t
    return s


class TauCurve:
    """E0 with the orbit-closure factor base of V'."""

    def __init__(self, fld, N, h):
        F = fld.F
        n = fld.n
        self.fld, self.b = fld, F(1)
        self.E = EllipticCurve(F, [1, 0, 0, 0, 1])
        self.N, self.h, self.p = N, h, N // h
        enc = lambda e: ZZ(e.polynomial().change_ring(ZZ)(2))
        base = {}
        for c in range(1, 2 ** fld.k):
            x = fld.fromBits([(c >> i) & 1 for i in range(fld.k)])
            rhs = x + 1 / x ** 2
            if rhs.trace() == 0:
                base[x] = self.E(x, x * halfTraceTau(rhs, n))
        # Orbit representatives: smallest-encoding x in each Frobenius orbit.
        self.reps, self.repOf = [], {}
        for x in sorted(base, key=enc):
            orbit = [x ** (2 ** e) for e in range(n)]
            rx = min(orbit, key=enc)
            if rx not in self.repOf:
                self.repOf[rx] = len(self.reps)
                ry = self.E.lift_x(rx)
                self.reps.append(self.E(rx, ry[1]))
        # Every V' point as sign * tau^e(rep).
        self.base = {}
        for x, P in base.items():
            orbit = [x ** (2 ** e) for e in range(n)]
            rx = min(orbit, key=enc)
            col = self.repOf[rx]
            Rp = self.reps[col]
            for e in range(n):
                T = self.E(Rp[0] ** (2 ** e), Rp[1] ** (2 ** e))
                if T == P:
                    self.base[x] = (P, col, e, 1)
                    break
                if T == -P:
                    self.base[x] = (P, col, e, -1)
                    break
            assert x in self.base
        self.fbPoints = n * len(self.base)   # upper bound on |F|, before orbit overlaps


def tauEigen(cur, G):
    p = cur.p
    Fp = GF(p)
    t = polygen(Fp)
    for lam in (t ** 2 + t + 2).roots(multiplicities=False):
        if ZZ(lam) * G == cur.E(G[0] ** 2, G[1] ** 2):
            return ZZ(lam)
    raise ValueError('no Frobenius eigenvalue')


def tauRelation(cur, R, stats, shifts):
    fld = cur.fld
    n = fld.n
    for j in shifts:
        c0 = time.process_time()
        polys = [f for f in fld.system(j, R[0], cur.b) if f != 0]
        I = ideal(polys)
        gb = I.groebner_basis()
        sols = I.variety() if gb != [1] else []
        stats['gb_cpu_s'] += time.process_time() - c0
        stats['gb_calls'] += 1
        for sol in sols:
            x1 = fld.fromBits([sol[g] for g in fld.u])
            x2 = fld.fromBits([sol[g] for g in fld.w])
            if x1 not in cur.base or x2 not in cur.base:
                stats['spurious'] += 1
                continue
            P1, col1, e1, sg1 = cur.base[x1]
            P2, col2, e2, sg2 = cur.base[x2]
            T2 = cur.E(P2[0] ** (2 ** j), P2[1] ** (2 ** j))
            for s1 in (1, -1):
                for s2 in (1, -1):
                    if s1 * P1 + s2 * T2 == R:
                        # P1 = sg1 tau^e1 rep1, T2 = tau^j P2 = sg2 tau^(j+e2) rep2.
                        return [(col1, s1 * sg1, e1), (col2, s2 * sg2, (j + e2) % n)]
            stats['spurious'] += 1
    return None


def tauDlp(cur, P, Q, rng, extra=10):
    p, h, n = cur.p, cur.h, cur.fld.n
    lam = tauEigen(cur, P)
    Fp = GF(p)
    ncol = len(cur.reps)
    stats = {'gb_cpu_s': 0.0, 'gb_calls': 0, 'spurious': 0, 'targets': 0}
    rows, rhs = [], []
    c0 = time.process_time()
    t0 = time.perf_counter()
    shifts = list(range(n))
    while len(rows) < ncol + extra:
        stats['targets'] += 1
        al, be = rng.randrange(1, int(p)), rng.randrange(1, int(p))
        R = al * P + be * Q
        if R.is_zero():
            continue
        rng.shuffle(shifts)
        rel = tauRelation(cur, R, stats, shifts)
        if rel is None:
            continue
        row = {}
        for col, sign, e in rel:
            row[col] = row.get(col, Fp(0)) + sign * Fp(lam) ** e
        rows.append(row)
        rhs.append((h * al % p, h * be % p))
    c1 = time.process_time()
    used = sorted({c for r in rows for c in r})
    idx = {c: i for i, c in enumerate(used)}
    M = matrix(Fp, len(rows), len(used), sparse=True)
    for i, r in enumerate(rows):
        for c, v in r.items():
            M[i, idx[c]] += v
    s = None
    for v in M.left_kernel().basis():
        A = sum(v[i] * rhs[i][0] for i in range(len(rows)))
        Bc = sum(v[i] * rhs[i][1] for i in range(len(rows)))
        if Bc != 0:
            s = ZZ(-A / Bc)
            break
    stats.update({'relations': len(rows), 'orbits': ncol, 'v_points': len(cur.base),
                  'relation_cpu_s': c1 - c0, 'linalg_cpu_s': time.process_time() - c1,
                  'total_cpu_s': time.process_time() - c0, 'total_s': time.perf_counter() - t0,
                  'log': int(s) if s is not None else None, 'recovered': s is not None and s * P == Q})
    return stats

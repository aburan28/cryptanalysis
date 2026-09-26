# E0 with the textbook tau-invariant factor base -- x of Hamming weight <= w
# in a normal basis -- decomposed by SAT instead of Groebner bases.
#
# Squaring cyclically shifts normal-basis coordinates, so the weight-bounded
# set is closed under tau and needs one unknown per Frobenius orbit. The
# Weil-descended S3 equations are quadratic in the coordinate bits c (of x1)
# and d (of x2). Each product c_i d_j gets an auxiliary variable (three
# clauses), every equation becomes one CryptoMiniSat XOR clause, and the
# weight bounds are sequential-counter cardinality constraints. All
# solutions are enumerated with blocking clauses.
#
# Needs tauEigen from tau.sage.

import time
import random
from itertools import combinations
from pycryptosat import Solver
from pysat.card import CardEnc, EncType
from sage.rings.polynomial.pbori.pbori import BooleanPolynomialRing


class NormalBasisField:
    def __init__(self, n, modulus, seed=5):
        R = PolynomialRing(GF(2), 'Z')
        self.F = GF(2 ** n, 'z', modulus=R(modulus))
        self.z = self.F.gen()
        self.n = n
        rng = random.Random(int(seed))
        while True:
            t = self.F.from_integer(rng.randrange(1, 2 ** n))
            if matrix(GF(2), [self.vec(t ** (2 ** i)) for i in range(n)]).rank() == n:
                break
        self.beta = [t ** (2 ** i) for i in range(n)]
        self.B = BooleanPolynomialRing(2 * n, ['c%d' % i for i in range(n)] + ['d%d' % i for i in range(n)])
        g = self.B.gens()
        self.c, self.d = g[:n], g[n:]
        self.index = {g[i].lm(): int(i + 1) for i in range(2 * n)}
        bv = [self.vec(b) for b in self.beta]
        lin = lambda coef: [sum((coef[i] for i in range(n) if bv[i][k]), self.B(0)) for k in range(n)]
        # Squaring shifts normal-basis coordinates by one place.
        shift = lambda v: [v[(i - 1) % n] for i in range(n)]
        self.sqSum = [a + b for a, b in zip(lin(shift(self.c)), lin(shift(self.d)))]      # x1^2 + x2^2
        prod = [[self.vec(self.beta[i] * self.beta[j]) for j in range(n)] for i in range(n)]
        bil = lambda u, w: [sum((u[i] * w[j] for i in range(n) for j in range(n) if prod[i][j][k]), self.B(0))
                            for k in range(n)]
        self.P12 = bil(self.c, self.d)                                                    # x1 x2
        self.P12sq = bil(shift(self.c), shift(self.d))                                    # (x1 x2)^2

    def vec(self, e):
        v = e.polynomial().list()
        return v + [0] * (self.n - len(v))

    def mulMatrix(self, e):
        return matrix(GF(2), [self.vec(e * self.z ** i) for i in range(self.n)]).transpose()

    def linear(self, M, polys):
        return [sum((polys[c] for c in M.nonzero_positions_in_row(r)), self.B(0)) for r in range(self.n)]

    def system(self, xR, b):
        t1 = self.linear(self.mulMatrix(xR ** 2), self.sqSum)
        t2 = self.linear(self.mulMatrix(xR), self.P12)
        bv = self.vec(b)
        return [self.P12sq[k] + t1[k] + t2[k] + bv[k] for k in range(self.n)]

    def element(self, bits):
        return sum((self.beta[i] for i in range(self.n) if bits[i]), self.F(0))


class NormalBasisCurve:
    """E0 with F = { P : x(P) has normal-basis weight 1..w }, one unknown per orbit."""

    def __init__(self, fld, weight, N, h):
        n = fld.n
        self.fld, self.weight = fld, weight
        self.b = fld.F(1)
        self.E = EllipticCurve(fld.F, [1, 0, 0, 0, 1])
        self.N, self.h, self.p = N, h, N // h
        self.base, self.reps = {}, []
        seen = set()
        for wt in range(1, weight + 1):
            for S in combinations(range(n), wt):
                if S in seen:
                    continue
                x = fld.element([i in S for i in range(n)])
                # The lift test Tr(x + 1/x^2) = 0 is invariant under squaring.
                if (x + 1 / x ** 2).trace() != 0:
                    continue
                rep = self.E.lift_x(x)
                col = len(self.reps)
                self.reps.append(rep)
                for e in range(n):
                    seen.add(tuple(sorted((i + e) % n for i in S)))
                    T = self.E(rep[0] ** (2 ** e), rep[1] ** (2 ** e))
                    self.base[T[0]] = (T, col, e)


def satDecompose(cur, R, stats, accept):
    """Search x1, x2 of weight <= w with S3(x1, x2, x(R)) = 0 via CryptoMiniSat.

    Each model is passed to accept(); the first relation it returns ends the
    search. Otherwise the model is blocked and the search continues until
    UNSAT, which proves the target has no decomposition over F."""
    fld = cur.fld
    n = fld.n
    polys = fld.system(R[0], cur.b)
    c0 = time.process_time()
    s = Solver(threads=1)
    var = dict(fld.index)
    top = [2 * n]

    def lit(m):
        if m in var:
            return var[m]
        # Sage preparses literals to Integer; the solver wants plain ints.
        a, b = [int(v + 1) for v in m.iterindex()]
        top[0] += 1
        t = int(top[0])
        s.add_clause([-t, a])
        s.add_clause([-t, b])
        s.add_clause([t, -a, -b])
        var[m] = t
        return t

    for f in polys:
        if f == 0:
            continue
        rhs, vs = False, []
        for m in f.terms():
            if m.deg() == 0:
                rhs = not rhs
            else:
                vs.append(lit(m))
        # f = 0  <=>  XOR of its monomials equals its constant term.
        s.add_xor_clause([int(v) for v in vs], bool(rhs))
    for block in ([int(i) for i in range(1, n + 1)], [int(i) for i in range(n + 1, 2 * n + 1)]):
        card = CardEnc.atmost(lits=block, bound=int(cur.weight), top_id=int(top[0]), encoding=EncType.seqcounter)
        top[0] = max(top[0], card.nv)
        for cl in card.clauses:
            s.add_clause([int(l) for l in cl])
        s.add_clause(block)       # x != 0
    rel = None
    while rel is None:
        ok, model = s.solve()
        if not ok:
            stats['unsat_proofs'] += 1
            break
        bits = [bool(model[int(i)]) for i in range(1, 2 * n + 1)]
        stats['solutions'] += 1
        rel = accept(bits[:n], bits[n:])
        if rel is None:
            s.add_clause([int(-(i + 1)) if bits[i] else int(i + 1) for i in range(2 * n)])
    stats['gb_cpu_s'] += time.process_time() - c0
    stats['gb_calls'] += 1
    return rel


def nbRelation(cur, R, stats):
    fld = cur.fld

    def accept(cb, db):
        x1, x2 = fld.element(cb), fld.element(db)
        if x1 not in cur.base or x2 not in cur.base:
            stats['spurious'] += 1
            return None
        P1, col1, e1 = cur.base[x1]
        P2, col2, e2 = cur.base[x2]
        for s1 in (1, -1):
            for s2 in (1, -1):
                if s1 * P1 + s2 * P2 == R:
                    return [(col1, s1, e1), (col2, s2, e2)]
        stats['spurious'] += 1
        return None

    return satDecompose(cur, R, stats, accept)


def nbDlp(cur, P, Q, rng, extra=10):
    p, h = cur.p, cur.h
    lam = tauEigen(cur, P)
    Fp = GF(p)
    ncol = len(cur.reps)
    stats = {'gb_cpu_s': 0.0, 'gb_calls': 0, 'solutions': 0, 'spurious': 0, 'unsat_proofs': 0, 'targets': 0}
    rows, rhs = [], []
    c0 = time.process_time()
    t0 = time.perf_counter()
    while len(rows) < ncol + extra:
        stats['targets'] += 1
        al, be = rng.randrange(1, int(p)), rng.randrange(1, int(p))
        R = al * P + be * Q
        if R.is_zero():
            continue
        rel = nbRelation(cur, R, stats)
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

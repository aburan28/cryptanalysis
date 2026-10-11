# Linearized-half decomposition (LHD) for m = 4 on y^2 + xy = x^3 + 1 over F_2^n.
#
# Factor base F_l = {P : x(P) in V}, V = span{1, z, ..., z^(l-1)} (polynomial basis).
#
# Two-point oracle.  With e1 = x1 + x2 and e2 = x1 x2, the third summation
# polynomial at a fixed x_T is
#     S_3(x1, x2, x_T) = e2^2 + x_T e2 + x_T^2 e1^2 + 1,
# which is F_2-LINEAR in (e1, e2) because squaring is.  x1, x2 in V puts
# e1 in V (l unknowns) and e2 in W = span{1, ..., z^(2l-2)} (2l - 1 unknowns),
# so "is T a signed sum of two base points" is an n x (3l - 1) linear system,
# followed by a root split X^2 + e1 X + e2 and a membership check.  Exact when
# the affine solution space is enumerated (it is tiny for 3l - 1 <= n).
#
# Four-point decomposition of R.  Repeatedly sample Q = P_a + P_b from the
# base and ask the oracle about R - Q.  Expected samples ~ 2^(n - 2l); each is
# one linear solve.  Meet-in-the-middle costs 2^(2l).  For n/4 < l <= (n+1)/3
# the sample count is below 2^(2l), i.e. an exponent (n - 2l)/l < 2 in |F|.
#
#   python3 lhd.py --n 31 --l 10 --targets 20 --seed 1 [--oracle-check 200]

import argparse
import json
import random
import sys
import time

# irreducible trinomials/pentanomials, low terms (x^n implicit)
POLYS = {17: [3, 0], 19: [5, 2, 1, 0], 23: [5, 0], 29: [2, 0], 31: [3, 0],
         37: [6, 4, 1, 0], 41: [3, 0], 43: [6, 4, 3, 0], 47: [5, 0],
         53: [6, 2, 1, 0], 59: [7, 4, 2, 0], 61: [5, 2, 1, 0], 67: [5, 2, 1, 0],
         71: [6, 0], 73: [25, 0], 79: [9, 0], 83: [7, 4, 2, 0], 89: [38, 0],
         97: [6, 0], 101: [7, 6, 1, 0], 131: [13, 2, 1, 0]}


class Field:
    def __init__(self, n):
        self.n = n
        self.mod = (1 << n)
        for t in POLYS[n]:
            self.mod |= 1 << t
        self.mask = (1 << n) - 1

    def mul(self, a, b):
        r = 0
        while b:
            if b & 1:
                r ^= a
            b >>= 1
            a <<= 1
            if a >> self.n:
                a ^= self.mod
        return r

    def sq(self, a):
        return self.mul(a, a)

    def pow(self, a, e):
        r = 1
        while e:
            if e & 1:
                r = self.mul(r, a)
            a = self.sq(a)
            e >>= 1
        return r

    def inv(self, a):
        return self.pow(a, (1 << self.n) - 2)

    def trace(self, a):
        t = a
        s = a
        for _ in range(self.n - 1):
            s = self.sq(s)
            t ^= s
        return t & 1 if t in (0, 1) else None

    def halfTrace(self, a):
        # n odd: H(a) = sum_{i=0}^{(n-1)/2} a^(4^i) solves z^2 + z = a when Tr(a) = 0
        h = a
        s = a
        for _ in range((self.n - 1) // 2):
            s = self.sq(self.sq(s))
            h ^= s
        return h


class Curve:
    """y^2 + xy = x^3 + 1; points as (x, y), None for O."""

    def __init__(self, f):
        self.f = f

    def lift(self, x):
        f = self.f
        if x == 0:
            return None
        # y = x z, z^2 + z = x + 1/x^2
        c = x ^ f.inv(f.sq(x))
        z = f.halfTrace(c)
        if (f.sq(z) ^ z) != c:
            return None
        return (x, f.mul(x, z))

    def neg(self, p):
        return None if p is None else (p[0], p[0] ^ p[1])

    def add(self, p, q):
        f = self.f
        if p is None:
            return q
        if q is None:
            return p
        x1, y1 = p
        x2, y2 = q
        if x1 == x2:
            if y1 != y2 or x1 == 0:
                return None
            lam = x1 ^ f.mul(y1, f.inv(x1))
            x3 = f.sq(lam) ^ lam
            y3 = f.sq(x1) ^ f.mul(lam ^ 1, x3)
            return (x3, y3)
        lam = f.mul(y1 ^ y2, f.inv(x1 ^ x2))
        x3 = f.sq(lam) ^ lam ^ x1 ^ x2
        y3 = f.mul(lam, x1 ^ x3) ^ x3 ^ y1
        return (x3, y3)


def solveAffine(cols, rhs, nvars, cap=64):
    """All x with sum_j x_j cols[j] = rhs over F_2 (cols are n-bit ints).
    Returns up to cap solutions as bit-ints, [] if inconsistent, None if the
    affine space is larger than cap."""
    piv = {}          # pivot bit -> (vec, combo), fully reduced
    kernel = []
    for j in range(nvars):
        v = cols[j]
        combo = 1 << j
        for b, (pv, pc) in piv.items():
            if (v >> b) & 1:
                v ^= pv
                combo ^= pc
        if v == 0:
            kernel.append(combo)
            continue
        b = v.bit_length() - 1
        for b2 in list(piv):
            pv2, pc2 = piv[b2]
            if (pv2 >> b) & 1:
                piv[b2] = (pv2 ^ v, pc2 ^ combo)
        piv[b] = (v, combo)
    r = rhs
    sol = 0
    for b, (pv, pc) in piv.items():
        if (r >> b) & 1:
            r ^= pv
            sol ^= pc
    if r:
        return []
    if (1 << len(kernel)) > cap:
        return None
    out = []
    for mask in range(1 << len(kernel)):
        s = sol
        for i in range(len(kernel)):
            if (mask >> i) & 1:
                s ^= kernel[i]
        out.append(s)
    return out


class Lhd:
    def __init__(self, n, l):
        if not (3 * l - 1 <= n):
            raise ValueError('need 3l - 1 <= n for the linearization')
        self.f = Field(n)
        self.E = Curve(self.f)
        self.n = n
        self.l = l
        self.vmask = (1 << l) - 1
        f = self.f
        self.zpow = [f.pow(2, j) if j else 1 for j in range(2 * l - 1)]  # z^j (z = 2)
        self.zsq = [f.sq(z) for z in self.zpow]
        self.calls = 0

    def inV(self, x):
        return x >> self.l == 0

    def oracle2(self, T):
        """Signed pairs (P1, P2) of base points with P1 + P2 = T (all of them)."""
        self.calls += 1
        f = self.f
        xT = T[0]
        xT2 = f.sq(xT)
        l = self.l
        cols = []
        for i in range(l):                       # e1 coefficient a_i: x_T^2 z^(2i)
            cols.append(f.mul(xT2, self.zsq[i]))
        for j in range(2 * l - 1):               # e2 coefficient c_j: z^(2j) + x_T z^j
            cols.append(self.zsq[j] ^ f.mul(xT, self.zpow[j]))
        sols = solveAffine(cols, 1, 3 * l - 1)
        if sols is None:
            raise RuntimeError('solution space too large')
        found = []
        for s in sols:
            e1 = s & self.vmask
            e2 = 0
            cbits = s >> l
            for j in range(2 * l - 1):
                if (cbits >> j) & 1:
                    e2 ^= self.zpow[j]
            if e1 == 0:
                continue  # x1 = x2: P1 = +-P2, sum is O or 2P; skip (measure-zero)
            c = f.mul(e2, f.inv(f.sq(e1)))
            zz = f.halfTrace(c)
            if (f.sq(zz) ^ zz) != c:
                continue
            x1 = f.mul(e1, zz)
            x2 = x1 ^ e1
            if not (self.inV(x1) and self.inV(x2)):
                continue
            p1 = self.E.lift(x1)
            p2 = self.E.lift(x2)
            if p1 is None or p2 is None:
                continue
            for a in (p1, self.E.neg(p1)):
                for b in (p2, self.E.neg(p2)):
                    if self.E.add(a, b) == T:
                        found.append((a, b))
        return found

    def randomBasePoint(self, rng):
        while True:
            x = rng.getrandbits(self.l)
            p = self.E.lift(x)
            if p is not None:
                return p if rng.getrandbits(1) else self.E.neg(p)

    def decompose4(self, R, rng, maxSamples):
        E = self.E
        for s in range(1, maxSamples + 1):
            pa = self.randomBasePoint(rng)
            pb = self.randomBasePoint(rng)
            Q = E.add(pa, pb)
            T = E.add(R, E.neg(Q))
            if T is None or Q is None:
                continue
            pairs = self.oracle2(T)
            if pairs:
                p1, p2 = pairs[0]
                acc = None
                for p in (pa, pb, p1, p2):
                    acc = E.add(acc, p)
                assert acc == R, 'decomposition does not re-add to R'
                return (pa, pb, p1, p2), s
        return None, maxSamples


def bruteOracle(lhd, T):
    """Every signed pair from V with sum T, by enumeration (small l only)."""
    E = lhd.E
    pts = []
    for x in range(1, 1 << lhd.l):
        p = E.lift(x)
        if p is not None:
            pts.append(p)
            pts.append(E.neg(p))
    out = set()
    for i in range(len(pts)):
        for j in range(len(pts)):
            if pts[i][0] != pts[j][0] and E.add(pts[i], pts[j]) == T:
                out.add((pts[i], pts[j]))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--n', type=int, required=True)
    ap.add_argument('--l', type=int, required=True)
    ap.add_argument('--targets', type=int, default=10)
    ap.add_argument('--seed', type=int, default=1)
    ap.add_argument('--max-samples', type=int, default=1 << 24)
    ap.add_argument('--oracle-check', type=int, default=0,
                    help='compare oracle2 with brute force on this many targets')
    ap.add_argument('--out')
    a = ap.parse_args()
    lhd = Lhd(a.n, a.l)
    rng = random.Random('%d-%d-%d' % (a.n, a.l, a.seed))
    rec = {'n': a.n, 'l': a.l, 'seed': a.seed, 'predicted_log2_samples': a.n - 2 * a.l,
           'mitm_log2': 2 * a.l, 'targets': []}
    if a.oracle_check:
        bad = 0
        hits = 0
        for _ in range(a.oracle_check):
            # half the targets planted in V + V, half random
            if rng.getrandbits(1):
                T = lhd.E.add(lhd.randomBasePoint(rng), lhd.randomBasePoint(rng))
            else:
                while True:
                    T = lhd.E.lift(rng.getrandbits(a.n))
                    if T is not None:
                        break
            if T is None:
                continue
            got = set(frozenset(p) for p in lhd.oracle2(T))
            want = set(frozenset(p) for p in bruteOracle(lhd, T))
            hits += bool(want)
            if got != want:
                bad += 1
        rec['oracle_check'] = {'targets': a.oracle_check, 'mismatches': bad, 'with_pairs': hits}
        print('oracle check: %d targets, %d with pairs, %d mismatches' % (a.oracle_check, hits, bad), flush=True)
    for t in range(a.targets):
        while True:
            R = lhd.E.lift(rng.getrandbits(a.n))
            if R is not None:
                break
        c0 = lhd.calls
        t0 = time.process_time()
        dec, samples = lhd.decompose4(R, rng, a.max_samples)
        dt = time.process_time() - t0
        rec['targets'].append({'solved': dec is not None, 'samples': samples,
                               'oracle_calls': lhd.calls - c0, 'cpu_s': dt})
        print('target %d: %s samples=%d cpu=%.2fs' % (t, 'solved' if dec else 'budget', samples, dt), flush=True)
    if a.out:
        with open(a.out, 'w') as fh:
            json.dump(rec, fh, indent=1)
    return 0


if __name__ == '__main__':
    sys.exit(main())

"""Exact 2-D CVP for eigenvalue targets in an imaginary quadratic order Z[w0],
norm form Q(x,y) = x^2 + x y + c y^2, eigenvalue map ev(x + y w0) = x + y*w mod n.
Pure python3 big ints.  Used by cvp_search.py (real N) and cvp_selftest.py (toy n)."""
import math


class OrderLattice:
    def __init__(self, n, w, c):
        self.n, self.w, self.c = n, w % n, c
        # lattice L = {(x,y): x + y w = 0 mod n}; integer form M = 2*bilinear(Q)
        b1, b2 = (n, 0), ((-self.w) % n - n if (-self.w) % n > n // 2 else (-self.w) % n, 1)
        M = self.M
        while True:
            if M(b1, b1) > M(b2, b2):
                b1, b2 = b2, b1
            m11, m12 = M(b1, b1), M(b1, b2)
            mu = (2 * m12 + m11) // (2 * m11)          # round(m12/m11)
            if mu == 0:
                break
            b2 = (b2[0] - mu * b1[0], b2[1] - mu * b1[1])
        self.b1, self.b2 = b1, b2
        self.M11, self.M12, self.M22 = M(b1, b1), M(b1, b2), M(b2, b2)
        assert 2 * abs(self.M12) <= self.M11 <= self.M22           # Lagrange reduced
        for bb in (b1, b2):
            assert (bb[0] + bb[1] * self.w) % n == 0
        assert abs(b1[0] * b2[1] - b1[1] * b2[0]) == n              # basis of the index-n lattice
        self.m1 = 2 * b1[0] + b1[1]                                   # M((h,0), b) = h * m
        self.m2 = 2 * b2[0] + b2[1]
        self.A = self.m2 * self.M11 - self.M12 * self.m1
        self.Delta = self.M11 * self.M22 - self.M12 ** 2
        assert self.Delta > 0

    def M(self, u, v):
        c = self.c
        return 2 * u[0] * v[0] + u[0] * v[1] + u[1] * v[0] + 2 * c * u[1] * v[1]

    def Q(self, x, y):
        return x * x + x * y + self.c * y * y

    def cvp(self, h):
        """min-norm alpha = x + y w0 with ev(alpha) = h mod n. Returns (norm, x, y).
        Exact: nearest-plane radius R^2 <= (|b1|^2+|b2*|^2)/4 and |b2*|^2 >= 3/4 |b1|^2 imply the optimal
        c2 lies within 0.764 of tau2, i.e. in {fl, fl+1}; we scan fl-1..fl+2."""
        h %= self.n
        b1x, b1y = self.b1
        b2x, b2y = self.b2
        M11, c = self.M11, self.c
        fl = (h * self.A) // self.Delta
        best = None
        for c2 in (fl - 1, fl, fl + 1, fl + 2):
            rx, ry = h - c2 * b2x, -c2 * b2y
            proj = 2 * rx * b1x + rx * b1y + b1x * ry + 2 * c * ry * b1y
            c1 = (2 * proj + M11) // (2 * M11)
            x, y = rx - c1 * b1x, ry - c1 * b1y
            qv = x * x + x * y + c * y * y
            if best is None or qv < best[0]:
                best = (qv, x, y)
        return best


def primitive_root(n, fact):
    g = 2
    while True:
        if all(pow(g, (n - 1) // l, n) != 1 for l, _ in fact):
            return g
        g += 1


def divisors_from_fact(fact):
    ds = [1]
    for l, k in fact:
        ds = [d * l ** i for d in ds for i in range(k + 1)]
    return sorted(ds)


def elements_by_order(n, fact, bound):
    """yield (d, h) for every h in F_n^* whose order d < bound"""
    g = primitive_root(n, fact)
    for d in divisors_from_fact(fact):
        if d >= bound:
            continue
        gd = pow(g, (n - 1) // d, n)
        hh = 1
        for k in range(1, d + 1):
            hh = hh * gd % n
            if math.gcd(k, d) == 1:
                yield d, hh

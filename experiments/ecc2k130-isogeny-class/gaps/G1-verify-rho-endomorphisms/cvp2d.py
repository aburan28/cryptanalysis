"""Exact 2-D CVP in an order of K = Q(sqrt(-7)) under the norm form (independent implementation for G1).

An element alpha = x + y*w with w = m*tau (m = 1 for O_K, m = 263 for O_263), tau^2 + tau + 2 = 0.
Norm form Q(x, y) = x^2 - m x y + 2 m^2 y^2 (integer valued, positive definite, disc -7 m^2).
Eigenvalue on the order-N subgroup: ev(x, y) = x + y*c mod N with c = m*s mod N.
The kernel lattice L = {(x, y) : x + c y = 0 mod N} has index N in Z^2.
For a target eigenvalue z, the coset {ev = z} = (z, 0) + L; its minimum-norm element is an exact CVP.
Exactness argument (see README): Lagrange-reduced basis => the optimal k2 is within 1.155 of the real
coordinate u2, and for fixed k2 the optimal k1 is floor or ceil of the 1-D real minimiser.
We scan k2 in floor(u2)-2 .. floor(u2)+3 (superset) and both k1 roundings.
"""
try:
    from gmpy2 import mpz
except ImportError:  # plain ints work too, just slower
    mpz = int

S_EIGEN = 196511074115861092422032515080945363956
N_ORDER = 680564733841876926932320129493409985129


class NormLattice:
    def __init__(self, m, N=N_ORDER, s=S_EIGEN):
        self.m = mpz(m)
        self.N = mpz(N)
        self.B = -self.m          # coefficient of xy
        self.C = 2 * self.m * self.m  # coefficient of y^2
        self.c = (self.m * mpz(s)) % self.N
        b1 = (self.N, mpz(0))
        b2 = (-self.c, mpz(1))
        b1, b2 = self._lagrange(b1, b2)
        self.b1, self.b2 = b1, b2
        self.Q1 = self.Q(*b1)
        self.Q2 = self.Q(*b2)
        self.twoQ1 = 2 * self.Q1
        D = b1[0] * b2[1] - b2[0] * b1[1]
        assert abs(D) == self.N, "basis does not have index N"
        self.D = D
        # both basis vectors lie in L
        for v in (b1, b2):
            assert (v[0] + v[1] * self.c) % self.N == 0
        # reduction certificate
        assert self.Q1 <= self.Q2
        assert abs(self.bil2(b1, b2)) <= self.Q1
        # Q(b2*) = det(Gram)/Q(b1); exact rational comparisons done with integers:
        # 4*det(Gram) = 4*Q1*Q2 - (2Bil)^2
        self.four_det = 4 * self.Q1 * self.Q2 - self.bil2(b1, b2) ** 2
        assert self.four_det > 0

    def Q(self, x, y):
        return x * x + self.B * x * y + self.C * y * y

    def bil2(self, u, v):
        """2*B(u,v) where B is the symmetric bilinear form with B(u,u) = Q(u)."""
        return 2 * u[0] * v[0] + self.B * (u[0] * v[1] + u[1] * v[0]) + 2 * self.C * u[1] * v[1]

    def _lagrange(self, b1, b2):
        Q = self.Q
        while True:
            if Q(*b2) < Q(*b1):
                b1, b2 = b2, b1
            num = self.bil2(b1, b2)
            den = 2 * Q(*b1)
            mu = (2 * num + den) // (2 * den)  # nearest integer to num/den
            if mu == 0:
                break
            b2 = (b2[0] - mu * b1[0], b2[1] - mu * b1[1])
        return b1, b2

    def ev(self, x, y):
        return (mpz(x) + mpz(y) * self.c) % self.N

    def cvp(self, z, window=(-2, 3)):
        """Minimum-norm element of the coset {ev = z}. Returns (norm, x, y, n_ties)."""
        z = mpz(z)
        b1x, b1y = self.b1
        b2x, b2y = self.b2
        D = self.D
        num2 = -z * b1y
        if D > 0:
            fl2 = num2 // D
        else:
            fl2 = (-num2) // (-D)
        best = None
        bx = by = None
        ties = 0
        for k2 in range(int(fl2) + window[0], int(fl2) + window[1] + 1):
            wx = z - k2 * b2x
            wy = -k2 * b2y
            n = self.bil2((wx, wy), self.b1)
            k1a = n // self.twoQ1
            for k1 in (k1a, k1a + 1):
                ax = wx - k1 * b1x
                ay = wy - k1 * b1y
                v = ax * ax + self.B * ax * ay + self.C * ay * ay
                if best is None or v < best:
                    best, bx, by, ties = v, ax, ay, 0
                elif v == best and (ax, ay) != (bx, by):
                    ties += 1
        return best, bx, by, ties

    def lambda1(self):
        return self.Q1

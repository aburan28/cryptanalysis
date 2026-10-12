"""Pure-Python (no Sage, no PARI) arithmetic for binary fields and ordinary binary curves.

Written for the 'group-order' sweep so that the per-curve order / structure checks do not
share code with the ground-truth builder (which used Sage + PARI).

  GF2m(d, taps): F_{2^d} = F_2[z]/(z^d + sum_{i in taps} z^i); elements are int bitmasks
                 (bit i = coefficient of z^i), the same encoding as ground_truth.json.
  Curve(F, a2, b): y^2 + x y = x^3 + a2 x^2 + b, affine points (x, y) or None for O.
  agm_trace(F, b, prec): Frobenius trace of y^2 + xy = x^3 + b by Mestre's AGM (2-adic).
"""
import random


class GF2m:
    def __init__(self, d, taps):
        self.d = d
        self.taps = tuple(sorted(set(taps), reverse=True))
        assert all(0 <= i < d for i in self.taps) and 0 in self.taps
        self.modulus = (1 << d) | sum(1 << i for i in self.taps)
        self.mask = (1 << d) - 1
        # linear trace functional Tr(x) = parity(x & tmask)
        tm = 0
        for i in range(d):
            if self._trace_slow(1 << i):
                tm |= 1 << i
        self.tmask = tm
        assert self.trace(1) == d % 2

    def reduce(self, r):
        d, mask, taps = self.d, self.mask, self.taps
        while r >> d:
            h = r >> d
            r &= mask
            for i in taps:
                r ^= h << i
        return r

    def mul(self, a, b):
        if a == 0 or b == 0:
            return 0
        tab = [0] * 16
        tab[1] = a
        for i in range(2, 16):
            tab[i] = (tab[i >> 1] << 1) if i % 2 == 0 else (tab[i - 1] ^ a)
        r = 0
        nb = b.bit_length()
        top = ((nb + 3) // 4) * 4
        for sh in range(top - 4, -1, -4):
            r = (r << 4) ^ tab[(b >> sh) & 15]
        return self.reduce(r)

    def sqr(self, a):
        return self.mul(a, a)

    def pow(self, a, e):
        r = 1
        base = a
        while e:
            if e & 1:
                r = self.mul(r, base)
            base = self.sqr(base)
            e >>= 1
        return r

    def inv(self, a):
        if a == 0:
            raise ZeroDivisionError
        u, v = a, self.modulus
        g1, g2 = 1, 0
        while u != 1:
            j = u.bit_length() - v.bit_length()
            if j < 0:
                u, v = v, u
                g1, g2 = g2, g1
                j = -j
            u ^= v << j
            g1 ^= g2 << j
        return self.reduce(g1)

    def _trace_slow(self, a):
        s, x = 0, a
        for _ in range(self.d):
            s ^= x
            x = self.sqr(x)
        assert s in (0, 1)
        return s

    def trace(self, a):
        return bin(a & self.tmask).count("1") & 1

    def sqrt(self, a):
        # a^(2^(d-1))
        for _ in range(self.d - 1):
            a = self.sqr(a)
        return a

    def half_trace(self, c):
        # for odd d: H(c) = sum_{i=0}^{(d-1)/2} c^(4^i); H^2 + H = c + Tr(c)
        assert self.d % 2 == 1
        h, x = 0, c
        for _ in range((self.d - 1) // 2 + 1):
            h ^= x
            x = self.sqr(self.sqr(x))
        return h

    def rand(self, rng):
        return rng.getrandbits(self.d)


class Curve:
    """y^2 + x y = x^3 + a2 x^2 + b over GF2m F (ordinary, b != 0)."""

    def __init__(self, F, a2, b):
        assert b != 0
        self.F, self.a2, self.b = F, a2, b

    def on_curve(self, P):
        if P is None:
            return True
        F = self.F
        x, y = P
        lhs = F.sqr(y) ^ F.mul(x, y)
        x2 = F.sqr(x)
        rhs = F.mul(x2, x) ^ F.mul(self.a2, x2) ^ self.b
        return lhs == rhs

    def neg(self, P):
        if P is None:
            return None
        return (P[0], P[0] ^ P[1])

    def dbl(self, P):
        if P is None:
            return None
        F = self.F
        x1, y1 = P
        if x1 == 0:
            return None  # (0, sqrt b) is the 2-torsion point
        lam = x1 ^ F.mul(y1, F.inv(x1))
        x3 = F.sqr(lam) ^ lam ^ self.a2
        y3 = F.sqr(x1) ^ F.mul(lam, x3) ^ x3
        return (x3, y3)

    def add(self, P, Q):
        if P is None:
            return Q
        if Q is None:
            return P
        F = self.F
        x1, y1 = P
        x2, y2 = Q
        if x1 == x2:
            if y1 == y2:
                return self.dbl(P)
            return None  # Q = -P
        lam = F.mul(y1 ^ y2, F.inv(x1 ^ x2))
        x3 = F.sqr(lam) ^ lam ^ x1 ^ x2 ^ self.a2
        y3 = F.mul(lam, x1 ^ x3) ^ x3 ^ y1
        return (x3, y3)

    def mul(self, k, P):
        if k < 0:
            return self.mul(-k, self.neg(P))
        R = None
        for bit in bin(k)[2:] if k else "":
            R = self.dbl(R)
            if bit == "1":
                R = self.add(R, P)
        return R

    def lift_x(self, x):
        """Return a point with this x (or None if x is not an abscissa)."""
        F = self.F
        if x == 0:
            return (0, F.sqrt(self.b))
        x2 = F.sqr(x)
        rhs = F.mul(x2, x) ^ F.mul(self.a2, x2) ^ self.b
        c = F.mul(rhs, F.inv(x2))  # w^2 + w = c, y = x w
        if F.trace(c):
            return None
        w = F.half_trace(c)
        P = (x, F.mul(x, w))
        assert self.on_curve(P)
        return P

    def random_point(self, rng):
        while True:
            P = self.lift_x(self.F.rand(rng))
            if P is not None:
                if rng.getrandbits(1):
                    P = self.neg(P)
                return P

    def count_bruteforce(self):
        """#E(F_{2^d}) by summing over x (small d only)."""
        F = self.F
        n = 2  # O and (0, sqrt b)
        for x in range(1, 1 << F.d):
            x2 = F.sqr(x)
            rhs = F.mul(x2, x) ^ F.mul(self.a2, x2) ^ self.b
            c = F.mul(rhs, F.inv(x2))
            if F.trace(c) == 0:
                n += 2
        return n


# ---------------------------------------------------------------------------
# 2-adic arithmetic in Z_q / 2^P, Z_q = Z_2[z]/(m~(z)), m~ = lift of the F_2 modulus with
# coefficients in {0,1}.  Elements are lists of d Python ints in [0, 2^P).
# ---------------------------------------------------------------------------


class Zq:
    def __init__(self, F, P):
        self.F, self.d, self.P = F, F.d, P
        self.M = (1 << P) - 1
        # Kronecker slot width in bytes: products of d pairs of P-bit coefficients stay < 2^(2P+8)
        self.WB = (2 * P + (F.d).bit_length() + 4 + 7) // 8
        self.taps = F.taps  # m~(z) = z^d + sum z^taps, so z^d = -sum z^taps

    def one(self):
        v = [0] * self.d
        v[0] = 1
        return v

    def from_f2(self, a):
        return [(a >> i) & 1 for i in range(self.d)]

    def pack(self, A):
        WB = self.WB
        return int.from_bytes(b"".join(c.to_bytes(WB, "little") for c in A), "little")

    def mul(self, A, B):
        """Kronecker substitution: pack coefficients into byte-aligned slots, one big-int product,
        unpack, then reduce with z^d = -sum z^taps (signed ints, cascades handled top-down)."""
        d, WB, M = self.d, self.WB, self.M
        c = self.pack(A) * self.pack(B)
        bs = c.to_bytes(WB * (2 * d - 1), "little")
        C = [int.from_bytes(bs[i * WB:(i + 1) * WB], "little") for i in range(2 * d - 1)]
        taps = self.taps
        for k in range(2 * d - 2, d - 1, -1):
            h = C[k]
            if h:
                C[k] = 0
                base = k - d
                for i in taps:
                    C[base + i] -= h
        return [x & M for x in C[:d]]

    def add(self, A, B):
        M = self.M
        return [(a + b) & M for a, b in zip(A, B)]

    def sub(self, A, B):
        M = self.M
        return [(a - b) & M for a, b in zip(A, B)]

    def half(self, A):
        """A / 2 for A with all coefficients even (loses the top bit of precision)."""
        assert all(a % 2 == 0 for a in A), "half of a non-even element"
        return [a >> 1 for a in A]

    def inv_1mod4(self, U):
        """U^{-1} for U = 1 mod 4 (coefficientwise) by Newton y <- y (2 - U y)."""
        assert U[0] % 4 == 1 and all(u % 4 == 0 for u in U[1:])
        Y = self.one()
        two = [0] * self.d
        two[0] = 2
        one = self.one()
        for _ in range(self.P.bit_length() + 4):
            UY = self.mul(U, Y)
            if UY == one:
                return Y
            Y = self.mul(Y, self.sub(two, UY))
        raise ArithmeticError("inverse Newton did not converge")

    def invsqrt_1mod8(self, X):
        """X^{-1/2} (the root = 1 mod 4) for X = 1 mod 8, Newton y <- y + y (1 - X y^2)/2."""
        assert X[0] % 8 == 1 and all(u % 8 == 0 for u in X[1:])
        Y = self.one()
        one = self.one()
        for _ in range(self.P.bit_length() + 5):
            E = self.sub(one, self.mul(X, self.mul(Y, Y)))
            if not any(E):
                return Y
            Y = self.add(Y, self.mul(Y, self.half(E)))
        raise ArithmeticError("inverse-sqrt Newton did not converge")


def agm_unit_root(F, b, prec=80, guard=24, warm=None, lift=None):
    """Mestre's AGM for E_b: y^2 + xy = x^3 + b over F_{2^d}.

    lambda_0 = 1/(1 + 8 b~) with b~ the {0,1}-lift of b; lambda_{k+1} = 2 sqrt(lambda_k)/(1+lambda_k).
    After `warm` steps the sequence is (to high 2-adic precision) Frobenius-periodic, so the product
    of 2/(1+lambda_k) over d consecutive steps is a norm N_{Q_q/Q_2}(.), an element of Z_2: the
    unit root of Frobenius.  Returns (c mod 2^prec, max 2-adic valuation check info).
    """
    P = prec + guard
    Z = Zq(F, P)
    if warm is None:
        warm = prec + 12
    bl = Z.from_f2(b if lift is None else lift)
    lam0 = [8 * x for x in bl]
    lam0[0] += 1
    lam = Z.inv_1mod4(lam0)  # 1/(1+8b~) = 1 mod 8
    prod = Z.one()
    for k in range(warm + F.d):
        s = Z.mul(lam, Z.invsqrt_1mod8(lam))  # sqrt(lambda), = 1 mod 4
        h = Z.half(Z.add(Z.one(), lam))  # (1 + lambda)/2 = 1 mod 4
        hinv = Z.inv_1mod4(h)
        if k >= warm:
            prod = Z.mul(prod, hinv)  # 2/(1+lambda_k)
        lam = Z.mul(s, hinv)
    Mp = (1 << prec) - 1
    c = prod[0] & Mp
    nonconst = [x & Mp for x in prod[1:]]
    in_Z2 = all(x == 0 for x in nonconst)
    return c, in_Z2


def trace_from_unit_root(c, d, prec):
    """t = c + q/c in Z_2, reduced to the symmetric residue mod 2^prec."""
    mod = 1 << prec
    q = 1 << d
    t = (c + q * pow(c, -1, mod)) % mod
    if t >= mod // 2:
        t -= mod
    return t


def agm_trace(F, b, prec=80, guard=24, warm=None, lift=None):
    c, in_Z2 = agm_unit_root(F, b, prec, guard, warm, lift)
    return trace_from_unit_root(c, F.d, prec), in_Z2

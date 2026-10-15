#!/usr/bin/env python3
"""Independent big-integer arithmetic for the two fields and curves of this
experiment.  Shares no code with the Rust crate: polynomials are Python ints
(bit i = coefficient of z^i), products are shift-and-add, inversion is the
extended Euclidean algorithm, points are affine tuples (None = infinity).

Fields:
  F83  = GF(2)[z]/(z^83 + z^7 + z^4 + z^2 + 1)   (crypto legacy n=83 a=1 fixture)
  F131 = GF(2)[z]/(0xd1d0d000d0000000d000000000000000d), the polynomial basis of
         cryptanalysis:ecc2k130/src/f131.h (the walk's own basis of ECC2K-130's
         field GF(2^131); isomorphic to the Certicom z^131+z^13+z^2+z+1 basis).
Curves: E_a : y^2 + xy = x^3 + a x^2 + 1, a = 1 at n = 83, a = 0 at n = 131.
"""
import hashlib

M83 = (1 << 83) | (1 << 7) | (1 << 4) | (1 << 2) | 1
M131 = 0xd1d0d000d0000000d000000000000000d


class Field:
    def __init__(self, n, m):
        assert m.bit_length() == n + 1
        self.n, self.m = n, m

    def red(self, a):
        n, m = self.n, self.m
        while a.bit_length() > n:
            a ^= m << (a.bit_length() - 1 - n)
        return a

    def mul(self, a, b):
        r = 0
        while b:
            if b & 1:
                r ^= a
            a <<= 1
            b >>= 1
        return self.red(r)

    def sqr(self, a):
        return self.mul(a, a)

    def inv(self, a):
        assert a
        u, v, g1, g2 = a, self.m, 1, 0
        while u != 1:
            j = u.bit_length() - v.bit_length()
            if j < 0:
                u, v, g1, g2, j = v, u, g2, g1, -j
            u ^= v << j
            g1 ^= g2 << j
        return self.red(g1)

    def trace(self, a):
        t, s = 0, a
        for _ in range(self.n):
            t ^= s
            s = self.sqr(s)
        return t

    def half_trace(self, a):
        h, s = 0, a
        for i in range(self.n):
            if i % 2 == 0:
                h ^= s
            s = self.sqr(s)
        return h


class Curve:
    def __init__(self, f, a):
        self.f, self.a = f, a

    def on(self, p):
        if p is None:
            return True
        x, y = p
        f = self.f
        return f.sqr(y) ^ f.mul(x, y) == f.mul(f.sqr(x), x) ^ f.mul(self.a, f.sqr(x)) ^ 1

    def neg(self, p):
        return None if p is None else (p[0], p[0] ^ p[1])

    def add(self, p, q):
        f = self.f
        if p is None:
            return q
        if q is None:
            return p
        (x1, y1), (x2, y2) = p, q
        if x1 == x2:
            if y1 ^ y2 == x1:
                return None
            if x1 == 0:
                return None
            lam = x1 ^ f.mul(y1, f.inv(x1))
            x3 = f.sqr(lam) ^ lam ^ self.a
            y3 = f.sqr(x1) ^ f.mul(lam ^ 1, x3)
            return (x3, y3)
        lam = f.mul(y1 ^ y2, f.inv(x1 ^ x2))
        x3 = f.sqr(lam) ^ lam ^ x1 ^ x2 ^ self.a
        y3 = f.mul(lam, x1 ^ x3) ^ x3 ^ y1
        return (x3, y3)

    def mul(self, p, k):
        r = None
        for bit in bin(k)[2:] if k > 0 else "":
            r = self.add(r, r)
            if bit == "1":
                r = self.add(r, p)
        return r

    def frob(self, p, t=1):
        if p is None:
            return None
        x, y = p
        for _ in range(t):
            x, y = self.f.sqr(x), self.f.sqr(y)
        return (x, y)


def koblitz_order(n, a):
    mu = 1 if a == 1 else -1
    t0, t1 = 2, mu
    for _ in range(n - 1):
        t0, t1 = t1, mu * t1 - 2 * t0
    return 2 ** n + 1 - t1


def is_prime(n):
    if n < 2:
        return False
    for p in (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37):
        if n % p == 0:
            return n == p
    d, s = n - 1, 0
    while d % 2 == 0:
        d //= 2
        s += 1
    for a in (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47, 53):
        x = pow(a, d, n)
        if x in (1, n - 1):
            continue
        for _ in range(s - 1):
            x = x * x % n
            if x == n - 1:
                break
        else:
            return False
    return True


def sqrt_mod(a, p):
    """Tonelli-Shanks."""
    a %= p
    if a == 0:
        return 0
    assert pow(a, (p - 1) // 2, p) == 1
    q, s = p - 1, 0
    while q % 2 == 0:
        q //= 2
        s += 1
    z = 2
    while pow(z, (p - 1) // 2, p) != p - 1:
        z += 1
    m, c, t, r = s, pow(z, q, p), pow(a, q, p), pow(a, (q + 1) // 2, p)
    while t != 1:
        i, tt = 0, t
        while tt != 1:
            tt = tt * tt % p
            i += 1
        b = pow(c, 1 << (m - i - 1), p)
        m, c, t, r = i, b * b % p, t * b * b % p, r * b % p
    return r


def lift_x(curve, x, flip):
    """A point with abscissa x (z = y/x solves z^2 + z = x + a + 1/x^2), or None."""
    f = curve.f
    if x == 0:
        return None
    ix = f.inv(x)
    beta = x ^ curve.a ^ f.sqr(ix)
    z = f.half_trace(beta)
    if f.sqr(z) ^ z != beta:
        return None
    if flip:
        z ^= 1
    return (x, f.mul(x, z))


def public_point(curve, cofactor, domain, role, seed, nbytes):
    """Hash to x (first `nbytes` digest bytes, little-endian, mod 2^n), y by
    half-trace with sign bit 0 of digest byte `nbytes`, then [h]P.  With
    nbytes = 8 this is crypto's single_target_panel.public_point law."""
    counter = 0
    n = curve.f.n
    while True:
        dig = b""
        blk = 0
        while len(dig) < nbytes + 1:
            dig += hashlib.sha256(f"{domain}|{role}|{seed}|{counter}".encode()
                                  + (b"" if blk == 0 else b"|" + str(blk).encode())).digest()
            blk += 1
        counter += 1
        x = int.from_bytes(dig[:nbytes], "little") & ((1 << n) - 1)
        p = lift_x(curve, x, dig[nbytes] & 1)
        if p is None:
            continue
        q = curve.mul(p, cofactor)
        if q is None:
            continue
        return q


def setup(n):
    if n == 83:
        f, a = Field(83, M83), 1
    else:
        f, a = Field(131, M131), 0
    c = Curve(f, a)
    order = koblitz_order(n, a)
    h = 2 if a == 1 else 4
    # n = 83, a = 1: the legacy fixture's prime subgroup has cofactor 1128547018
    if n == 83:
        h = 1128547018
    r = order // h
    assert order % h == 0 and is_prime(r)
    mu = 1 if a == 1 else -1
    disc = (mu * mu - 8) % r
    s = sqrt_mod(disc, r)
    inv2 = pow(2, -1, r)
    roots = sorted({(mu + s) * inv2 % r, (mu - s) * inv2 % r})
    return c, order, h, r, roots

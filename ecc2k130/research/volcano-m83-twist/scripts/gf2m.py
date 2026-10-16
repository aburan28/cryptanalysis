"""GF(2^n) arithmetic (ints as bit-polynomials), polynomials over it, binary curves
y^2 + xy = x^3 + a2 x^2 + a6, char-2 division polynomials and Velu."""
import random

class Field:
    def __init__(s, n, mod):
        s.n, s.mod = n, mod
        s.sq_tab = [sum(((b >> i) & 1) << (2 * i) for i in range(8)) for b in range(256)]
    def red(s, a):
        n, m = s.n, s.mod
        while a.bit_length() > n:
            a ^= m << (a.bit_length() - 1 - n)
        return a
    def mul(s, a, b):
        if a.bit_length() < b.bit_length(): a, b = b, a
        T = [0] * 16
        for i in range(1, 16): T[i] = T[i >> 1] << 1 if i & 1 == 0 else T[i ^ 1] ^ a
        r = 0; k = 0
        while b:
            r ^= T[b & 15] << k; b >>= 4; k += 4
        return s.red(r)
    def sqr(s, a):
        r = 0; k = 0
        while a:
            r |= s.sq_tab[a & 255] << k; a >>= 8; k += 16
        return s.red(r)
    def inv(s, a):
        assert a
        r, t = 1, a      # a^(2^n - 2)
        for _ in range(s.n - 1):
            t = s.sqr(t); r = s.mul(r, t)
        return r
    def tr(s, a):
        t = a; r = a
        for _ in range(s.n - 1): t = s.sqr(t); r ^= t
        return r
    def sqrt(s, a):
        for _ in range(s.n - 1): a = s.sqr(a)
        return a
    def half_trace(s, a):  # solves z^2+z=a when Tr(a)=0 (n odd)
        r = a; t = a
        for _ in range((s.n - 1) // 2):
            t = s.sqr(s.sqr(t)); r ^= t
        return r
    def rand(s, rng): return rng.getrandbits(s.n)

# ---- polynomials over F: lists low->high ----
def pnorm(a):
    while a and a[-1] == 0: a.pop()
    return a
def padd(a, b):
    r = [0] * max(len(a), len(b))
    for i, c in enumerate(a): r[i] ^= c
    for i, c in enumerate(b): r[i] ^= c
    return pnorm(r)
def pmul(F, a, b):
    if not a or not b: return []
    r = [0] * (len(a) + len(b) - 1)
    for i, x in enumerate(a):
        if x:
            for j, y in enumerate(b):
                if y: r[i + j] ^= F.mul(x, y)
    return pnorm(r)
def pscale(F, a, c): return pnorm([F.mul(x, c) for x in a])
def pdivmod(F, a, b):
    a = a[:]; q = [0] * max(len(a) - len(b) + 1, 1); il = F.inv(b[-1])
    while len(a) >= len(b) and a:
        c = F.mul(a[-1], il); d = len(a) - len(b); q[d] = c
        for i, y in enumerate(b): a[i + d] ^= F.mul(c, y)
        pnorm(a)
    return pnorm(q), a
def pmod(F, a, b): return pdivmod(F, a, b)[1]
def pmonic(F, a): return pscale(F, a, F.inv(a[-1]))
def pgcd(F, a, b):
    while b: a, b = b, pmod(F, a, b)
    return pmonic(F, a) if a else a
def psqrmod(F, a, m):
    r = []
    for i, c in enumerate(a):
        if c:
            r += [0] * (2 * i + 1 - len(r)); r[2 * i] = F.sqr(c)
    return pmod(F, pnorm(r), m)
def pcompose_mod(F, g, h, m):  # g(h(x)) mod m, Horner
    r = []
    for c in reversed(g): r = padd(pmod(F, pmul(F, r, h), m), [c] if c else [])
    return r
def pderiv(a): return pnorm([c if i % 2 == 1 else 0 for i, c in enumerate(a)][1:])

def xq_pow(F, m, k):
    """x^(2^(n*k)) mod m"""
    r = [0, 1]
    for _ in range(F.n * k): r = psqrmod(F, r, m)
    return r

def distinct_degree(F, f, maxd):
    out = {}; h = [0, 1]; f = pmonic(F, f); d = 0
    while len(f) > 1 and d < maxd:
        d += 1
        for _ in range(F.n): h = psqrmod(F, h, f)
        g = pgcd(F, f, padd(h, [0, 1]))
        if len(g) > 1:
            out[d] = g; f = pdivmod(F, f, g)[0]; h = pmod(F, h, f) if len(f) > 1 else h
    return out, f

def equal_degree(F, g, d, rng):
    """split monic g, product of irreducibles of degree d, over GF(2^n) (trace method)."""
    if len(g) - 1 == d: return [g]
    while True:
        r = [F.rand(rng) for _ in range(len(g) - 1)]
        # T(r) = sum_{i<n*d} r^(2^i) mod g
        t = pmod(F, r, g); acc = t[:]
        for _ in range(F.n * d - 1):
            t = psqrmod(F, t, g); acc = padd(acc, t)
        h = pgcd(F, g, acc) if acc else []
        if h and 1 < len(h) < len(g):
            return equal_degree(F, h, d, rng) + equal_degree(F, pdivmod(F, g, h)[0], d, rng)

# ---- curves ----
class Curve:
    def __init__(s, F, a2, a6): s.F, s.a2, s.a6 = F, a2, a6
    def j(s): return s.F.inv(s.a6)
    def on(s, P):
        if P is None: return True
        F = s.F; x, y = P
        return F.sqr(y) ^ F.mul(x, y) ^ F.mul(F.sqr(x), x) ^ F.mul(s.a2, F.sqr(x)) ^ s.a6 == 0
    def add(s, P, Q):
        F = s.F
        if P is None: return Q
        if Q is None: return P
        x1, y1 = P; x2, y2 = Q
        if x1 == x2:
            if y1 ^ y2 == x2: return None  # Q = -P
            return s.dbl(P)
        l = F.mul(y1 ^ y2, F.inv(x1 ^ x2))
        x3 = F.sqr(l) ^ l ^ x1 ^ x2 ^ s.a2
        return (x3, F.mul(l, x1 ^ x3) ^ x3 ^ y1)
    def dbl(s, P):
        F = s.F
        if P is None or P[0] == 0: return None
        x, y = P; l = x ^ F.mul(y, F.inv(x))
        x3 = F.sqr(l) ^ l ^ s.a2
        return (x3, F.sqr(x) ^ F.mul(l ^ 1, x3))
    def neg(s, P): return None if P is None else (P[0], P[0] ^ P[1])
    def mul(s, k, P):
        R = None
        for b in bin(k)[2:]:
            R = s.dbl(R)
            if b == "1": R = s.add(R, P)
        return R
    def lift_x(s, x):
        """a point with abscissa x, or None"""
        F = s.F
        if x == 0: return (0, F.sqrt(s.a6))
        # y = x z, z^2 + z = x + a2 + a6/x^2
        c = x ^ s.a2 ^ F.mul(s.a6, F.sqr(F.inv(x)))
        if F.tr(c) & 1: return None
        return (x, F.mul(x, F.half_trace(c)))
    def rand_point(s, rng):
        while True:
            P = s.lift_x(s.F.rand(rng))
            if P: return P

def koblitz_order(n, a):
    mu = 1 if a == 1 else -1
    t0, t1 = 2, mu
    for _ in range(n - 1): t0, t1 = t1, mu * t1 - 2 * t0
    return 2 ** n + 1 - t1, t1

def division_poly(F, a6, m):
    cache = {0: [], 1: [1], 2: [0, 1], 3: [a6, 0, 0, 1, 1], 4: [0, 0, a6, 0, 0, 0, 1]}
    def rec(k):
        if k in cache: return cache[k]
        if k % 2:
            q = (k - 1) // 2
            a, b, c, d = rec(q + 2), rec(q), rec(q - 1), rec(q + 1)
            out = padd(pmul(F, a, pmul(F, b, pmul(F, b, b))), pmul(F, c, pmul(F, d, pmul(F, d, d))))
        else:
            q = k // 2
            a, b, c, d, e = rec(q + 2), rec(q - 1), rec(q - 2), rec(q + 1), rec(q)
            num = pmul(F, e, padd(pmul(F, a, pmul(F, b, b)), pmul(F, c, pmul(F, d, d))))
            assert num[0] == 0; out = num[1:]
        cache[k] = out; return out
    return rec(m)

def velu_codomain(F, a6, h):
    d = len(h) - 1; t = h[d - 1]
    return a6 ^ t ^ F.sqr(t)

def velu_x(F, h, x):
    d = len(h) - 1
    hv = 0
    for c in reversed(h): hv = F.mul(hv, x) ^ c
    if hv == 0: return None
    dh = pderiv(h); dv = 0
    for c in reversed(dh): dv = F.mul(dv, x) ^ c
    A = (d & 1) ^ F.mul(x, F.mul(dv, F.inv(hv)))
    return x ^ A ^ F.sqr(A)

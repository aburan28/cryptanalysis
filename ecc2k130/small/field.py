"""Reference arithmetic for the small ECC2K-like walker.

Everything the Metal kernel computes has a counterpart here: F_2^m in a
polynomial basis chosen for cheap GPU reduction, the isomorphism from the
challenge file's basis, a normal basis for the Frobenius-invariant
Hamming weight, the curve y^2 + xy = x^3 + a x^2 + 1, the walk
R -> R + sigma^j(R), and the start points Q + sum sigma^e_k(P_k).
Standard library only.
"""

from __future__ import annotations

import random

MASK64 = (1 << 64) - 1
J_BASE = 3  # the walk's j is J_BASE + ((HW / 2) mod 8), as in ECC2K-130
J_COUNT = 8


def clmul(a: int, b: int) -> int:
    if a.bit_length() < b.bit_length():
        a, b = b, a
    r = 0
    while b:
        low = b & -b
        r ^= a << (low.bit_length() - 1)
        b ^= low
    return r


def spread(a: int) -> int:
    r = 0
    i = 0
    while a:
        if a & 1:
            r |= 1 << (2 * i)
        a >>= 1
        i += 1
    return r


def irreducible_prime_degree(terms: list[int]) -> bool:
    """x^(2^m) = x mod f, which suffices for prime m and f(0) = f(1) = 1."""
    m = max(terms)
    f = sum(1 << t for t in terms)
    field = Field(m, f, check=False)
    x = 2
    for _ in range(m):
        x = field.sqr(x)
    return x == 2 and len(terms) % 2 == 1 and 0 in terms


def gpu_polynomial(m: int) -> list[int]:
    """Lowest trinomial, else pentanomial, whose middle terms fit the
    kernel's word-at-a-time folding (every middle term <= m - 33)."""
    limit = m - 33
    for k in range(1, limit + 1):
        if irreducible_prime_degree([m, k, 0]):
            return [m, k, 0]
    for k3 in range(3, limit + 1):
        for k2 in range(2, k3):
            for k1 in range(1, k2):
                if irreducible_prime_degree([m, k3, k2, k1, 0]):
                    return [m, k3, k2, k1, 0]
    raise RuntimeError(f"no sparse polynomial for m={m}")


class Field:
    def __init__(self, m: int, modulus: int, check: bool = True):
        self.m = m
        self.f = modulus
        self.mask = (1 << m) - 1
        if check and not irreducible_prime_degree([i for i in range(m + 1) if modulus >> i & 1]):
            raise ValueError("modulus is not irreducible")

    def reduce(self, a: int) -> int:
        m, f = self.m, self.f
        while a.bit_length() > m:
            a ^= f << (a.bit_length() - 1 - m)
        return a

    def mul(self, a: int, b: int) -> int:
        return self.reduce(clmul(a, b))

    def sqr(self, a: int) -> int:
        return self.reduce(spread(a))

    def sqrn(self, a: int, n: int) -> int:
        for _ in range(n):
            a = self.sqr(a)
        return a

    def inv(self, a: int) -> int:
        if a == 0:
            raise ZeroDivisionError
        # Extended Euclid in F_2[x].
        u, v, g1, g2 = a, self.f, 1, 0
        while u != 1:
            j = u.bit_length() - v.bit_length()
            if j < 0:
                u, v, g1, g2, j = v, u, g2, g1, -j
            u ^= v << j
            g1 ^= g2 << j
        return self.reduce(g1)

    def pow(self, a: int, e: int) -> int:
        r = 1
        while e:
            if e & 1:
                r = self.mul(r, a)
            a = self.sqr(a)
            e >>= 1
        return r

    def trace(self, a: int) -> int:
        t, s = a, a
        for _ in range(self.m - 1):
            s = self.sqr(s)
            t ^= s
        return t


# --- the curve y^2 + xy = x^3 + a x^2 + 1 -----------------------------------

INF = None


class Curve:
    def __init__(self, field: Field, a: int):
        self.F = field
        self.a = a

    def on_curve(self, P) -> bool:
        if P is INF:
            return True
        F = self.F
        x, y = P
        return F.sqr(y) ^ F.mul(x, y) == F.mul(F.sqr(x), x) ^ F.mul(self.a, F.sqr(x)) ^ 1

    def neg(self, P):
        return INF if P is INF else (P[0], P[0] ^ P[1])

    def frob(self, P, n: int = 1):
        return INF if P is INF else (self.F.sqrn(P[0], n), self.F.sqrn(P[1], n))

    def add(self, P, Q):
        F = self.F
        if P is INF:
            return Q
        if Q is INF:
            return P
        x1, y1 = P
        x2, y2 = Q
        if x1 == x2:
            if y1 != y2 or x1 == 0:
                return INF
            lam = x1 ^ F.mul(y1, F.inv(x1))
            x3 = F.sqr(lam) ^ lam ^ self.a
            return x3, F.sqr(x1) ^ F.mul(lam ^ 1, x3)
        lam = F.mul(y1 ^ y2, F.inv(x1 ^ x2))
        x3 = F.sqr(lam) ^ lam ^ x1 ^ x2 ^ self.a
        return x3, F.mul(lam, x1 ^ x3) ^ x3 ^ y1

    def mul(self, k: int, P):
        if k < 0:
            return self.mul(-k, self.neg(P))
        R = INF
        while k:
            if k & 1:
                R = self.add(R, P)
            P = self.add(P, P)
            k >>= 1
        return R


# --- the isomorphism from the challenge file's field --------------------------


def _poly_monic(g, F):
    inv = F.inv(g[-1])
    return [F.mul(c, inv) for c in g]


def _poly_trim(g):
    while g and g[-1] == 0:
        g.pop()
    return g


def _poly_mod(a, g, F):
    a = list(a)
    d = len(g) - 1  # g is monic
    for i in range(len(a) - 1, d - 1, -1):
        c = a[i]
        if c:
            for k in range(d + 1):
                a[i - d + k] ^= F.mul(c, g[k])
    return _poly_trim(a[:d])


def _poly_gcd(a, b, F):
    a, b = _poly_trim(list(a)), _poly_trim(list(b))
    while b:
        b = _poly_monic(b, F)
        a, b = b, _poly_mod(a, b, F)
    return _poly_monic(a, F) if a else a


def _poly_div(a, g, F):
    a = list(a)
    d = len(g) - 1
    q = [0] * (len(a) - d)
    for i in range(len(a) - 1, d - 1, -1):
        c = a[i]
        if c:
            q[i - d] = c
            for k in range(d + 1):
                a[i - d + k] ^= F.mul(c, g[k])
    return q


def find_root(poly_terms: list[int], F: Field, rng: random.Random) -> int:
    """A root in F of the F_2-irreducible polynomial with these terms
    (Cantor-Zassenhaus with the absolute trace)."""
    g = [0] * (max(poly_terms) + 1)
    for t in poly_terms:
        g[t] = 1
    while len(g) > 2:
        delta = rng.getrandbits(F.m) or 1
        # T = sum_{i<m} (delta X)^(2^i) mod g
        cur = _poly_mod([0, delta], g, F) if len(g) > 2 else [0, delta]
        acc = list(cur)
        for _ in range(F.m - 1):
            sq = [0] * (2 * len(cur))
            for i, c in enumerate(cur):
                sq[2 * i] = F.sqr(c)
            cur = _poly_mod(sq, g, F)
            acc += [0] * (len(cur) - len(acc))
            for i, c in enumerate(cur):
                acc[i] ^= c
        h = _poly_gcd(g, _poly_trim(acc), F)
        if 1 < len(h) < len(g):
            other = _poly_monic(_poly_div(g, h, F), F)
            g = h if len(h) <= len(other) else other
    return g[0]  # X + g0 has root g0 in characteristic 2


def isomorphism(src_terms: list[int], F: Field, seed: int = 1):
    """Linear map from F_2[z]/(src) to F: z -> a root of src in F."""
    r = find_root(src_terms, F, random.Random(seed))
    images = [1]
    for _ in range(F.m - 1):
        images.append(F.mul(images[-1], r))

    def phi(a: int) -> int:
        out = 0
        i = 0
        while a:
            if a & 1:
                out ^= images[i]
            a >>= 1
            i += 1
        return out

    return phi


# --- normal basis ------------------------------------------------------------


def invert_gf2(rows: list[int], n: int) -> list[int]:
    """Inverse of an n x n GF(2) matrix given as row bit masks."""
    a = [(rows[i] | (1 << (n + i))) for i in range(n)]
    for col in range(n):
        piv = next((r for r in range(col, n) if a[r] >> col & 1), None)
        if piv is None:
            raise ValueError("singular")
        a[col], a[piv] = a[piv], a[col]
        for r in range(n):
            if r != col and a[r] >> col & 1:
                a[r] ^= a[col]
    return [row >> n for row in a]


def normal_basis(F: Field):
    """The first normal element beta (in counting order) and the rows R with
    coordinate_i(x) = parity(R[i] & x) for x = sum_i c_i beta^(2^i)."""
    m = F.m
    for beta in range(2, 1 << 20):
        cols = [beta]
        for _ in range(m - 1):
            cols.append(F.sqr(cols[-1]))
        # matrix N with N[r][i] = bit r of beta^(2^i); x = N c
        rows = [sum(((cols[i] >> r) & 1) << i for i in range(m)) for r in range(m)]
        try:
            inv = invert_gf2(rows, m)
        except ValueError:
            continue
        return beta, inv
    raise RuntimeError("no normal element")


def to_normal(x: int, rows: list[int]) -> int:
    return sum((bin(r & x).count("1") & 1) << i for i, r in enumerate(rows))


def min_rotation(v: int, m: int) -> tuple[int, int]:
    """Smallest cyclic rotation of an m-bit vector and the rotation count."""
    mask = (1 << m) - 1
    best, where = v, 0
    for s in range(1, m):
        r = ((v << s) | (v >> (m - s))) & mask
        if r < best:
            best, where = r, s
    return best, where


# --- the walk ------------------------------------------------------------------


def splitmix64(x: int) -> int:
    x = (x + 0x9E3779B97F4A7C15) & MASK64
    z = x
    z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & MASK64
    z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & MASK64
    return z ^ (z >> 31)


def start_exponents(seed: int, k: int, m: int) -> list[int]:
    return [splitmix64((seed * 16 + i) & MASK64) % m for i in range(k)]


def weight(x: int, rows) -> int:
    return bin(to_normal(x, rows)).count("1")


def walk_j(x: int, rows) -> int:
    return J_BASE + ((weight(x, rows) >> 1) % J_COUNT)


def step(E: Curve, P, rows):
    j = walk_j(P[0], rows)
    return E.add(P, E.frob(P, j)), j


def start_point(E: Curve, seed: int, Q, bases, m: int):
    R = Q
    for e, B in zip(start_exponents(seed, len(bases), m), bases):
        R = E.add(R, E.frob(B, e))
    return R


# --- F_2^m element <-> 32-bit words ------------------------------------------------


def to_words(a: int, nw: int) -> list[int]:
    return [(a >> (32 * i)) & 0xFFFFFFFF for i in range(nw)]


def from_words(ws) -> int:
    return sum(int(w) << (32 * i) for i, w in enumerate(ws))

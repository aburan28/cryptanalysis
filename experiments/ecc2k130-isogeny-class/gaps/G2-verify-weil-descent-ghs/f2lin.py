"""Own F_2 / F_{2^131} arithmetic and F_2 linear algebra for the G2 GHS audit.

Pure Python (no Sage, nothing from weil-descent-ghs/).  Field elements are ints,
bit i = coefficient of z^i, modulus z^131 + z^13 + z^2 + z + 1 (ECC2K-130 polynomial
basis).  Polynomials in F_2[x] are also ints (bit i = coefficient of x^i).
"""
import random

N_DEG = 131
MOD = (1 << 131) | (1 << 13) | (1 << 2) | (1 << 1) | 1
MASK = (1 << N_DEG) - 1


# ---------------------------------------------------------------- F_2[x] (carry-less)
def clmul(a, b):
    r = 0
    while b:
        if b & 1:
            r ^= a
        a <<= 1
        b >>= 1
    return r


def pdeg(a):
    return a.bit_length() - 1


def pdivmod(a, b):
    if b == 0:
        raise ZeroDivisionError
    q = 0
    db = pdeg(b)
    while a and pdeg(a) >= db:
        s = pdeg(a) - db
        q ^= 1 << s
        a ^= b << s
    return q, a


def pmod(a, b):
    return pdivmod(a, b)[1]


def pgcd(a, b):
    while b:
        a, b = b, pmod(a, b)
    return a


def plcm(a, b):
    g = pgcd(a, b)
    q, r = pdivmod(clmul(a, b), g)
    assert r == 0
    return q


def pmulmod(a, b, m):
    return pmod(clmul(a, b), m)


def ppowmod(a, e, m):
    r = 1
    a = pmod(a, m)
    while e:
        if e & 1:
            r = pmulmod(r, a, m)
        a = pmulmod(a, a, m)
        e >>= 1
    return r


def pstr(a, var="x"):
    if a == 0:
        return "0"
    terms = []
    for i in range(pdeg(a), -1, -1):
        if (a >> i) & 1:
            terms.append("1" if i == 0 else (var if i == 1 else f"{var}^{i}"))
    return " + ".join(terms)


def prime_factors(n):
    fs, d = [], 2
    while d * d <= n:
        if n % d == 0:
            fs.append(d)
            while n % d == 0:
                n //= d
        d += 1
    if n > 1:
        fs.append(n)
    return fs


def is_irreducible_f2(f):
    """Rabin's test over F_2: deg n irreducible iff x^(2^n) = x mod f and
    gcd(x^(2^(n/r)) - x, f) = 1 for every prime r | n."""
    n = pdeg(f)
    if n <= 0:
        return False
    x = 2

    def x_pow_2k(k):
        r = x
        for _ in range(k):
            r = pmulmod(r, r, f)
        return r
    if x_pow_2k(n) != pmod(x, f):
        return False
    for r in prime_factors(n):
        if pgcd(x_pow_2k(n // r) ^ pmod(x, f), f) != 1:
            return False
    return True


# ---------------------------------------------------------------- F_{2^131}
def fred(a):
    """reduce a carry-less product modulo MOD"""
    while a >> N_DEG:
        top = a >> N_DEG
        a &= MASK
        a ^= top ^ (top << 1) ^ (top << 2) ^ (top << 13)
    return a


def fmul(a, b):
    return fred(clmul(a, b))


# squaring spreads bits: bit i -> bit 2i
def fsqr(a):
    r = 0
    i = 0
    while a:
        if a & 1:
            r |= 1 << (2 * i)
        a >>= 1
        i += 1
    return fred(r)


def fsqr_k(a, k):
    for _ in range(k):
        a = fsqr(a)
    return a


def fsqrt(a):
    # sqrt = sigma^(n-1) since sigma^n = id
    return fsqr_k(a, N_DEG - 1)


def fpow(a, e):
    r = 1
    while e:
        if e & 1:
            r = fmul(r, a)
        a = fsqr(a)
        e >>= 1
    return r


def finv(a):
    if a == 0:
        raise ZeroDivisionError
    return fpow(a, (1 << N_DEG) - 2)


def ftrace(a):
    """absolute trace Tr_{F_q/F_2}(a) = sum_{i<131} a^(2^i); returns 0 or 1"""
    s = 0
    c = a
    for _ in range(N_DEG):
        s ^= c
        c = fsqr(c)
    assert s in (0, 1), "trace not in F_2 -- field arithmetic broken"
    return s


def conjugates(a, count=N_DEG):
    out = []
    c = a
    for _ in range(count):
        out.append(c)
        c = fsqr(c)
    return out


def half_trace(c):
    """for odd n: H(c) = sum_{i=0}^{(n-1)/2} c^(4^i); H(c)^2 + H(c) = c + Tr(c)"""
    s = 0
    u = c
    for _ in range((N_DEG - 1) // 2 + 1):
        s ^= u
        u = fsqr(fsqr(u))
    return s


# ---------------------------------------------------------------- F_2 linear algebra
class F2Basis:
    """Incremental Gaussian elimination over F_2 on int bit-vectors.
    Each stored row keeps a companion 'combination' bitmask recording which of the
    inserted vectors (by insertion index) XOR to it."""

    def __init__(self):
        self.rows = {}   # pivot bit -> (vector, combination)
        self.count = 0

    def reduce(self, v):
        comb = 0
        while v:
            p = v.bit_length() - 1
            if p in self.rows:
                rv, rc = self.rows[p]
                v ^= rv
                comb ^= rc
            else:
                return v, comb
        return 0, comb

    def insert(self, v):
        """returns (independent?, combination) ; if dependent, combination gives the
        set of previously inserted indices whose XOR equals v."""
        idx = self.count
        self.count += 1
        r, comb = self.reduce(v)
        if r == 0:
            return False, comb
        self.rows[r.bit_length() - 1] = (r, comb ^ (1 << idx))
        return True, None

    @property
    def rank(self):
        return len(self.rows)


def rank_f2(vectors):
    B = F2Basis()
    for v in vectors:
        B.insert(v)
    return B.rank


def ord_poly(c):
    """Ord_c: monic minimal P in F_2[x] with P(sigma)(c) = 0, via the Krylov space
    c, sigma(c), sigma^2(c), ...  Returns the polynomial as an int bitmask."""
    if c == 0:
        return 1
    B = F2Basis()
    v = c
    d = 0
    while True:
        indep, comb = B.insert(v)
        if not indep:
            # sigma^d(c) = sum_{i in comb} sigma^i(c)  ->  P = x^d + sum x^i
            return (1 << d) ^ comb
        v = fsqr(v)
        d += 1
        assert d <= N_DEG + 1


def apply_poly_sigma(P, c):
    """P(sigma)(c) for P in F_2[x]"""
    s = 0
    u = c
    i = 0
    while P >> i:
        if (P >> i) & 1:
            s ^= u
        u = fsqr(u)
        i += 1
    return s


def magic_number(sqrt_b):
    """m = dim_F2 Span{(1, sigma^i(sqrt b)) : 0 <= i < n} ; the '1' coordinate is
    bit 131 (above the 131 field bits)."""
    return rank_f2([(1 << N_DEG) | c for c in conjugates(sqrt_b)])


def ghs_genus_rule(m, ord_sqrt_b):
    """Menezes-Teske (Remark 2) / Hess Cor. 6 rule"""
    return 2 ** (m - 1) if pmod(ord_sqrt_b, 0b11) == 0 else 2 ** (m - 1) - 1


def hess_genus(ord1, ord2, trace_a=0):
    """Hess Theorem 5 / Menezes-Teske eq. (5): g = 2^t - 2^(t-s1) - 2^(t-s2) + 1"""
    L = plcm(ord1, ord2)
    if trace_a == 1:
        L = plcm(L, 0b11)
    t = pdeg(L)
    s1, s2 = pdeg(ord1), pdeg(ord2)
    return 2 ** t - 2 ** (t - s1) - 2 ** (t - s2) + 1, t, s1, s2


# ---------------------------------------------------------------- curve arithmetic
# E: y^2 + x y = x^3 + a x^2 + b ; points are (x, y) or None (= O)
def ec_on(P, a, b):
    if P is None:
        return True
    x, y = P
    return fsqr(y) ^ fmul(x, y) == fmul(fsqr(x), x) ^ fmul(a, fsqr(x)) ^ b


def ec_neg(P):
    if P is None:
        return None
    x, y = P
    return (x, x ^ y)


def ec_add(P, Q, a, b):
    if P is None:
        return Q
    if Q is None:
        return P
    x1, y1 = P
    x2, y2 = Q
    if x1 == x2:
        if y1 ^ y2 == x2:          # Q = -P
            return None
        return ec_dbl(P, a, b)
    lam = fmul(y1 ^ y2, finv(x1 ^ x2))
    x3 = fsqr(lam) ^ lam ^ x1 ^ x2 ^ a
    y3 = fmul(lam, x1 ^ x3) ^ x3 ^ y1
    return (x3, y3)


def ec_dbl(P, a, b):
    if P is None:
        return None
    x1, y1 = P
    if x1 == 0:
        return None
    lam = x1 ^ fmul(y1, finv(x1))
    x3 = fsqr(lam) ^ lam ^ a
    y3 = fsqr(x1) ^ fmul(lam ^ 1, x3)
    return (x3, y3)


def ec_mul(k, P, a, b):
    if k < 0:
        return ec_mul(-k, ec_neg(P), a, b)
    R = None
    Q = P
    while k:
        if k & 1:
            R = ec_add(R, Q, a, b)
        Q = ec_dbl(Q, a, b)
        k >>= 1
    return R


def ec_random_point(a, b, rng):
    """random affine point with x != 0: y = x w, w^2 + w = x + a + b/x^2"""
    while True:
        x = rng.getrandbits(N_DEG)
        if x == 0:
            continue
        c = x ^ a ^ fmul(b, finv(fsqr(x)))
        if ftrace(c) != 0:
            continue
        w = half_trace(c)
        assert fsqr(w) ^ w == c
        if rng.getrandbits(1):
            w ^= 1
        P = (x, fmul(x, w))
        assert ec_on(P, a, b)
        return P


def ec_frob(P):
    if P is None:
        return None
    return (fsqr(P[0]), fsqr(P[1]))

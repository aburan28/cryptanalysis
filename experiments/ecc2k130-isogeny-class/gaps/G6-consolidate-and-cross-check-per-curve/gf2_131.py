"""Pure-python GF(2^131) arithmetic, polynomial basis z^131 + z^13 + z^2 + z + 1.

Field elements are ints < 2^131, bit i = coefficient of z^i (same encoding as
ground_truth.json).  Written for G6 so the consolidated cross-checks do not rely
on Sage/NTL for the per-curve field identities (j*b = 1, Tr(b), GHS rank,
b + v + v^2 = 1, gamma1*gamma2 = sqrt(b), Frobenius labels, x-doubling cycles).
"""

N_BITS = 131
MOD = (1 << 131) | (1 << 13) | (1 << 2) | (1 << 1) | 1
MASK = (1 << 131) - 1


def reduce(x):
    # fold x = H*z^131 + L  ->  L + H*(z^13 + z^2 + z + 1); two folds suffice for deg < 262
    while x >> 131:
        h = x >> 131
        x = (x & MASK) ^ h ^ (h << 1) ^ (h << 2) ^ (h << 13)
    return x


def clmul(a, b):
    if a.bit_length() < b.bit_length():
        a, b = b, a
    r = 0
    # 4-bit window on b
    tbl = [0] * 16
    for i in range(1, 16):
        v = 0
        for k in range(4):
            if (i >> k) & 1:
                v ^= a << k
        tbl[i] = v
    shift = 0
    while b:
        r ^= tbl[b & 15] << shift
        b >>= 4
        shift += 4
    return r


def mul(a, b):
    return reduce(clmul(a, b))


_SPREAD = []
for _i in range(256):
    _v = 0
    for _k in range(8):
        if (_i >> _k) & 1:
            _v |= 1 << (2 * _k)
    _SPREAD.append(_v)


def sq(a):
    r = 0
    shift = 0
    while a:
        r |= _SPREAD[a & 255] << shift
        a >>= 8
        shift += 16
    return reduce(r)


def add(a, b):
    return a ^ b


def pow_(a, e):
    r = 1
    while e:
        if e & 1:
            r = mul(r, a)
        a = sq(a)
        e >>= 1
    return r


def inv(a):
    """inverse by the extended Euclidean algorithm in GF(2)[z]"""
    if a == 0:
        raise ZeroDivisionError("inverse of 0")
    u, v = a, MOD
    g1, g2 = 1, 0
    while u != 1:
        j = u.bit_length() - v.bit_length()
        if j < 0:
            u, v = v, u
            g1, g2 = g2, g1
            j = -j
        u ^= v << j
        g1 ^= g2 << j
    return reduce(g1)


def frob(a, k=1):
    for _ in range(k % 131):
        a = sq(a)
    return a


def sqrt(a):
    # sqrt(a) = a^(2^130)
    return frob(a, 130)


def _trace_slow(a):
    s = 0
    x = a
    for _ in range(131):
        s ^= x
        x = sq(x)
    assert s in (0, 1), "trace not in F_2"
    return s


TRMASK = 0
for _i in range(131):
    if _trace_slow(1 << _i):
        TRMASK |= 1 << _i


def trace(a):
    return bin(a & TRMASK).count("1") & 1


def gf2_rank(vectors):
    """rank over F_2 of a list of ints (bit vectors)"""
    basis = {}  # leading bit -> vector
    r = 0
    for v in vectors:
        while v:
            lb = v.bit_length() - 1
            if lb in basis:
                v ^= basis[lb]
            else:
                basis[lb] = v
                r += 1
                break
    return r


def conj_rank(a):
    """dim_F2 span{a^(2^i) : 0 <= i < 131} = degree of the F_2-linearised order Ord_a"""
    vs = []
    x = a
    for _ in range(131):
        vs.append(x)
        x = sq(x)
    return gf2_rank(vs)


def mq_magic_number(b):
    """Menezes-Qu magic number for y^2+xy=x^3+ax^2+b with a in F_2:
    m = dim_F2 span{(1, sqrt(b)^(2^i)) : 0 <= i < 131} (vectors in F_2 x F_q)."""
    s = sqrt(b)
    vs = []
    x = s
    for _ in range(131):
        vs.append((1 << 131) | x)   # prepend the constant-1 coordinate as bit 131
        x = sq(x)
    return gf2_rank(vs)


def selftest(rounds=200, seed=20260924):
    import random
    rnd = random.Random(seed)
    assert reduce(1 << 131) == (1 << 13) | 7
    for _ in range(rounds):
        a, b, c = (rnd.getrandbits(131) for _ in range(3))
        assert mul(a, b) == mul(b, a)
        assert mul(mul(a, b), c) == mul(a, mul(b, c))
        assert mul(a, b ^ c) == mul(a, b) ^ mul(a, c)
        assert sq(a) == mul(a, a)
        if a:
            assert mul(a, inv(a)) == 1
        assert frob(a, 131) == a
        assert sq(sqrt(a)) == a
        assert trace(a) == _trace_slow(a)
        assert trace(a ^ b) == trace(a) ^ trace(b)
    assert trace(1) == 1
    return True


if __name__ == "__main__":
    selftest()
    print("gf2_131 selftest ok; TRMASK popcount", bin(TRMASK).count("1"), "TRMASK", TRMASK)

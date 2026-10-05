"""Shared helpers for the toy analogues of the ECC2K-130 263-volcano.

Family = (a, n, l): E0 : y^2 + x y = x^3 + a x^2 + 1 over F_{2^n} (n prime), l an odd prime
dividing the Frobenius conductor f_n (t^2 - 4q = -7 f_n^2) that splits in Q(sqrt(-7)).
Field: polynomial basis F_2[z]/(z^n + tail), tail = the smallest odd integer (bitmask) that
makes z^n + tail irreducible.  Field elements are exchanged as integers (bit i = z^i).
"""
from sage.all import (GF, PolynomialRing, EllipticCurve, Integer, ZZ, factor, is_prime,
                      kronecker, matrix, vector, prime_range)
import json, os

WORK = '/Volumes/SSD990/ecdlp-hardness-work/toy-analogue-a'

FAMILIES = {
    # name: (a, n, l)
    'T11': (1, 11, 23),     # structural twin: l = 2n+1, 2 Frobenius orbits, lambda = -1
    'T19': (1, 19, 457),
    'T23': (0, 23, 967),     # a=0 so that E0[l] is rational over F_{q^21} (not F_{q^42})
    'T59': (0, 59, 5783),   # primary: N_n = 10063074221 (33.2 bits)
    'T109': (0, 109, 3271),  # large n: N_n = 30751236803477 (44.8 bits)
}

F2z = PolynomialRing(GF(2), 'z')


def int2poly(v):
    return F2z([(v >> i) & 1 for i in range(max(1, Integer(v).nbits()))])


def modulus_tail(n):
    r = 1
    zz = F2z.gen()
    while True:
        if (zz**n + int2poly(r)).is_irreducible():
            return r
        r += 2


def lucas_t(t1, m):
    tt = [Integer(2), Integer(t1)]
    for _ in range(2, m + 1):
        tt.append(t1 * tt[-1] - 2 * tt[-2])
    return tt[m]


def make_field(n, tail=None):
    if tail is None:
        tail = modulus_tail(n)
    zz = F2z.gen()
    K = GF(2**n, 'z', modulus=zz**n + int2poly(tail))
    return K, tail


def fe2int(u):
    return int(u.to_integer())


def int2fe(K, v):
    return K.from_integer(int(v))


def family_basics(name):
    a, n, l = FAMILIES[name]
    t1 = -1 if a == 0 else 1
    t = lucas_t(t1, n)
    q = Integer(2)**n
    card = q + 1 - t
    fac = factor(card)
    N = max(p for p, e in fac)
    h = card // N
    assert card % (N * N) != 0
    D = t * t - 4 * q
    f2 = -D // 7
    f = f2.isqrt()
    assert f * f == f2 and f % l == 0 and (f // l) % l != 0
    assert kronecker(-7, l) == 1 and is_prime(l) and is_prime(N)
    return dict(a=a, n=n, l=l, t1=t1, t=t, q=q, card=card, N=N, h=h, f=f,
                card_fac=str(fac), f_fac=str(factor(f)))


def tau_eigen(E, P, N, t1):
    """eigenvalue s of tau(x,y)=(x^2,y^2) on <P> (order N)."""
    R = PolynomialRing(GF(N), 'X')
    X = R.gen()
    tP = E(P[0]**2, P[1]**2)
    for s in (X**2 - t1 * X + 2).roots(multiplicities=False):
        if int(s) * P == tP:
            return Integer(s)
    raise ValueError('no eigenvalue')


def load_family(name):
    with open(os.path.join(WORK, 'data', f'{name}_family.json')) as fh:
        return json.load(fh)


def make_ext(K, n, k):
    """Absolute field L = F_{2^(n k)} with an explicit embedding emb: K -> L and its inverse
    `down` on emb(K), built by linear algebra in the tensor model K[u]/(g(u)) (g irreducible of
    degree k over F_2, gcd(n, k) = 1) with generator theta = z + u.  (Sage's any_root is far too
    slow for degree-2891 fields.)"""
    from sage.all import GF, Integer, PolynomialRing, matrix, vector, gcd
    if k == 1:
        return K, (lambda x: x), (lambda x: x)
    assert gcd(n, k) == 1
    F2 = GF(2)
    g = PolynomialRing(F2, 'u').irreducible_element(k)
    gl = [int(c) for c in g.list()]          # g = u^k + sum_{j<k} gl[j] u^j
    z = K.gen()
    D = n * k

    def tovec(el):                            # el = list of k elements of K (coeffs of u^j)
        bits = []
        for a in el:
            ai = int(a.to_integer())
            bits += [(ai >> i) & 1 for i in range(n)]
        return bits

    def mul_theta(el):                        # (sum a_j u^j) * (z + u) mod g(u)
        out = [a * z for a in el]
        carry = el[-1]                        # coefficient that lands on u^k
        for j in range(k - 1, 0, -1):
            out[j] += el[j - 1]
        # u^k = sum_{j<k} gl[j] u^j (char 2)
        for j in range(k):
            if gl[j]:
                out[j] += carry
        return out
    cur = [K(1)] + [K(0)] * (k - 1)
    rows = []
    for i in range(D):
        rows.append(tovec(cur))
        cur = mul_theta(cur)
    V = matrix(F2, rows)                      # row i = theta^i
    last = vector(F2, tovec(cur))             # theta^D
    p = V.solve_left(last)                    # theta^D = sum p_i theta^i
    R = PolynomialRing(F2, 'w')
    P = R.gen()**D + R([int(c) for c in p])
    assert P.is_irreducible(), 'theta does not generate'
    L = GF(Integer(2)**D, 'w', modulus=P)
    zvec = vector(F2, tovec([z] + [K(0)] * (k - 1)))
    cz = V.solve_left(zvec)
    zeta = L(R([int(c) for c in cz]))
    assert K.modulus()(zeta) == 0
    emb = K.hom([zeta], L)

    # rows of V as integers (bit j of row i = coordinate j of theta^i); down() is then an XOR
    # of the rows selected by the bits of y (y = sum c_i w^i  ->  sum c_i theta^i)
    Vrows = [sum(1 << j for j, bit in enumerate(r) if bit) for r in rows]
    maskn = (1 << n) - 1

    def down(y):
        yi = int(y.to_integer())
        tacc = 0
        i = 0
        while yi:
            if yi & 1:
                tacc ^= Vrows[i]
            yi >>= 1
            i += 1
        assert tacc >> n == 0, 'element not in K'
        return K.from_integer(tacc & maskn)
    return L, emb, down

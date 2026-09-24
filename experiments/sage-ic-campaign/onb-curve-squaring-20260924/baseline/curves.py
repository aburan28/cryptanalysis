# Koblitz curve y^2 + xy = x^3 + 1 over GF(2^m), group order, Frobenius
# eigenvalue, and the challenge / test instances.
#
# No type hints, camelCase identifiers, no itertools (project convention).

import field


def curveOrder(m):
    """#E(GF(2^m)) for y^2 + xy = x^3 + 1;  V_0 = 2, V_1 = -1, V_{k+1} = -V_k - 2 V_{k-1}."""
    v0, v1 = 2, -1
    for _ in range(m - 1):
        v0, v1 = v1, -v1 - 2 * v0
    return (1 << m) + 1 - v1


def isPrimeBig(n, rounds=48):
    if n < 2:
        return False
    smalls = [2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47]
    for p in smalls:
        if n % p == 0:
            return n == p
    d, r = n - 1, 0
    while d % 2 == 0:
        d //= 2
        r += 1
    import random as _r
    rng = _r.Random(12345)
    for _ in range(rounds):
        a = rng.randrange(2, n - 1)
        x = pow(a, d, n)
        if x == 1 or x == n - 1:
            continue
        ok = False
        for _ in range(r - 1):
            x = x * x % n
            if x == n - 1:
                ok = True
                break
        if not ok:
            return False
    return True


def sqrtMod(a, p):
    a %= p
    if a == 0:
        return 0
    if pow(a, (p - 1) // 2, p) != 1:
        return None
    q, s = p - 1, 0
    while q % 2 == 0:
        q //= 2
        s += 1
    z = 2
    while pow(z, (p - 1) // 2, p) != p - 1:
        z += 1
    m_, c, t, r = s, pow(z, q, p), pow(a, q, p), pow(a, (q + 1) // 2, p)
    while t != 1:
        i, tt = 0, t
        while tt != 1:
            tt = tt * tt % p
            i += 1
        b = pow(c, 1 << (m_ - i - 1), p)
        m_, c, t, r = i, b * b % p, t * b * b % p, r * b % p
    return r


class Curve:
    """Affine arithmetic on y^2 + xy = x^3 + 1 in the ONB model."""

    def __init__(self, onb):
        self.f = onb
        self.one = onb.one()

    def onCurve(self, p):
        if p is None:
            return True
        x, y = p
        return self.f.add(self.f.mul(y, y), self.f.mul(x, y)) == self.f.add(self.f.mul(self.f.mul(x, x), x), self.one)

    def neg(self, p):
        if p is None:
            return None
        x, y = p
        return (x, self.f.add(x, y))

    def dbl(self, p):
        if p is None:
            return None
        x, y = p
        if x == 0:
            return None
        f = self.f
        lam = f.add(x, f.mul(y, f.inv(x)))
        x3 = f.add(f.mul(lam, lam), lam)
        y3 = f.add(f.mul(x, x), f.mul(f.add(lam, self.one), x3))
        return (x3, y3)

    def add(self, p, q):
        if p is None:
            return q
        if q is None:
            return p
        f = self.f
        x1, y1 = p
        x2, y2 = q
        if x1 == x2:
            return self.dbl(p) if y1 == y2 else None
        d = f.add(x1, x2)
        lam = f.mul(f.add(y1, y2), f.inv(d))
        x3 = f.add(f.add(f.mul(lam, lam), lam), d)
        y3 = f.add(f.add(f.mul(lam, f.add(x1, x3)), x3), y1)
        return (x3, y3)

    def mul(self, p, k):
        r = None
        b = p
        while k:
            if k & 1:
                r = self.add(r, b)
            b = self.dbl(b)
            k >>= 1
        return r

    def frob(self, p, j=1):
        if p is None:
            return None
        x, y = p
        return (self.f.frob(x, j), self.f.frob(y, j))

    def halfTrace(self, a):
        """z with z^2 + z = a, valid for odd m when Tr(a) = 0."""
        f = self.f
        acc = a
        t = a
        for _ in range((f.m - 1) // 2):
            t = f.frob(t, 2)
            acc = f.add(acc, t)
        return acc

    def pointFromX(self, x):
        """Return (x, y) on the curve or None if x is not a valid abscissa."""
        f = self.f
        if x == 0:
            return None
        c = f.add(x, f.inv(f.mul(x, x)))     # x + 1/x^2
        if f.trace(c):
            return None
        z = self.halfTrace(c)
        y = f.mul(x, z)
        p = (x, y)
        assert self.onCurve(p)
        return p

    def randomPointOfOrder(self, ell, cofactor, rng):
        while True:
            x = self.f.randomElement(rng)
            p = self.pointFromX(x)
            if p is None:
                continue
            p = self.mul(p, cofactor)
            if p is None:
                continue
            assert self.mul(p, ell) is None
            return p


def frobeniusEigenvalue(curve, basePoint, ell):
    """s with sigma(R) = [s]R on the order-ell subgroup."""
    r = sqrtMod(-7 % ell, ell)
    if r is None:
        raise RuntimeError("sqrt(-7) does not exist mod ell")
    inv2 = pow(2, -1, ell)
    for cand in ((-1 + r) * inv2 % ell, (-1 - r) * inv2 % ell):
        if curve.mul(basePoint, cand) == curve.frob(basePoint, 1):
            return cand
    raise RuntimeError("no Frobenius eigenvalue matched")


def findTestCurves(mMin, mMax):
    """Small m with a type-II ONB and #E = 4 * prime."""
    out = []
    for m in range(mMin, mMax + 1):
        if not field.isPrime(m):
            continue
        n = 2 * m + 1
        if not field.isPrime(n):
            continue
        o = field.multiplicativeOrder(2, n)
        if o != m and o != 2 * m:
            continue
        order = curveOrder(m)
        if order % 4 != 0:
            continue
        ell = order // 4
        if not isPrimeBig(ell):
            continue
        out.append((m, ell))
    return out


def findIrreduciblePoly(m):
    """Lowest-weight irreducible polynomial of degree m over GF(2)."""
    def irreducible(p):
        xp = 2
        for _ in range(m // 2):
            s = 0
            c, i = xp, 0
            while c:
                if c & 1:
                    s |= 1 << (2 * i)
                c >>= 1
                i += 1
            xp = field.polyMod(s, p)
            if field.polyGcd(p, xp ^ 2) != 1:
                return False
        return True

    for k in range(1, m):
        p = (1 << m) | (1 << k) | 1
        if irreducible(p):
            return p, (k, -1, -1)
    for k3 in range(3, m):
        for k2 in range(2, k3):
            for k1 in range(1, k2):
                p = (1 << m) | (1 << k3) | (1 << k2) | (1 << k1) | 1
                if irreducible(p):
                    return p, (k3, k2, k1)
    raise RuntimeError("no low-weight irreducible found")


def basisImages(onb, pbPoly, m, rng):
    """Return (zToOnb, gammaToPb): images of the polynomial-basis generator
    powers z^i as ONB coordinate vectors, and of the ONB basis elements as
    polynomial-basis bit vectors."""
    w = field.findRootInOnb(onb, pbPoly, rng)
    zToOnb = []
    cur = onb.one()
    for _ in range(m):
        zToOnb.append(onb.toCoords(cur))
        cur = onb.mul(cur, w)
    # invert the m x m matrix over GF(2): columns are zToOnb
    rows = []
    for i in range(m):
        r = 0
        for j in range(m):
            if (zToOnb[j] >> i) & 1:
                r |= 1 << j
        rows.append((r, 1 << i))
    # Gauss-Jordan on [A | I]
    mat = []
    for i in range(m):
        mat.append([rows[i][0], rows[i][1]])
    piv = []
    for col in range(m):
        sel = -1
        for r in range(len(piv), m):
            if (mat[r][0] >> col) & 1:
                sel = r
                break
        if sel < 0:
            raise RuntimeError("change of basis is singular")
        mat[len(piv)], mat[sel] = mat[sel], mat[len(piv)]
        pr = mat[len(piv)]
        for r in range(m):
            if r != len(piv) and ((mat[r][0] >> col) & 1):
                mat[r][0] ^= pr[0]
                mat[r][1] ^= pr[1]
        piv.append(col)
    inv = [0] * m
    for r in range(m):
        col = -1
        for c in range(m):
            if (mat[r][0] >> c) & 1:
                col = c
                break
        inv[col] = mat[r][1]
    # inv[row] is row `row` of A^{-1} as a mask over its columns; the image of
    # the ONB basis element gamma_{j+1} is column j of A^{-1}.
    gammaToPb = []
    for j in range(m):
        v = 0
        for row in range(m):
            if (inv[row] >> j) & 1:
                v |= 1 << row
        gammaToPb.append(v)
    return w, zToOnb, gammaToPb


def findNormalBasis(pb, m, rng, tries=400):
    """Find a normal element of GF(2^m) in polynomial-basis representation and
    return (beta, rowsPbToNb, colsNbToPb).

    rowsPbToNb[i] is the bitmask of polynomial-basis coordinates whose parity
    gives normal-basis coordinate i, so the normal-basis weight of x is the
    popcount of applying those rows.  Among candidates the sparsest matrix
    wins, since that is what the generated linear map costs."""
    best = None
    for _ in range(tries):
        beta = rng.getrandbits(m)
        if beta == 0:
            continue
        conj = []
        cur = beta
        for _ in range(m):
            conj.append(cur)
            cur = pb.sqr(cur)
        inv = invertGf2Columns(conj, m)
        if inv is None:
            continue
        ones = 0
        for r in inv:
            ones += bin(r).count('1')
        if best is None or ones < best[0]:
            best = (ones, beta, inv, conj)
    if best is None:
        raise RuntimeError("no normal element found for m=%d" % m)
    return best[1], best[2], best[3]


def invertGf2Columns(cols, m):
    """Invert the m x m GF(2) matrix whose columns are `cols`; return its rows."""
    left = [0] * m
    right = [0] * m
    for i in range(m):
        r = 0
        for j in range(m):
            if (cols[j] >> i) & 1:
                r |= 1 << j
        left[i] = r
        right[i] = 1 << i
    row = 0
    for col in range(m):
        piv = -1
        for r in range(row, m):
            if (left[r] >> col) & 1:
                piv = r
                break
        if piv < 0:
            return None
        left[row], left[piv] = left[piv], left[row]
        right[row], right[piv] = right[piv], right[row]
        for r in range(m):
            if r != row and ((left[r] >> col) & 1):
                left[r] ^= left[row]
                right[r] ^= right[row]
        row += 1
    out = [0] * m
    for r in range(m):
        col = (left[r] & -left[r]).bit_length() - 1
        out[col] = right[r]
    return out


class CurvePb:
    """y^2 + xy = x^3 + 1 over a polynomial-basis GF(2^m)."""

    def __init__(self, pb):
        self.f = pb

    def onCurve(self, p):
        if p is None:
            return True
        x, y = p
        f = self.f
        return f.mul(y, y) ^ f.mul(x, y) == f.mul(f.mul(x, x), x) ^ 1

    def neg(self, p):
        return None if p is None else (p[0], p[0] ^ p[1])

    def dbl(self, p):
        if p is None or p[0] == 0:
            return None
        f = self.f
        x, y = p
        lam = x ^ f.mul(y, f.inv(x))
        x3 = f.mul(lam, lam) ^ lam
        y3 = f.mul(x, x) ^ f.mul(lam ^ 1, x3)
        return (x3, y3)

    def add(self, p, q):
        if p is None:
            return q
        if q is None:
            return p
        f = self.f
        x1, y1 = p
        x2, y2 = q
        if x1 == x2:
            return self.dbl(p) if y1 == y2 else None
        d = x1 ^ x2
        lam = f.mul(y1 ^ y2, f.inv(d))
        x3 = f.mul(lam, lam) ^ lam ^ d
        y3 = f.mul(lam, x1 ^ x3) ^ x3 ^ y1
        return (x3, y3)

    def mul(self, p, k):
        r = None
        b = p
        while k:
            if k & 1:
                r = self.add(r, b)
            b = self.dbl(b)
            k >>= 1
        return r

    def frob(self, p, j=1):
        if p is None:
            return None
        x, y = p
        for _ in range(j):
            x, y = self.f.sqr(x), self.f.sqr(y)
        return (x, y)

    def halfTrace(self, a):
        acc = a
        t = a
        for _ in range((self.f.m - 1) // 2):
            t = self.f.sqr(self.f.sqr(t))
            acc ^= t
        return acc

    def trace(self, a):
        t = a
        acc = a
        for _ in range(self.f.m - 1):
            t = self.f.sqr(t)
            acc ^= t
        return acc & 1

    def pointFromX(self, x):
        if x == 0:
            return None
        f = self.f
        c = x ^ f.inv(f.mul(x, x))
        if self.trace(c):
            return None
        z = self.halfTrace(c)
        p = (x, f.mul(x, z))
        assert self.onCurve(p)
        return p

    def randomPointOfOrder(self, ell, cofactor, rng):
        while True:
            x = rng.getrandbits(self.f.m)
            p = self.pointFromX(x)
            if p is None:
                continue
            p = self.mul(p, cofactor)
            if p is None:
                continue
            assert self.mul(p, ell) is None
            return p

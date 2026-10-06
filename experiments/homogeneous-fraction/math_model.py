import random
from array import array
class GF2n:
    def __init__(self, n, modulus):
        self.n, self.modulus, self.mask = n, modulus, (1 << n) - 1
        assert modulus >> n == 1 and modulus & 1

    def mul(self, a, b):
        out = 0
        while b:
            if b & 1:
                out ^= a
            b >>= 1
            a <<= 1
            if a >> self.n:
                a ^= self.modulus
        return out

    def sq(self, a):
        return self.mul(a, a)

    def power(self, a, exponent):
        result = 1
        while exponent:
            if exponent & 1:
                result = self.mul(result, a)
            a = self.sq(a)
            exponent >>= 1
        return result

    def inv(self, a):
        assert a
        return self.power(a, (1 << self.n) - 2)

    def s3(self, x, y, z):
        return self.sq(self.mul(x, y) ^ self.mul(x, z) ^ self.mul(y, z)) ^ self.mul(self.mul(x, y), z) ^ 1

    def s4(self, x, y, z, target):
        a, b = self.sq(x ^ y), self.mul(x, y)
        c = self.sq(b) ^ 1
        d, e = self.sq(z ^ target), self.mul(z, target)
        f = self.sq(e) ^ 1
        return self.sq(self.mul(a, f) ^ self.mul(c, d)) ^ self.mul(self.mul(a, e) ^ self.mul(b, d), self.mul(b, f) ^ self.mul(c, e))

    def s4_cleared(self, pairs, target):
        (n1, d1), (n2, d2), (n3, d3) = pairs
        a = self.sq(self.mul(n1, d2) ^ self.mul(n2, d1))
        b = self.mul(self.mul(n1, n2), self.mul(d1, d2))
        c = self.sq(self.mul(n1, n2)) ^ self.sq(self.mul(d1, d2))
        dd = self.sq(n3 ^ self.mul(target, d3))
        e = self.mul(self.mul(n3, target), d3)
        f = self.sq(self.mul(n3, target)) ^ self.sq(d3)
        return self.sq(self.mul(a, f) ^ self.mul(c, dd)) ^ self.mul(self.mul(a, e) ^ self.mul(b, dd), self.mul(b, f) ^ self.mul(c, e))

    def all_points(self):
        artin_schreier = {}
        for z in range(1 << self.n):
            artin_schreier.setdefault(self.sq(z) ^ z, z)
        result = [(0, 1)]
        for x in range(1, 1 << self.n):
            z = artin_schreier.get(x ^ self.inv(self.sq(x)))
            if z is not None:
                y = self.mul(x, z)
                result += [(x, y), (x, y ^ x)]
        return result

    def add(self, p, q):
        if p is None:
            return q
        if q is None:
            return p
        x, y = p
        xx, yy = q
        if x == xx:
            if (y ^ yy) == x or x == 0:
                return None
            slope = x ^ self.mul(y, self.inv(x))
            xxx = self.sq(slope) ^ slope
            return xxx, self.sq(x) ^ self.mul(slope ^ 1, xxx)
        slope = self.mul(y ^ yy, self.inv(x ^ xx))
        xxx = self.sq(slope) ^ slope ^ x ^ xx
        return xxx, self.mul(slope, x ^ xxx) ^ xxx ^ y


class FastGF2n(GF2n):
    """GF(2^n) arithmetic with a compact nibble multiplication table.

    This is an exact arithmetic backend for small fields used while expanding
    large Boolean polynomials.  It keeps only 64 products per field element
    (rather than a full q-by-q table), then multiplies with four lookups and
    XORs.  Fields above 16 bits retain the reference implementation.
    """

    def __init__(self, n, modulus):
        super().__init__(n, modulus)
        self._mul_nibbles = None
        if n > 16:
            return
        q = 1 << n
        table = array("H", [0]) * (q * 64)
        for a in range(q):
            powers = []
            value = a
            for _ in range(n):
                powers.append(value)
                value <<= 1
                if value >> n:
                    value ^= modulus
            offset = a * 64
            for chunk in range(4):
                start = 4 * chunk
                for nibble in range(16):
                    product = 0
                    for bit in range(4):
                        power = start + bit
                        if nibble & (1 << bit) and power < n:
                            product ^= powers[power]
                    table[offset + chunk * 16 + nibble] = product
        self._mul_nibbles = table

    def mul(self, a, b):
        table = self._mul_nibbles
        if table is None or (a | b) & ~self.mask:
            return super().mul(a, b)
        offset = a * 64
        product = 0
        for chunk in range(4):
            product ^= table[offset + chunk * 16 + ((b >> (4 * chunk)) & 15)]
        return product


def symbolic_anf(field, omega, k, target):
    """Expand the cleared S4 directly in the Boolean quotient over GF(2^n)."""
    width = 2 * (k + 1)

    def add(a, b):
        out = a.copy()
        for monomial, coeff in b.items():
            out[monomial] = out.get(monomial, 0) ^ coeff
            if not out[monomial]:
                del out[monomial]
        return out

    def mul(a, b):
        out = {}
        for am, ac in a.items():
            for bm, bc in b.items():
                monomial = am | bm  # boolean variables obey bit^2 = bit
                out[monomial] = out.get(monomial, 0) ^ field.mul(ac, bc)
        return {monomial: coeff for monomial, coeff in out.items() if coeff}

    def sq(a):
        return {monomial: field.sq(coeff) for monomial, coeff in a.items()}

    pairs = []
    for block in range(3):
        nval, dval = {}, {}
        for j in range(k + 1):
            nval[1 << (width * block + j)] = field.power(omega, j)
            dval[1 << (width * block + k + 1 + j)] = field.power(omega, j)
        pairs.append((nval, dval))

    (n1, d1), (n2, d2), (n3, d3) = pairs
    t = {0: target}
    one = {0: 1}
    a = sq(add(mul(n1, d2), mul(n2, d1)))
    b = mul(mul(n1, n2), mul(d1, d2))
    c = add(sq(mul(n1, n2)), sq(mul(d1, d2)))
    dd = sq(add(n3, mul(t, d3)))
    e = mul(mul(n3, t), d3)
    f = add(sq(mul(n3, t)), sq(d3))
    out = add(sq(add(mul(a, f), mul(c, dd))),
              mul(add(mul(a, e), mul(b, dd)), add(mul(b, f), mul(c, e))))
    assert mul(one, out) == out
    # Validate this symbolic expansion against independent field arithmetic.
    rng = random.Random(235 + k)
    for _ in range(100):
        bits = rng.getrandbits(width * 3)
        symbolic_value = 0
        for mask, coeff in out.items():
            if mask & bits == mask:
                symbolic_value ^= coeff
        numerical_pairs = []
        for i in range(3):
            block = (bits >> (width * i)) & ((1 << width) - 1)
            num = 0
            den = 0
            for j in range(k + 1):
                if block & (1 << j):
                    num ^= field.power(omega, j)
                if block & (1 << (k + 1 + j)):
                    den ^= field.power(omega, j)
            numerical_pairs.append((num, den))
        assert symbolic_value == field.s4_cleared(numerical_pairs, target)

    return out

"""Independent Python field arithmetic using linear tables and integer packing.

All tables depend only on the public field. No target values are cached. The
packed product is ordinary Python integer multiplication followed by exact
coefficient parity extraction and polynomial reduction. No native producer
arithmetic is called. Degree <= 255 ensures every integer convolution
coefficient is below 256, so base-256 coefficient slots cannot carry.
"""
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.append(str(HERE.parent.parent / 'pdp-scaling'))
sys.path.append(str(HERE.parent / 'round63'))
from gf2n import GF2n, Curve, _pmod, _pmulmod, is_irreducible
from curve_replay import PublicReplay


def linear_table(images):
    table = [0] * 256
    for byte in range(1, 256):
        low = byte & -byte
        table[byte] = table[byte ^ low] ^ images[low.bit_length() - 1]
    return tuple(table)


class SquareField(GF2n):
    """Replace binary squaring by a prepared linear map, keeping reference mul."""
    def __init__(self, n, mod):
        if type(n) is not int or not 1 <= n <= 255:
            raise ValueError('prepared field degrees must be in 1..255')
        if type(mod) is not int or mod <= 0 or mod.bit_length() != n + 1 or not is_irreducible(mod):
            raise ValueError('invalid field modulus')
        super().__init__(n, mod)
        self._limit = 1 << n
        self._mask = self._limit - 1
        self._squares = tuple(linear_table([_pmod(1 << (2 * (8 * i + bit)), mod)
                                           for bit in range(8)])
                              for i in range((n + 7) // 8))

    def _element(self, a):
        if type(a) is not int or not 0 <= a < self._limit:
            raise ValueError('noncanonical field element')

    def sqr(self, a):
        self._element(a)
        result = 0
        for row in self._squares:
            result ^= row[a & 255]
            a >>= 8
        return result


class PackedBits:
    """Exact coefficient packing; degree limit includes the carry bound."""
    def __init__(self, n):
        if type(n) is not int or not 1 <= n <= 255:
            raise ValueError('base-256 packing requires 1..255 input coefficients')
        width = 1 << (n - 1).bit_length()
        pack, block = [], width // 2
        while block:
            mask = sum(((1 << block) - 1) << (8 * i) for i in range(0, width, block))
            pack.append((7 * block, mask))
            block //= 2
        capacity = 2 * width
        unpack, block = [], 2
        while block <= capacity:
            mask = sum(((1 << block) - 1) << (8 * i) for i in range(0, capacity, block))
            unpack.append((7 * (block // 2), mask))
            block *= 2
        self.n = n
        self.pack_steps = tuple(pack)
        self.unpack_steps = tuple(unpack)
        self.parity_mask = sum(1 << (8 * i) for i in range(capacity))

    def pack(self, a):
        for shift, mask in self.pack_steps:
            a = (a | (a << shift)) & mask
        return a

    def parity(self, product):
        product &= self.parity_mask
        for shift, mask in self.unpack_steps:
            product = (product | (product >> shift)) & mask
        return product

    def product(self, a, b):
        if any(type(v) is not int or not 0 <= v < 1 << self.n for v in (a, b)):
            raise ValueError('operand exceeds the declared coefficient count')
        return self.parity(self.pack(a) * self.pack(b))


class PackedField(SquareField):
    def __init__(self, n, mod):
        super().__init__(n, mod)
        self._bits = PackedBits(n)
        self._reductions = tuple(linear_table([_pmod(1 << (n + 8 * i + bit), mod)
                                              for bit in range(8)])
                                 for i in range((n - 1 + 7) // 8))

    def mul(self, a, b):
        self._element(a)
        self._element(b)
        if not a or not b:
            return 0
        if a < b:
            a, b = b, a
        if b == 1:
            return a
        # A <=4-bit multiplier needs at most four simple reference iterations.
        # Commutativity selects the smaller operand; no target data is cached.
        if b < 16:
            return _pmulmod(a, b, self.mod)
        bits = self._bits
        product = bits.parity(bits.pack(a) * bits.pack(b))
        result, high = product & self._mask, product >> self.n
        for row in self._reductions:
            result ^= row[high & 255]
            high >>= 8
        return result


class PreparedReplay(PublicReplay):
    """Unchanged witness identities with a separately implemented field kernel."""
    def __init__(self, n, mod, b, mode):
        if mode not in ('squares', 'packed'):
            raise ValueError('unknown checker arithmetic')
        super().__init__(n, mod, b)
        self.F = (SquareField if mode == 'squares' else PackedField)(n, mod)
        self.E = Curve(self.F, b)

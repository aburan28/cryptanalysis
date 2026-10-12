"""Independent polynomial inversion; no native solver, points, or answer cache.

Each XOR subtraction cancels a leading polynomial term. The invariants are
u = g*a (mod modulus), v = h*a (mod modulus). Swaps preserve them; cancelling
u's leading term strictly decreases deg(u)+deg(v). For a nonzero element of
the validated field, gcd(a, modulus)=1, so u eventually equals one and g is
the inverse. The final reduction selects the canonical field representative.

This specializes polynomial extended Euclid to GF(2), where subtraction is
XOR. See Handbook of Applied Cryptography, section 2.6.2, algorithm 2.221.
"""
from pathlib import Path
import sys

_path = sys.path[:]
try:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]/'pdp-scaling'))
    from gf2n import GF2n
finally:
    sys.path[:] = _path


class EuclidField(GF2n):
    """Preserve the reference field; replace only inversion of canonical ints."""
    def inv(self, a):
        if type(a) is not int or not 0 <= a < 1 << self.n:
            raise ValueError('inverse requires a canonical field integer')
        if a == 0:
            raise ZeroDivisionError('zero has no field inverse')
        u, v, g, h = a, self.mod, 1, 0
        while u != 1:
            if u == 0:
                raise ZeroDivisionError('element and modulus are not coprime')
            shift = u.bit_length()-v.bit_length()
            if shift < 0:
                u, v, g, h, shift = v, u, h, g, -shift
            u ^= v << shift
            g ^= h << shift
        while g.bit_length() > self.n:
            g ^= self.mod << (g.bit_length()-self.n-1)
        return g

"""Weil descent of the point decomposition problem

    S_{m+1}(x_1, ..., x_m, x(R)) = 0,     x_i in V = span{1, z, ..., z^(l-1)}

to a system of n Boolean equations in the m*l coordinates v_{i,j} of the
x_i (x_i = sum_j v_{i,j} z^j).  Since v^2 = v over F_2, x_i^(2^k) is
F_2-linear in the v_{i,j}, so a monomial x_1^e_1 ... x_m^e_m descends to a
product of sum_i wt(e_i) linear forms.  The descent is organised as a
staged tensor contraction: the F_{2^n} coefficient tensor c[e_1..e_m] of
S_{m+1} (with x(R) and b substituted) is contracted one index at a time
with the "block" polynomials that descend x_i^e.

The result is one polynomial in the v's with coefficients in F_{2^n},
stored as {monomial bitmask: coefficient}; bit t of every coefficient is
Boolean equation number t.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

import sumpoly
from gf2n import Curve, GF2n, Point


class MulTable:
    """Multiplication by a fixed a in F_{2^n}, byte-sliced."""

    def __init__(self, F: GF2n, a: int):
        self.nbytes = (F.n + 7) // 8
        self.t = []
        for k in range(self.nbytes):
            shifted = F.mul(a, 1 << (8 * k))
            row = [0] * 256
            for byte in range(1, 256):
                acc = 0
                bb = byte
                s = shifted
                while bb:
                    if bb & 1:
                        acc ^= s
                    bb >>= 1
                    s = F.mul(s, 2)
                row[byte] = acc
            self.t.append(row)

    def __call__(self, x: int) -> int:
        r = 0
        for k in range(self.nbytes):
            r ^= self.t[k][(x >> (8 * k)) & 0xFF]
        return r


def block_polys(F: GF2n, l: int, max_e: int) -> list[dict[int, int]]:
    """blk[e] = descent of x^e for x = sum_{j<l} v_j z^j, as {mask over the l v_j: coeff}."""
    out: list[dict[int, int]] = []
    for e in range(max_e + 1):
        poly = {0: 1}
        k = 0
        ee = e
        while ee:
            if ee & 1:
                lin = [(1 << j, F.frob(1 << j, k)) for j in range(l)]  # (z^j)^(2^k)
                nxt: dict[int, int] = {}
                for mask, c in poly.items():
                    for vm, zc in lin:
                        nm = mask | vm
                        nxt[nm] = nxt.get(nm, 0) ^ F.mul(c, zc)
                poly = {mk: c for mk, c in nxt.items() if c}
            ee >>= 1
            k += 1
        out.append(poly)
    return out


@dataclass
class Instance:
    n: int
    mod: int
    b: int
    m: int
    l: int
    xR: int
    anf: dict[int, int]  # mask -> coefficient in F_{2^n}
    planted: int  # mask of the planted solution (bit i*l+j = v_{i,j})
    points: list[Point]  # the planted factor-base points

    @property
    def nvars(self) -> int:
        return self.m * self.l

    def equations(self) -> list[set[int]]:
        eqs: list[set[int]] = [set() for _ in range(self.n)]
        for mask, c in self.anf.items():
            t = 0
            while c:
                if c & 1:
                    eqs[t].add(mask)
                c >>= 1
                t += 1
        return eqs

    def evaluate(self, v: int) -> int:
        acc = 0
        for mask, c in self.anf.items():
            if mask & ~v == 0:
                acc ^= c
        return acc

    def x_from_assignment(self, v: int) -> list[int]:
        return [(v >> (i * self.l)) & ((1 << self.l) - 1) for i in range(self.m)]


def descend(
    S: dict[int, frozenset], F: GF2n, E: Curve, m: int, l: int, xR: int
) -> dict[int, int]:
    p = S[m + 1]
    max_e = 2 ** (m - 1)
    # coefficient tensor over (e_1..e_m), with x_{m+1} = xR and b substituted
    c: dict[tuple[int, ...], int] = {}
    for mono in p:
        key = tuple(mono[:m])
        val = F.mul(F.pow(xR, mono[m]), F.pow(E.b, mono[sumpoly.B]))
        c[key] = c.get(key, 0) ^ val
    c = {k: v for k, v in c.items() if v}

    blk = block_polys(F, l, max_e)
    tables = {
        e: {mask: MulTable(F, coef) for mask, coef in blk[e].items()}
        for e in range(max_e + 1)
    }

    # stage i contracts e_i:  A[(mask, rest)] with mask over the first i blocks
    A: dict[tuple[int, tuple[int, ...]], int] = {(0, k): v for k, v in c.items()}
    for i in range(m):
        nxt: dict[tuple[int, tuple[int, ...]], int] = {}
        shift = i * l
        for (mask, rest), val in A.items():
            e, rest2 = rest[0], rest[1:]
            for bm, tab in tables[e].items():
                key = (mask | (bm << shift), rest2)
                nxt[key] = nxt.get(key, 0) ^ tab(val)
        A = {k: v for k, v in nxt.items() if v}
    return {mask: val for (mask, _), val in A.items()}


def make_instance(
    n: int, m: int, l: int, seed: int, b: int | None = 1, build_anf: bool = True
) -> Instance:
    """A PDP instance with a planted decomposition R = P_1 + ... + P_m, P_i in F_V.

    b = 1 is the Koblitz curve; b = None draws a random curve coefficient.
    build_anf=False skips the descent (for engines that work on the points).
    """
    rng = random.Random(seed)
    F = GF2n(n)
    if b is None:
        b = F.random(rng) or 1
    E = Curve(F, b)
    S = sumpoly.load(m + 1) if build_anf else {}
    while True:
        pts = [E.random_factor_base_point(l, rng) for _ in range(m)]
        R = E.sum(pts)
        if not R.inf and len({P.x for P in pts}) == m:
            break
    anf = descend(S, F, E, m, l, R.x) if build_anf else {}
    planted = 0
    for i, P in enumerate(pts):
        planted |= P.x << (i * l)
    inst = Instance(
        n=n, mod=F.mod, b=b, m=m, l=l, xR=R.x, anf=anf, planted=planted, points=pts
    )
    if build_anf:
        assert inst.evaluate(planted) == 0, (
            "planted solution does not satisfy the descended system"
        )
    return inst


def verify_solution(inst: Instance, v: int) -> bool:
    """Does assignment v give x_i that lift to points summing to R up to signs?"""
    if inst.evaluate(v) != 0:
        return False
    F = GF2n(inst.n, inst.mod)
    E = Curve(F, inst.b)
    xs = inst.x_from_assignment(v)
    pts = []
    for x in xs:
        P = E.lift_x(x)
        if P is None:
            return False
        pts.append(P)
    R = E.sum(inst.points)
    for signs in range(1 << inst.m):
        Q = E.sum([E.neg(P) if (signs >> i) & 1 else P for i, P in enumerate(pts)])
        if Q.x == R.x and not Q.inf:
            return True
    return False


if __name__ == "__main__":
    import sys
    import time

    n, m, l = (int(a) for a in sys.argv[1:4])
    t0 = time.time()
    inst = make_instance(n, m, l, seed=1)
    eqs = inst.equations()
    print(
        f"n={n} m={m} l={l}: {inst.nvars} variables, {len(inst.anf)} monomials, "
        f"max degree {max(k.bit_count() for k in inst.anf)}, "
        f"{sum(len(e) for e in eqs) / len(eqs):.0f} monomials per equation, "
        f"built in {time.time() - t0:.1f}s"
    )

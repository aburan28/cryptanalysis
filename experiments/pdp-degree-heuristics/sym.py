"""The symmetric formulation of the PDP: unknowns are the elementary symmetric functions.

S_{m+1}(x_1, ..., x_m, X) is symmetric in the x_i, so it is a polynomial in
e_k = sigma_k(x_1, ..., x_m).  With x_i in V, e_k lies in V^(k), the span of k-fold
products; writing e_k = sum_j u_{k,j} b_{k,j} over a basis of V^(k) and descending gives
n Boolean equations in N_e = sum_k dim V^(k) unknowns (FPPR / Petit-Quisquater; the core
of the WDSat model in pdp-scaling/symmodel.py).  The factor base therefore sets the size
of this system directly, through its product profile.

A solution (e_1, ..., e_m) is a decomposition only if T^m + e_1 T^(m-1) + ... + e_m splits
with all roots in V; `split` finds the roots by evaluating on V and returns the x-tuple.
For m = 2 the equations are linear (e_1^2 X^2 + e_2 X + e_2^2 + b), so the whole difficulty
is the 2^(N_e - rank) solutions that must be split: N_e = dim V + dim V^(2) = omega - 1.
"""

from __future__ import annotations

import itertools
from collections import defaultdict

import numpy as np

import factor_base as fbmod
from descent import BooleanSystem, _block_polys, summation_polynomial
from factor_base import FactorBase

try:
    import sumpoly
except ImportError:  # pragma: no cover - descent puts pdp-scaling on sys.path
    raise


def _poly_mul(p: dict, q: dict) -> dict:
    out: dict = defaultdict(int)
    for a, ca in p.items():
        for b, cb in q.items():
            out[tuple(x + y for x, y in zip(a, b))] ^= ca & cb
    return {k: 1 for k, v in out.items() if v}


def _elementary(m: int) -> list[dict]:
    """e_1 .. e_m as polynomials in x_1..x_m over F_2 ({exponent tuple: 1})."""
    es = []
    for k in range(1, m + 1):
        poly = {}
        for S in itertools.combinations(range(m), k):
            poly[tuple(1 if i in S else 0 for i in range(m))] = 1
        es.append(poly)
    return es


def symmetrize(m: int) -> dict[tuple[int, ...], int]:
    """S_{m+1} as {(a_1..a_m, e_X, e_b): 1}: e_1^a_1 ... e_m^a_m X^e_X b^e_b."""
    S = summation_polynomial(m + 1)
    es = _elementary(m)
    cache: dict[tuple[int, ...], dict] = {}

    def e_mono(a: tuple[int, ...]) -> dict:
        if a not in cache:
            p = {(0,) * m: 1}
            for k, ak in enumerate(a):
                base, e = es[k], ak
                acc = {(0,) * m: 1}
                while e:
                    if e & 1:
                        acc = _poly_mul(acc, base)
                    e >>= 1
                    if e:
                        base = {tuple(2 * x for x in mono): 1 for mono in base}  # squaring over F_2
                p = _poly_mul(p, acc)
            cache[a] = p
        return cache[a]

    groups: dict[tuple[int, int], set] = defaultdict(set)
    for mono in S:
        groups[(mono[m], mono[sumpoly.B])] ^= {tuple(mono[:m])}
    out: dict[tuple[int, ...], int] = {}
    for (ex, eb), monos in groups.items():
        cur = set(monos)
        while cur:
            lead = max(cur, key=lambda t: tuple(sorted(t, reverse=True)))
            lam = sorted(lead, reverse=True) + [0]
            a = tuple(lam[k] - lam[k + 1] for k in range(m))
            out[a + (ex, eb)] = out.get(a + (ex, eb), 0) ^ 1
            cur ^= set(e_mono(a))
    return {k: 1 for k, v in out.items() if v}


def product_bases(K, basis: list[int], m: int) -> list[list[int]]:
    """Echelon bases of V^(1), ..., V^(m)."""
    out = [fbmod.reduce_basis(basis)]
    for _ in range(2, m + 1):
        out.append(fbmod.reduce_basis(K.mul(p, v) for p in out[-1] for v in basis))
    return out


class SymPieces:
    """Target-independent descent of the symmetrized S_{m+1} over the bases of V^(k)."""

    formulation = "symmetric_e"

    def __init__(self, fb: FactorBase, m: int):
        self.fb, self.m = fb, m
        K = fb.curve.K
        self.bases = product_bases(K, fb.basis, m)
        self.dims = [len(b) for b in self.bases]
        self.offsets = [sum(self.dims[:k]) for k in range(m)]
        self.N = sum(self.dims)
        if self.N > 31:
            raise ValueError(f"symmetric system has {self.N} unknowns (> 31)")
        sym = symmetrize(m)
        max_a = [max(key[k] for key in sym) for k in range(m)]
        blks = [_block_polys(K, self.bases[k], max_a[k]) for k in range(m)]
        by_power: dict[int, dict[tuple[int, ...], int]] = defaultdict(dict)
        for key in sym:
            a, ex, eb = key[:m], key[m], key[m + 1]
            c = K.pow(fb.curve.b, eb)
            by_power[ex][a] = by_power[ex].get(a, 0) ^ c
        pieces: dict[int, dict[int, int]] = {}
        for j, terms in sorted(by_power.items()):
            A: dict[tuple[int, tuple[int, ...]], int] = {(0, a): v for a, v in terms.items() if v}
            for k in range(m):
                nxt: dict[tuple[int, tuple[int, ...]], int] = {}
                shift = self.offsets[k]
                for (mask, rest), val in A.items():
                    e, rest2 = rest[0], rest[1:]
                    for bm, bc in blks[k][e].items():
                        key = (mask | (bm << shift), rest2)
                        nxt[key] = nxt.get(key, 0) ^ K.mul(val, bc)
                A = {kk: v for kk, v in nxt.items() if v}
            pieces[j] = {mask: v for (mask, _), v in A.items()}
        self.powers = sorted(pieces)
        allmasks = sorted(set().union(*[set(p) for p in pieces.values()]))
        self.masks = np.array(allmasks, dtype=np.uint32)
        self.piece_pos, self.piece_coeffs = [], []
        for j in self.powers:
            items = sorted(pieces[j].items())
            self.piece_pos.append(np.searchsorted(self.masks, np.array([a for a, _ in items], dtype=np.uint32)))
            self.piece_coeffs.append(np.array([b for _, b in items], dtype=np.uint64))
        self.degree = int(max(bin(int(a)).count("1") for a in allmasks)) if allmasks else 0
        self.sym_terms = len(sym)

    # the descent.Pieces interface
    def coefficients(self, xR: int) -> np.ndarray:
        K = self.fb.curve.K
        acc = np.zeros(len(self.masks), dtype=np.uint64)
        for j, pos, coeffs in zip(self.powers, self.piece_pos, self.piece_coeffs):
            acc[pos] ^= K.mul_const(coeffs, K.pow(xR, j))
        return acc

    def system(self, xR: int) -> BooleanSystem:
        return BooleanSystem(self.N, self.fb.curve.n, self.masks, self.coefficients(xR))

    def structure(self) -> dict:
        from descent import Pieces

        st = Pieces.structure(self)  # same definitions over this formulation's pieces
        return {**st, "sym_dims": self.dims, "sym_unknowns": self.N, "sym_terms": self.sym_terms}

    def coordinate_functions(self) -> list[int]:
        from descent import Pieces

        return Pieces.coordinate_functions(self)

    # ------------------------------------------------------------------ splitting
    def e_values(self, v: int) -> list[int]:
        out = []
        for k in range(self.m):
            acc = 0
            bits = (v >> self.offsets[k]) & ((1 << self.dims[k]) - 1)
            for j, b in enumerate(self.bases[k]):
                if (bits >> j) & 1:
                    acc ^= b
            out.append(acc)
        return out

    def split(self, v: int) -> list[int] | None:
        """x_1..x_m in V with sigma_k(x) = e_k for the e-solution v, or None."""
        K = self.fb.curve.K
        es = self.e_values(v)
        T = self.fb.elements
        acc = np.ones(len(T), dtype=np.uint64)
        for e in es:
            acc = K.mul_vec(acc, T) ^ np.uint64(e)
        roots = [int(x) for x in T[acc == 0]]
        if not roots:
            return None
        for combo in itertools.combinations_with_replacement(roots, self.m):
            if set(combo) != set(roots) and len(roots) <= self.m:
                continue
            sig = [0] * (self.m + 1)
            sig[0] = 1
            for x in combo:
                for k in range(self.m, 0, -1):
                    sig[k] ^= K.mul(sig[k - 1], x)
            if sig[1:] == es:
                return list(combo)
        return None

"""Weil descent of the m-summand point decomposition problem over an arbitrary subspace V.

    S_{m+1}(x_1, ..., x_m, x(R)) = 0,    x_i = sum_j v_{i,j} beta_j,  beta = basis of V,

becomes n Boolean equations in N = m*l variables (bit t of every F_2^n coefficient is
equation t).  Because S_{m+1}(x, X) = sum_j X^j C_j(x), the descents D_j of the C_j do
not depend on the target, so they are computed once per factor base; a target costs
one constant multiplication per stored coefficient.

The pieces also give the linearization rank used by the heuristics:

    omega_V = dim_F2 span{ coordinate functions of D_0, ..., D_top, and 1 }.

Every target's n equations lie in that space.  When n > omega_V - 1 they are linearly
dependent there, so a non-decomposable target is refuted by plain linear algebra at
the base degree with probability about 1 - 2^-(n - omega_V + 1).  For m = 2 the pieces
are e_2^2 + b, e_2 and e_1^2 (e_1 = x_1 + x_2, e_2 = x_1 x_2), whence
omega_V = 1 + dim V + dim V^(2): the product profile of V decides it.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "pdp-scaling"))

import sumpoly  # noqa: E402

import factor_base as fbmod  # noqa: E402
import kernel  # noqa: E402
from factor_base import FactorBase  # noqa: E402


@cache
def summation_polynomial(k: int) -> frozenset:
    return sumpoly.load(k)[k]


def _block_polys(K: kernel.Field, basis: list[int], max_e: int) -> list[dict[int, int]]:
    """blk[e] = descent of x^e for x = sum_j v_j basis[j], as {mask: coefficient}."""
    out = []
    for e in range(max_e + 1):
        poly = {0: 1}
        k, ee = 0, e
        while ee:
            if ee & 1:
                lin = [(1 << j, K.frob(bj, k)) for j, bj in enumerate(basis)]
                nxt: dict[int, int] = {}
                for mask, c in poly.items():
                    for vm, zc in lin:
                        nm = mask | vm
                        nxt[nm] = nxt.get(nm, 0) ^ K.mul(c, zc)
                poly = {mk: c for mk, c in nxt.items() if c}
            ee >>= 1
            k += 1
        out.append(poly)
    return out


@dataclass
class Pieces:
    """Target-independent descent of S_{m+1} over V: D_j for every power X^j."""

    fb: FactorBase
    m: int
    masks: np.ndarray = field(init=False)
    piece_pos: list[np.ndarray] = field(init=False)
    piece_coeffs: list[np.ndarray] = field(init=False)

    def __post_init__(self):
        K = self.fb.curve.K
        l, m = self.fb.l, self.m
        self.N = m * l
        if self.N > 31:
            raise ValueError("more than 31 Boolean variables")
        S = summation_polynomial(m + 1)
        max_e = 2 ** (m - 1)
        blk = _block_polys(K, self.fb.basis, max_e)
        by_power: dict[int, dict[tuple[int, ...], int]] = {}
        for mono in S:
            key = tuple(mono[:m])
            c = K.pow(self.fb.curve.b, mono[sumpoly.B])
            d = by_power.setdefault(mono[m], {})
            d[key] = d.get(key, 0) ^ c
        pieces: dict[int, dict[int, int]] = {}
        for j, terms in sorted(by_power.items()):
            A: dict[tuple[int, tuple[int, ...]], int] = {(0, k): v for k, v in terms.items() if v}
            for i in range(m):
                nxt: dict[tuple[int, tuple[int, ...]], int] = {}
                shift = i * l
                for (mask, rest), val in A.items():
                    e, rest2 = rest[0], rest[1:]
                    for bm, bc in blk[e].items():
                        key = (mask | (bm << shift), rest2)
                        nxt[key] = nxt.get(key, 0) ^ K.mul(val, bc)
                A = {k: v for k, v in nxt.items() if v}
            pieces[j] = {mask: v for (mask, _), v in A.items()}
        self.powers = sorted(pieces)
        allmasks = sorted(set().union(*[set(p) for p in pieces.values()]))
        self.masks = np.array(allmasks, dtype=np.uint32)
        self.piece_pos, self.piece_coeffs = [], []
        for j in self.powers:
            items = sorted(pieces[j].items())
            mk = np.array([a for a, _ in items], dtype=np.uint32)
            self.piece_pos.append(np.searchsorted(self.masks, mk))
            self.piece_coeffs.append(np.array([b for _, b in items], dtype=np.uint64))
        self.degree = int(max(bin(int(a)).count("1") for a in allmasks)) if allmasks else 0

    # ------------------------------------------------------------------ targets
    def coefficients(self, xR: int) -> np.ndarray:
        """F_2^n coefficient of every monomial in self.masks for the target abscissa xR."""
        K = self.fb.curve.K
        acc = np.zeros(len(self.masks), dtype=np.uint64)
        for j, pos, coeffs in zip(self.powers, self.piece_pos, self.piece_coeffs):
            acc[pos] ^= K.mul_const(coeffs, K.pow(xR, j))
        return acc

    def system(self, xR: int) -> "BooleanSystem":
        return BooleanSystem(self.N, self.fb.curve.n, self.masks, self.coefficients(xR))

    # ------------------------------------------------------------------ structure
    def coordinate_functions(self) -> list[int]:
        """Every coordinate function of every piece, as a bit vector over self.masks."""
        n = self.fb.curve.n
        out = []
        for pos, coeffs in zip(self.piece_pos, self.piece_coeffs):
            for t in range(n):
                sel = pos[((coeffs >> np.uint64(t)) & np.uint64(1)).astype(bool)]
                v = 0
                for p in sel.tolist():
                    v |= 1 << p
                if v:
                    out.append(v)
        return out

    def structure(self) -> dict:
        """omega_V (with the constant), the rank of its top-degree parts, and the highest
        degree left in W ∩ P_<d (what top-cancelling combinations fall to)."""
        pc = np.array([bin(int(a)).count("1") for a in self.masks])
        order = np.lexsort((self.masks, pc))
        pos = np.empty(len(order), dtype=np.int64)
        pos[order] = np.arange(len(order))
        funcs = []
        for v in self.coordinate_functions():
            w = 0
            while v:
                low = v & -v
                w |= 1 << int(pos[low.bit_length() - 1])
                v ^= low
            funcs.append(w)
        has_const = len(self.masks) > 0 and int(self.masks[0]) == 0
        vecs = funcs + ([1 << int(pos[0])] if has_const else [])
        basis = fbmod.reduce_basis(vecs)
        omega = len(basis) + (0 if has_const else 1)
        top_lo = int(np.count_nonzero(pc < self.degree))
        omega_top = sum(1 for b in basis if b.bit_length() - 1 >= top_lo)
        deg_at = pc[order]
        fallen = [int(deg_at[b.bit_length() - 1]) for b in basis if b.bit_length() - 1 < top_lo]
        return {
            "omega": omega,
            "omega_top": omega_top,
            "fallen_degree": max(fallen) if fallen else 0,
            "piece_monomials": int(len(self.masks)),
            "system_degree": self.degree,
        }


@dataclass
class BooleanSystem:
    """n Boolean equations (bit t of each F_2^n coefficient) in N variables."""

    N: int
    n: int
    masks: np.ndarray
    coeffs: np.ndarray

    def __post_init__(self):
        keep = self.coeffs != 0
        self.masks = self.masks[keep]
        self.coeffs = self.coeffs[keep]
        pcs = np.array([bin(int(a)).count("1") for a in self.masks], dtype=np.int32)
        eqs, degs = [], []
        for t in range(self.n):
            sel = ((self.coeffs >> np.uint64(t)) & np.uint64(1)).astype(bool)
            if sel.any():
                eqs.append(self.masks[sel])
                degs.append(int(pcs[sel].max()))
        self.equations = eqs
        self.degrees = degs
        self.top_degree = max(degs) if degs else 0

    @property
    def monomials(self) -> int:
        return int(len(self.masks))

    def packed(self) -> tuple[np.ndarray, np.ndarray]:
        off = np.zeros(len(self.equations) + 1, dtype=np.int32)
        off[1:] = np.cumsum([len(e) for e in self.equations])
        flat = np.concatenate(self.equations).astype(np.uint32) if self.equations else np.zeros(0, np.uint32)
        return flat, off

    def solutions(self, max_out: int = 1 << 16) -> tuple[int, np.ndarray]:
        """Exact solution set: Gaussian elimination for affine systems, else the Moebius
        transform (N <= 26).  Returns (count, up to max_out solutions)."""
        if self.top_degree <= 1:
            return self._affine_solutions(max_out)
        if self.N > 26:
            raise ValueError("brute force limited to 26 variables")
        table = np.zeros(1 << self.N, dtype=np.uint64)
        table[self.masks] = self.coeffs
        return kernel.anf_zeros(table, self.N, max_out)

    def _affine_solutions(self, max_out: int) -> tuple[int, np.ndarray]:
        # row = (variable bits) | constant << N
        N = self.N
        pivots: dict[int, int] = {}
        for eq in self.equations:
            row = 0
            for mask in eq.tolist():
                row ^= (1 << N) if mask == 0 else mask
            while row & ((1 << N) - 1):
                h = (row & ((1 << N) - 1)).bit_length() - 1
                if h in pivots:
                    row ^= pivots[h]
                else:
                    pivots[h] = row
                    break
            else:
                if row:
                    return 0, np.zeros(0, dtype=np.uint32)
        for h in sorted(pivots):
            for g in list(pivots):
                if g != h and (pivots[g] >> h) & 1:
                    pivots[g] ^= pivots[h]
        free = [j for j in range(N) if j not in pivots]
        count = 1 << len(free)
        out = []
        for k in range(min(count, max_out)):
            v = 0
            for i, j in enumerate(free):
                if (k >> i) & 1:
                    v |= 1 << j
            for h, row in pivots.items():
                bit = (row >> N) & 1
                bit ^= bin(row & v & ((1 << N) - 1) & ~(1 << h)).count("1") & 1
                v |= bit << h
            out.append(v)
        return count, np.array(out, dtype=np.uint32)

    def rank_profile(self) -> dict:
        """Base-degree ranks: independent equations and the rank of their top-degree parts."""
        pc = np.array([bin(int(a)).count("1") for a in self.masks])
        vecs, tops = [], []
        top_sel = pc == self.top_degree
        for t in range(self.n):
            sel = ((self.coeffs >> np.uint64(t)) & np.uint64(1)).astype(bool)
            v = 0
            tv = 0
            for p in np.flatnonzero(sel).tolist():
                v |= 1 << p
                if top_sel[p]:
                    tv |= 1 << p
            vecs.append(v)
            tops.append(tv)
        return {"equation_rank": fbmod.rank(vecs), "top_rank": fbmod.rank(tops)}


def assignment_to_xs(fb: FactorBase, m: int, v: int) -> list[int]:
    l = fb.l
    return [int(fb.elements[(v >> (i * l)) & ((1 << l) - 1)]) for i in range(m)]


def xs_to_assignment(fb: FactorBase, xs: list[int]) -> int:
    v = 0
    for i, x in enumerate(xs):
        v |= fb.coords[x] << (i * fb.l)
    return v

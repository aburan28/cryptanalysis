"""Half-trace projection solver for the two-point decomposition over an F_2-subspace (m = 2, odd n).

On y^2 + xy = x^3 + b, for a target x-coordinate S != 0 and u = X + Y, p = X Y of the two summands,
S_3(X, Y, S) = 0 is the Artin-Schreier equation (p/S)^2 + p/S = (u + sqrt(b)/S)^2, so p is an
F_2-affine function of u (Courtois, ePrint 2016/003, Sec. 2) and the summands are the roots of
Z^2 + u Z + p(u).  Both X^2 and u X lie in V^(2) = span{v_i v_j}; projecting onto F_2^n / V^(2)
leaves n - dim V^(2) linear equations in u alone, plus the trace equation Tr(u) = Tr(sqrt(b)/S)
(vacuous when V lies in ker Tr).  Each solution u gives at most one {X, Y} by one half-trace.

The residual search dimension is max(0, dim V + dim V^(2) - n - 1 + [V in ker Tr]); the solver is
complete (it returns every decomposition) and needs no Groebner basis or solution enumeration.
Every field operation is metered by pdpkernel.c's opcount classes; the F_2 linear algebra is
charged as mac_op word operations.
"""

from __future__ import annotations

import kernel
import opcount
from factor_base import FactorBase, _columns_of_rows, kernel_basis, reduce_basis


def half_trace(K, z: int, n: int) -> int:
    """HT(z) = sum_{i=0}^{(n-1)/2} z^(4^i); HT(z)^2 + HT(z) = z + Tr(z) for odd n (pdpkernel.c, gf_lin)."""
    return K.half_trace(z)


def _reduce(echelon: dict[int, int], v: int) -> int:
    steps = 0
    while v:
        h = v.bit_length() - 1
        if h not in echelon:
            break
        v ^= echelon[h]
        steps += 1
    opcount.charge("mac_op", steps + 1)
    return v


def _echelon(vectors) -> dict[int, int]:
    e: dict[int, int] = {}
    for v in vectors:
        v = _reduce(e, int(v))
        if v:
            e[v.bit_length() - 1] = v
    return e


class HalfTraceSolver:
    """Precomputed per factor base; `decompose(S)` is linear algebra per target."""

    def __init__(self, fb: FactorBase):
        C, K = fb.curve, fb.curve.K
        self.fb, self.C, self.K, self.n = fb, C, K, C.n
        if self.n % 2 == 0:
            raise ValueError("half-trace needs odd n")
        self.basis = [int(b) for b in fb.basis]
        self.l = len(self.basis)
        self.V = _echelon(self.basis)
        prods = [K.mul(a, b) for i, a in enumerate(self.basis) for b in self.basis[i:]]
        self.V2 = reduce_basis(prods)
        self.dim_V2 = len(self.V2)
        # parity checks h: <h, w> = 0 for every w in V^(2); pi(z) = (<h_k, z>)_k
        self.checks = (kernel_basis(_columns_of_rows(self.V2, self.n), self.n) if self.V2
                       else [1 << i for i in range(self.n)])
        self.sqrt_b = K.sqrt(C.b)
        # u -> HT(u^2) is F_2-linear; precompute it on the basis of V
        self.ht_sq = [half_trace(K, K.sqr(v), self.n) for v in self.basis]

    @staticmethod
    def _dot(a: int, b: int) -> int:
        return bin(a & b).count("1") & 1

    def excess(self) -> int:
        return self.n - self.l - self.dim_V2

    def candidates(self, S: int) -> tuple[list[int], int]:
        """Every u in V solving the projected linear system for some eps, and the solution-space dim."""
        K, n = self.K, self.n
        inv_s = K.inv(S)
        c0 = self.sqrt_b and K.mul(self.sqrt_b, inv_s)  # sqrt(b) / S
        cols = [K.mul(S, h) for h in self.ht_sq]          # A(v_j) = S * HT(v_j^2)
        const_ht = K.mul(S, half_trace(K, K.sqr(c0), n))  # S * HT((sqrt(b)/S)^2)
        out, dims = [], 0
        trace_rhs = K.trace(c0)
        for eps in (0, 1):
            const = const_ht ^ (S if eps else 0)
            rows = []
            for h in self.checks:
                row = sum(self._dot(h, a) << j for j, a in enumerate(cols))
                rows.append((row, self._dot(h, const)))
            opcount.charge("mac_op", len(self.checks) * (self.l + 1))
            rows.append((sum(K.trace(v) << j for j, v in enumerate(self.basis)), trace_rhs))
            sol = _affine_solve(rows, self.l)
            if sol is None:
                continue
            u0, free = sol
            dims = max(dims, len(free))
            for mask in range(1 << len(free)):
                coef = u0
                for k, f in enumerate(free):
                    if (mask >> k) & 1:
                        coef ^= f
                u = 0
                for j, v in enumerate(self.basis):
                    if (coef >> j) & 1:
                        u ^= v
                out.append(u)
        return out, dims

    def decompose(self, R: tuple[int, int]) -> list[tuple[tuple[int, int], tuple[int, int]]]:
        """All {P1, P2} with P1, P2 in the factor base and P1 + P2 = R (x(P_i) in V)."""
        K = self.K
        S = R[0]
        found = set()
        us, _ = self.candidates(S)
        for u in set(us):
            F = half_trace(K, K.sqr(u ^ K.mul(self.sqrt_b, K.inv(S))), self.n)
            for eps in (0, 1):
                p = K.mul(S, F ^ eps)
                if u == 0:
                    X = K.sqrt(p)
                    roots = [X]
                else:
                    z = K.mul(p, K.inv(K.sqr(u)))
                    if K.trace(z):
                        continue
                    X = K.mul(u, half_trace(K, z, self.n))
                    roots = [X, X ^ u]
                if any(_reduce(self.V, x) for x in roots):
                    continue
                X, Y = roots[0], roots[-1]
                for P in _signed(K, X):
                    for Q in _signed(K, Y):
                        if K.add(P, Q) == R:
                            found.add(tuple(sorted((P, Q))))
        return sorted(found)


def _signed(K, x: int):
    P = K.lift(x)
    if P is None:
        return []
    return [P, K.neg(P)] if x else [P]


def _affine_solve(rows, nvars):
    """rows: (mask over nvars, rhs).  Returns (particular solution, null-space basis) or None."""
    piv: dict[int, tuple[int, int]] = {}
    opcount.charge("mac_op", len(rows) * (nvars + 1))
    for mask, rhs in rows:
        for c, (pm, pr) in piv.items():
            if (mask >> c) & 1:
                mask ^= pm
                rhs ^= pr
        if not mask:
            if rhs:
                return None
            continue
        c = mask.bit_length() - 1
        for k, (pm, pr) in list(piv.items()):
            if (pm >> c) & 1:
                piv[k] = (pm ^ mask, pr ^ rhs)
        piv[c] = (mask, rhs)
    x = 0
    for c, (pm, pr) in piv.items():
        if pr:
            x |= 1 << c
    free_vars = [v for v in range(nvars) if v not in piv]
    null = []
    for f in free_vars:
        vec = 1 << f
        for c, (pm, _) in piv.items():
            if (pm >> f) & 1:
                vec |= 1 << c
        null.append(vec)
    return x, null

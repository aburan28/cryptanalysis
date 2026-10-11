"""Exact degree measurements of Boolean PDP systems, and the semi-regular predictions.

Columns are multilinear monomials in grevlex order (x_0 > ... > x_{N-1}); bit position
increases with the order, so the echelon kernel's highest-bit pivots are leading
monomials and each new degree block is appended above the old ones.  R_D is the row
space of the Macaulay matrix M_<=D = {x^a f_i : |a| + deg f_i <= D} in the Boolean ring
F_2[x]/(x_i^2 + x_i), which equals the multilinear part of the Macaulay matrix with the
field equations included.

Per degree D the scan records rank(R_D), the rank of its degree-D (top) projection, and

    fall(D) = dim(R_D ∩ P_<=D-1) - dim R_{D-1} = rank_D - top_D - rank_{D-1},

the number of new lower-degree polynomials that degree D produces.  Then

  first fall degree  FFD     = min{D : fall(D) > 0};
  solving degree     D_solve = min{D : LM(R_D) generates LT(I)}, tested exactly: the
                               ideal is radical with #solutions = S (known by brute force),
                               so it holds iff the multilinear monomials divisible by no
                               leading monomial number S (S = 0: 1 in R_D, a refutation;
                               S = 1: every variable is a leading monomial);
  regularity         D_reg   = min{D : (top parts)_D = every degree-D monomial} in the
                               graded ring F_2[x]/(x_i^2), measured separately and compared
                               with the semi-regular series (1+t)^N / prod(1 + t^d_i).

For the refutations and unique solutions that make up almost every relation-collection
query, D_solve is exactly where an XL solver stops, so its matrix and word-XOR count are
charged as the PDP cost.  D_reg is reported because it is the textbook proxy, and on
structured systems it can sit above D_solve.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from math import comb

import numpy as np

import kernel


# ------------------------------------------------------------------ predictions
def semi_regular_series(N: int, degrees: list[int], upto: int | None = None) -> list[int]:
    """Coefficients of (1+t)^N / prod_i (1 + t^d_i) up to t^upto."""
    upto = N + 1 if upto is None else upto
    c = [comb(N, k) for k in range(upto + 1)]
    for d in degrees:
        nxt = [0] * (upto + 1)
        for k in range(upto + 1):
            nxt[k] = c[k] - (nxt[k - d] if k >= d else 0)
        c = nxt
    return c


def semi_regular_dreg(N: int, degrees: list[int]) -> int | None:
    """Index of the first non-positive coefficient, or None if the series stays positive."""
    for k, v in enumerate(semi_regular_series(N, degrees)):
        if v <= 0:
            return k
    return None


def macaulay_shape(N: int, degrees: list[int], D: int) -> tuple[int, int]:
    """(rows, cols) of M_<=D for equations of the given degrees."""
    cols = sum(comb(N, k) for k in range(D + 1))
    rows = sum(sum(comb(N, k) for k in range(D - d + 1)) for d in degrees if d <= D)
    return rows, cols


# ------------------------------------------------------------------ layout
class Layout:
    """Monomials of N variables ordered by (degree, grevlex): positions and inverse."""

    _cache: dict[int, "Layout"] = {}

    def __init__(self, N: int):
        if N > 26:
            raise ValueError("monomial layout limited to 26 variables")
        self.N = N
        a = np.arange(1 << N, dtype=np.uint32)
        pc = np.zeros(1 << N, dtype=np.uint8)
        for i in range(N):
            pc += ((a >> np.uint32(i)) & np.uint32(1)).astype(np.uint8)
        self.pc = pc
        self.colidx = np.full(1 << N, -1, dtype=np.int32)
        self._blocks: dict[int, np.ndarray] = {}
        self.cum = [0] * (N + 2)
        acc = 0
        for k in range(N + 1):
            acc += comb(N, k)
            self.cum[k + 1] = acc
        self._filled = -1

    @classmethod
    def get(cls, N: int) -> "Layout":
        if N not in cls._cache:
            cls._cache[N] = cls(N)
        return cls._cache[N]

    def cols(self, D: int) -> int:
        """Number of monomials of degree <= D."""
        return self.cum[min(D, self.N) + 1] if D >= 0 else 0

    def block(self, k: int) -> np.ndarray:
        """Degree-k monomials in ascending position (descending integer mask)."""
        if k not in self._blocks:
            self._blocks[k] = np.flatnonzero(self.pc == k)[::-1].astype(np.uint32)
        return self._blocks[k]

    def fill(self, D: int) -> None:
        for k in range(self._filled + 1, min(D, self.N) + 1):
            blk = self.block(k)
            self.colidx[blk] = np.arange(self.cum[k], self.cum[k] + len(blk), dtype=np.int32)
        self._filled = max(self._filled, min(D, self.N))

    def pos2mask(self, D: int) -> np.ndarray:
        """Monomial at every column position of degree <= D."""
        D = min(D, self.N)
        key = ("p2m", D)
        if key not in self._blocks:
            self._blocks[key] = np.concatenate([self.block(k) for k in range(D + 1)])
        return self._blocks[key]

    def masks_at(self, positions: np.ndarray) -> np.ndarray:
        out = np.empty(len(positions), dtype=np.uint32)
        for k in range(self.N + 1):
            lo, hi = self.cum[k], self.cum[k + 1]
            sel = (positions >= lo) & (positions < hi)
            if sel.any():
                out[sel] = self.block(k)[positions[sel] - lo]
        return out


# ------------------------------------------------------------------ scan
@dataclass
class Limits:
    d_max: int = 8
    max_cols: int = 60_000
    max_rows: int = 250_000
    chunk: int = 4096


def _standard_count(ech: kernel.Echelon, lay: Layout) -> int:
    piv = ech.pivots()
    return kernel.count_standard(lay.masks_at(piv), lay.N)


MODES = ("xl", "mxl")


def degree_scan(system, S: int | None, limits: Limits = Limits(), stop_on_unit: bool = True, mode: str = "xl") -> dict:
    """Macaulay degree scan of a descent.BooleanSystem with S known solutions.

    mode "xl": R_D is spanned by x^a f_i, |a| + deg f_i <= D (the Macaulay matrix; the
    Caminata-Gorla solving degree).  mode "mxl": R_D is the closure of the equations under
    multiplication by variables within degree D, so polynomials that fall below D are
    multiplied again at the same degree (MutantXL; the step degree an F4 run reaches).
    """
    if mode not in MODES:
        raise ValueError(mode)
    N = system.N
    lay = Layout.get(N)
    flat, off = system.packed()
    degs = system.degrees
    out: dict = {"mode": mode, "per_degree": [], "status": None, "D_solve": None, "FFD": None}
    if not degs:
        out["status"] = "no_equations"
        return out
    D0 = min(degs)
    lay.fill(D0)
    ech = kernel.Echelon(lay.cols(D0))
    multiplied = np.zeros(0, dtype=bool)
    prev_rank = 0
    rows_total = 0
    t_start = time.perf_counter_ns()
    for D in range(D0, limits.d_max + 1):
        cols = lay.cols(D)
        tasks = []
        for i, d in enumerate(degs):
            if mode == "xl":
                ks = range(0, D - d + 1) if D == D0 else ([D - d] if D - d >= 0 else [])
            else:
                ks = [0] if (d <= D if D == D0 else d == D) else []
            tasks += [(i, k) for k in ks]
        nrows = sum(len(lay.block(k)) for _, k in tasks)
        if mode == "mxl":
            nrows += N * max(0, ech.rank - int(multiplied.sum()))
        if cols > limits.max_cols or rows_total + nrows > limits.max_rows:
            out["status"] = "budget"
            out["budget_degree"] = D
            break
        t0 = time.perf_counter_ns()
        lay.fill(D)
        ech.extend(cols)
        words = ech.words
        x0 = ech.xors
        build_ops = 0
        used_rows = 0
        stopped = False
        closure_rounds = 0
        for i, k in tasks:
            mults = lay.block(k)
            for s in range(0, len(mults), limits.chunk):
                mm = mults[s : s + limits.chunk]
                rows, ops = kernel.build_rows(words, flat, off, mm, np.full(len(mm), i, np.int32), lay.colidx)
                build_ops += ops
                used_rows += ech.add(rows, stop_on_unit)
                if stop_on_unit and ech.has_unit:
                    stopped = True
                    break
            if stopped:
                break
        if mode == "mxl" and not stopped:
            p2m = lay.pos2mask(D)
            below = lay.cols(D - 1)
            per_chunk = max(1, (1 << 22) // max(1, N * words))
            while not stopped:
                piv = ech.row_pivots()
                if len(multiplied) < len(piv):
                    multiplied = np.concatenate([multiplied, np.zeros(len(piv) - len(multiplied), dtype=bool)])
                cand = np.flatnonzero(~multiplied[: len(piv)] & (piv < below)).astype(np.int32)
                if not len(cand):
                    break
                if rows_total + used_rows + N * len(cand) > limits.max_rows:
                    out["status"] = "budget"
                    out["budget_degree"] = D
                    stopped = True
                    break
                closure_rounds += 1
                multiplied[cand] = True
                for s in range(0, len(cand), per_chunk):
                    rows, ops = ech.mul_rows(cand[s : s + per_chunk], N, p2m, lay.colidx)
                    build_ops += ops
                    used_rows += ech.add(rows, stop_on_unit)
                    if stop_on_unit and ech.has_unit:
                        stopped = True
                        break
        rows_total += used_rows
        rank = ech.rank
        top = ech.pivots_from(lay.cols(D - 1))
        rec = {
            "D": D,
            "cols": cols,
            "rows": used_rows,
            "rows_total": rows_total,
            "rank": rank,
            "top_rank": top,
            "fall": rank - top - prev_rank,
            "unit": ech.has_unit,
            "partial": stopped,
            "closure_rounds": closure_rounds,
            "xors": ech.xors - x0,
            "build_ops": build_ops,
            "wall_ns": time.perf_counter_ns() - t0,
        }
        out["per_degree"].append(rec)
        if out["FFD"] is None and rec["fall"] > 0:
            out["FFD"] = D
        if out["status"] == "budget":
            break
        if ech.has_unit:
            out["status"] = "refuted"
            out["D_solve"] = D
            break
        if S is not None and S >= 1:
            if S == 1:
                done = ech.pivots_from(lay.cols(0)) - ech.pivots_from(lay.cols(1)) == N
            else:
                std = _standard_count(ech, lay)
                rec["standard_monomials"] = std
                done = std == S
            if done:
                out["status"] = "solved"
                out["D_solve"] = D
                break
        prev_rank = rank
    else:
        out["status"] = "degree_limit"
    if out["status"] is None:
        out["status"] = "degree_limit"
    out["xors"] = sum(r["xors"] for r in out["per_degree"])
    out["build_ops"] = sum(r["build_ops"] for r in out["per_degree"])
    out["wall_ns"] = time.perf_counter_ns() - t_start
    last = out["per_degree"][-1] if out["per_degree"] else None
    out["final_cols"] = last["cols"] if last else 0
    out["final_rows"] = last["rows_total"] if last else 0
    out["max_degree_built"] = last["D"] if last else None
    return out


def homogeneous_regularity(system, limits: Limits = Limits()) -> dict:
    """Hilbert function of (top parts) in F_2[x]/(x_i^2), degree by degree, until it vanishes."""
    N = system.N
    lay = Layout.get(N)
    degs = system.degrees
    tops = []
    for eq, d in zip(system.equations, degs):
        sel = lay.pc[eq] == d
        tops.append(eq[sel])
    off = np.zeros(len(tops) + 1, dtype=np.int32)
    off[1:] = np.cumsum([len(t) for t in tops])
    flat = np.concatenate(tops).astype(np.uint32) if tops else np.zeros(0, np.uint32)
    hf = []
    D_reg = None
    status = "degree_limit"
    for D in range(min(degs), min(limits.d_max, N) + 1):
        width = comb(N, D)
        nrows = sum(comb(N, D - d) for d in degs if D - d >= 0)
        if width > limits.max_cols or nrows > limits.max_rows:
            status = "budget"
            break
        lay.fill(D)
        ech = kernel.Echelon(width)
        words = ech.words
        for i, d in enumerate(degs):
            if D - d < 0:
                continue
            mults = lay.block(D - d)
            for s in range(0, len(mults), limits.chunk):
                mm = mults[s : s + limits.chunk]
                rows, _ = kernel.build_rows(
                    words, flat, off, mm, np.full(len(mm), i, np.int32), lay.colidx, lay.cols(D - 1), D
                )
                ech.add(rows)
        hf.append({"D": D, "hilbert": width - ech.rank, "cols": width})
        if ech.rank == width:
            D_reg = D
            status = "regular"
            break
    sr = semi_regular_hilbert(N, degs, (hf[-1]["D"] if hf else 0))
    for rec in hf:
        rec["semi_regular"] = sr[rec["D"]]
    return {"D_reg": D_reg, "status": status, "hilbert": hf}


def semi_regular_hilbert(N: int, degrees: list[int], upto: int) -> list[int]:
    """The semi-regular Hilbert function: the series truncated at its first non-positive term."""
    out = []
    dead = False
    for v in semi_regular_series(N, degrees, upto):
        dead = dead or v <= 0
        out.append(0 if dead else v)
    return out

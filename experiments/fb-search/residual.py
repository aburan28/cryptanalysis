#!/usr/bin/env python3
"""The residual bilinear system left above the linearization limit, and how hard it really is.

After the linear solve of the half-trace oracle (htsolver.py), what remains for one target S and
one eps in {0, 1} is: find t in F_2^d and X in V (l bits) with

    X^2 + u(t) X + p(u(t)) = 0,   u(t) = u0 + sum_k t_k f_k,  p affine in t,

whose only nontrivial part lies in V^(2): an overdetermined bilinear system of 2l - 1 equations
in l + d unknowns.  Generic counting (ABOVE_LIMIT.md, Sec. 3) says nothing beats enumerating
the 2^d values of t.  This script asks whether *our* system is generic: it builds the Boolean
system for real targets, runs the MXL degree scan on it, and records the solving degree and cost
next to 2^d enumeration and the generic overdetermined-bilinear degree prediction.

    python3 residual.py --n 41 --l 15 16 17 --family geomtraceu --targets 30
"""

from __future__ import annotations

import argparse
import math
import random
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "pdp-degree-heuristics"))
sys.path.insert(0, str(HERE.parent / "ic-bench"))

import kernel  # noqa: E402
import macaulay  # noqa: E402
import opcount  # noqa: E402
from descent import BooleanSystem  # noqa: E402
from factor_base import FactorBase  # noqa: E402
from htsolver import HalfTraceSolver, _affine_solve  # noqa: E402
from toycurve import ToyCurve, canonical  # noqa: E402


def residual_systems(sv: HalfTraceSolver, S: int) -> list[dict]:
    """For each eps whose projected linear system is consistent: the residual Boolean system."""
    K, n, l = sv.K, sv.n, sv.l
    inv_s = K.inv(S)
    c0 = K.mul(sv.sqrt_b, inv_s)
    cols = [K.mul(S, h) for h in sv.ht_sq]
    const_ht = K.mul(S, K.half_trace(K.sqr(c0)))
    out = []
    for eps in (0, 1):
        const = const_ht ^ (S if eps else 0)
        rows = [(sum(sv._dot(h, a) << j for j, a in enumerate(cols)), sv._dot(h, const)) for h in sv.checks]
        rows.append((sum(K.trace(v) << j for j, v in enumerate(sv.basis)), K.trace(c0)))
        sol = _affine_solve(rows, l)
        if sol is None:
            continue
        u0c, free = sol

        def field(coef: int) -> int:
            z = 0
            for j, v in enumerate(sv.basis):
                if (coef >> j) & 1:
                    z ^= v
            return z

        u0 = field(u0c)
        fs = [field(f) for f in free]
        d = len(fs)
        N = l + d
        # p(u) = S * (HT((u + c0)^2) + eps) = A(u) + const, A(u) = S * HT(u^2)
        p_u0 = K.mul(S, K.half_trace(K.sqr(u0 ^ c0)) ^ (1 if eps else 0))
        mono: dict[int, int] = {0: p_u0}
        for i, v in enumerate(sv.basis):
            mono[1 << i] = mono.get(1 << i, 0) ^ K.sqr(v) ^ K.mul(u0, v)
        for k, f in enumerate(fs):
            mono[1 << (l + k)] = mono.get(1 << (l + k), 0) ^ K.mul(S, K.half_trace(K.sqr(f)))
            for i, v in enumerate(sv.basis):
                m = (1 << i) | (1 << (l + k))
                mono[m] = mono.get(m, 0) ^ K.mul(f, v)
        system = None
        if N <= 32:
            masks = np.array(sorted(mono), dtype=np.uint32)
            coeffs = np.array([mono[int(m)] for m in masks], dtype=np.uint64)
            system = BooleanSystem(N, n, masks, coeffs)
        out.append({"eps": eps, "d": d, "N": N, "system": system, "mono": mono})
    return out


def bilinear_equations(sv: HalfTraceSolver, S: int, eps_sys: dict) -> tuple[int, int, list[list[tuple[int, int]]]]:
    """The residual system as Boolean equations, each a list of monomials (x_mask, t_mask) with
    x_mask of weight <= 1: the coordinate functions of X^2 + u(t) X + p(u(t)) over F_2."""
    s = eps_sys["system"]
    l, d, n = sv.l, eps_sys["d"], sv.n
    xs_mask, t_shift = (1 << l) - 1, l
    eqs = []
    for bit in range(n):
        sel = ((s.coeffs >> np.uint64(bit)) & np.uint64(1)).astype(bool)
        if not sel.any():
            continue
        eqs.append([(int(m) & xs_mask, int(m) >> t_shift) for m in s.masks[sel].tolist()])
    return l, d, eqs


def y_xl(l: int, d: int, eqs, k_max: int = 4, max_cols: int = 2_000_000) -> dict:
    """y-XL in the t variables (arXiv 2006.09442): rows f * t^S for |S| <= k, X kept linear.
    Returns the smallest k at which 1 is in the row space (a refutation), and the matrix sizes."""
    from itertools import combinations

    import kernel as _k

    out = {"k_refute": None, "per_k": []}
    for k in range(0, k_max + 1):
        tmon = [0]
        for r in range(1, k + 2):
            tmon += [sum(1 << i for i in c) for c in combinations(range(d), r)]
        # columns: (x part, t part); degree order so that the constant is column 0
        cols = sorted({(xm, tm) for xm in [0] + [1 << i for i in range(l)] for tm in tmon},
                      key=lambda c: (bin(c[0]).count("1") + bin(c[1]).count("1"), c[0], c[1]))
        if len(cols) > max_cols:
            out["per_k"].append({"k": k, "cols": len(cols), "status": "budget"})
            break
        col = {c: i for i, c in enumerate(cols)}
        mults = [0] + [sum(1 << i for i in c) for r in range(1, k + 1) for c in combinations(range(d), r)]
        words = (len(cols) + 63) // 64
        ech = _k.Echelon(len(cols))
        rows_total = 0
        for f in eqs:
            batch = np.zeros((len(mults), words), dtype=np.uint64)
            for ri, mt in enumerate(mults):
                acc: dict[int, int] = {}
                for xm, tm in f:
                    key = col[(xm, tm | mt)]
                    acc[key] = acc.get(key, 0) ^ 1
                for c_, v in acc.items():
                    if v:
                        batch[ri, c_ >> 6] ^= np.uint64(1) << np.uint64(c_ & 63)
            ech.add(batch, stop_on_unit=True)
            rows_total += len(mults)
            if ech.has_unit:
                break
        rec = {"k": k, "cols": len(cols), "rows": rows_total, "rank": ech.rank, "xors": ech.xors,
               "unit": ech.has_unit}
        out["per_k"].append(rec)
        if ech.has_unit:
            out["k_refute"] = k
            break
    return out


def boolean_equations(n: int, mono: dict[int, int]) -> list[list[int]]:
    """Coordinate functions over F_2 of sum_m mono[m] * m, as lists of 64-bit monomial masks."""
    eqs = []
    for bit in range(n):
        f = [m for m, c in mono.items() if (c >> bit) & 1]
        if f:
            eqs.append(sorted(f))
    return eqs


_SMXL = None


def smxl(N: int, eqs: list[list[int]], d_max: int = 5, max_cols: int = 120_000) -> dict:
    """Sparse-column MXL closure (smxl.c), up to 64 variables."""
    import ctypes
    import subprocess

    global _SMXL
    if _SMXL is None:
        so = HERE / "build" / "libsmxl.so"
        src = HERE / "smxl.c"
        if not so.exists() or so.stat().st_mtime < src.stat().st_mtime:
            so.parent.mkdir(exist_ok=True)
            subprocess.run(["cc", "-O3", "-march=native", "-shared", "-fPIC", "-o", str(so), str(src)], check=True)
        _SMXL = ctypes.CDLL(str(so))
        _SMXL.smxl_run.restype = ctypes.c_longlong
    flat = np.array([m for f in eqs for m in f], dtype=np.uint64)
    off = np.zeros(len(eqs) + 1, dtype=np.int32)
    off[1:] = np.cumsum([len(f) for f in eqs])
    out = np.zeros(8, dtype=np.int64)
    P = ctypes.POINTER
    _SMXL.smxl_run(ctypes.c_int(N), flat.ctypes.data_as(P(ctypes.c_uint64)), off.ctypes.data_as(P(ctypes.c_int32)),
                   ctypes.c_int(len(eqs)), ctypes.c_int(d_max), ctypes.c_longlong(max_cols),
                   out.ctypes.data_as(P(ctypes.c_longlong)))
    status = {1: "refuted", 0: "degree_limit", -1: "budget", -2: "memory"}[int(out[0])]
    return {"status": status, "degree": int(out[1]), "cols": int(out[2]), "rank": int(out[3]),
            "xors": int(out[4]), "rows_in": int(out[5]), "linear_pivots": int(out[6])}


def bilinear_degree(nx: int, ny: int, m: int) -> int | None:
    """Generic y-semiregular degree for an overdetermined bilinear system (arXiv 2006.09442):
    ceil(n_x (n_y - 1) / (m - n_x)) + 1, multiplying by y-monomials only."""
    if m <= nx:
        return None
    return math.ceil(nx * max(0, ny - 1) / (m - nx)) + 1


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--n", type=int, required=True)
    ap.add_argument("--l", type=int, nargs="+", required=True)
    ap.add_argument("--family", default="geomtraceu")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--targets", type=int, default=30)
    ap.add_argument("--mode", default="mxl", choices=macaulay.MODES)
    ap.add_argument("--d-max", type=int, default=6)
    ap.add_argument("--max-cols", type=int, default=400_000)
    ap.add_argument("--solver", default="mxl", choices=("mxl", "yxl", "smxl"),
                    help="mxl: degree scan of the residual Boolean system (N <= 26); yxl: y-XL in t")
    ap.add_argument("--k-max", type=int, default=4)
    ap.add_argument("--only-refutations", action="store_true", help="skip decomposable targets")
    ap.add_argument("--out", default="")
    args = ap.parse_args()
    C = ToyCurve(args.n)
    limits = macaulay.Limits(d_max=args.d_max, max_cols=args.max_cols, max_rows=4_000_000)
    for l in args.l:
        fb = FactorBase(C, args.family, l, args.seed)
        sv = HalfTraceSolver(fb)
        rng = random.Random(f"residual|{fb.digest}")
        for _ in range(args.targets):
            _, R = C.random_subgroup_point(rng)
            truth = bool(sv.decompose(R))
            if truth and args.only_refutations:
                continue
            for rs in residual_systems(sv, R[0]):
                s = rs["system"]
                if args.solver == "smxl":
                    eqs = boolean_equations(sv.n, rs["mono"])
                    sm = smxl(rs["N"], eqs, args.d_max, args.max_cols)
                    rec = {"n": args.n, "l": l, "family": args.family, "eps": rs["eps"], "d": rs["d"], "N": rs["N"],
                           "equations": len(eqs), "decomposable": truth, "solver": "smxl", **sm,
                           "enum_candidates": 2 ** rs["d"], "generic_deg_y_t": bilinear_degree(l, rs["d"], len(eqs))}
                    print(canonical(rec), flush=True)
                    if args.out:
                        with open(args.out, "a") as fh:
                            fh.write(canonical(rec) + "\n")
                    continue
                if args.solver == "yxl":
                    _, d, eqs = bilinear_equations(sv, R[0], rs)
                    yx = y_xl(l, d, eqs, args.k_max)
                    last = yx["per_k"][-1]
                    rec = {"n": args.n, "l": l, "family": args.family, "eps": rs["eps"], "d": d, "N": rs["N"],
                           "equations": len(eqs), "decomposable": truth, "solver": "y-XL(t)",
                           "k_refute": yx["k_refute"], "cols": last["cols"], "rows": last.get("rows"),
                           "xors": sum(r.get("xors", 0) for r in yx["per_k"]), "enum_candidates": 2 ** d,
                           "generic_deg_y_t": bilinear_degree(l, d, len(eqs))}
                    print(canonical(rec), flush=True)
                    if args.out:
                        with open(args.out, "a") as fh:
                            fh.write(canonical(rec) + "\n")
                    continue
                m_eqs = len(s.equations)
                scan = macaulay.degree_scan(s, (lambda s=s: s.solutions()[0]) if rs["N"] <= 26 else None,
                                            limits, mode=args.mode)
                rec = {"n": args.n, "l": l, "family": args.family, "eps": rs["eps"], "d": rs["d"], "N": rs["N"],
                       "equations": m_eqs, "decomposable": truth, "status": scan["status"],
                       "D_solve": scan["D_solve"], "mac_ops": scan["xors"] + scan["build_ops"],
                       "final_cols": scan["final_cols"], "enum_candidates": 2 ** rs["d"],
                       "generic_deg_y_t": bilinear_degree(l, rs["d"], m_eqs),
                       "generic_deg_y_x": bilinear_degree(rs["d"], l, m_eqs)}
                print(canonical(rec), flush=True)
                if args.out:
                    with open(args.out, "a") as fh:
                        fh.write(canonical(rec) + "\n")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Two-point test for non-subspace factor bases: is any F of size 2^l better than a progression?

An m = 2 oracle that is F_2-linear in (e1, e2) = (x1 + x2, x1 x2) has its unknowns in
span(F + F) x span(F) span(F), so its residual dimension is

    d_lin(F) = max(0, dim span(F + F) + dim span(F)^(2) - n - 1).

span(F + F) contains x0 + F, so its dimension is >= log2 |F|, and Hou-Leung-Xiang (n prime) gives
dim span(F)^(2) >= 2 dim span(F) - 1 >= 2 log2 |F| - 1.  Hence d_lin(F) >= 3 log2 |F| - n - 2, the value of a
progression of the same size: the relation yield depends on |F| only, so a progression dominates every base
of the same size for linear oracles.  The other generic route, enumerating one summand, costs |F| = 2^l,
which is >= 2^(3l - n - 2) for every l <= (n + 2)/2.  This script measures d_lin on concrete non-subspace
families, for the record.

    python3 nonsubspace.py --n 23 41 --out results/nonsubspace.jsonl
"""

from __future__ import annotations

import argparse
import math
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "pdp-degree-heuristics"))

from factor_base import FactorBase, product_profile, reduce_basis, span  # noqa: E402
from toycurve import ToyCurve, canonical  # noqa: E402

FAMILIES = ("progression", "cube", "fifth", "union", "random")


def family_set(C: ToyCurve, family: str, l: int, rng: random.Random) -> set[int]:
    K, n = C.K, C.n
    prog = [int(v) for v in span(FactorBase(C, "prefix", l, 1).basis)]
    if family == "progression":
        return set(prog)
    if family == "cube":
        return {K.mul(K.sqr(v), v) for v in prog}
    if family == "fifth":
        return {K.mul(K.sqr(K.sqr(v)), v) for v in prog}
    if family == "union":
        def sub() -> list[int]:
            return [int(v) for v in span(reduce_basis(rng.getrandbits(n) for _ in range(l - 1)))]
        return set(sub()) | set(sub())
    if family == "random":
        out = {0}
        while len(out) < 1 << l:
            out.add(rng.getrandbits(n))
        return out
    raise ValueError(family)


def profile(C: ToyCurve, F: set[int]) -> dict:
    n = C.n
    x0 = next(iter(F))
    s_sum = len(reduce_basis(x ^ x0 for x in F))
    basis = reduce_basis(F)
    s, s2 = product_profile(C.K, basis, 2)
    size = math.log2(len(F))
    d_lin = max(0, s_sum + s2 - n - 1)
    d_prog = max(0, 3 * math.ceil(size) - n - 2)
    return {"log2_size": round(size, 3), "dim_span_sum": s_sum, "dim_span": s, "dim_span_sq": s2,
            "d_lin": d_lin, "d_progression_same_size": d_prog, "excess": d_lin - d_prog}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--n", type=int, nargs="+", default=[23, 41])
    ap.add_argument("--out", default="")
    args = ap.parse_args()
    out = open(args.out, "w") if args.out else None
    print("| n | l | family | log2 |F| | dim span(F+F) | dim span(F) | dim span(F)^(2) | d_lin | progression | excess |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    for n in args.n:
        C = ToyCurve(n)
        limit = (n + 2) / 3
        for l in sorted({math.floor(limit), math.floor(limit) + 2, min((n + 1) // 2, math.floor(limit) + 4)}):
            for fam in FAMILIES:
                p = profile(C, family_set(C, fam, l, random.Random(f"nonsubspace|{n}|{l}|{fam}")))
                row = {"schema": "fb-search-nonsubspace/1", "kind": "stage", "n": n, "l": l, "family": fam, **p}
                print(f"| {n} | {l} | {fam} | {p['log2_size']} | {p['dim_span_sum']} | {p['dim_span']} | "
                      f"{p['dim_span_sq']} | {p['d_lin']} | {p['d_progression_same_size']} | {p['excess']} |", flush=True)
                if out:
                    out.write(canonical(row) + "\n")


if __name__ == "__main__":
    main()

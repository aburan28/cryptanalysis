"""Plain (non-mutant) Macaulay certificates for the residual system: is 1 in the span of
{m * f : f a residual equation, m a multiplier monomial} at degree D?

Multiplier sets: "t" (t-monomials of degree <= D - 2), "x" (x-monomials), "xt" (all).
A refutation found here is a single explicit identity sum_m m * g_m = 1, unlike the mutant
closures of smxl.c, which multiply intermediate results.
"""

from __future__ import annotations

import argparse
import itertools
import json
import random
import sys
import time
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "pdp-degree-heuristics"))
sys.path.insert(0, str(HERE))

from factor_base import family_basis  # noqa: E402
from htsolver import HalfTraceSolver  # noqa: E402
from residual import boolean_equations, residual_systems  # noqa: E402
from toycurve import ToyCurve, sha256_hex  # noqa: E402


def multipliers(N: int, l: int, kind: str, deg: int) -> list[int]:
    pool = {"t": list(range(l, N)), "x": list(range(l)), "xt": list(range(N))}[kind]
    out = [0]
    for k in range(1, deg + 1):
        out += [sum(1 << v for v in c) for c in itertools.combinations(pool, k)]
    return out


def certificate(N: int, l: int, eqs: list[list[int]], kind: str, D: int) -> dict:
    """Gaussian elimination over F_2 with Python-int rows; columns are monomials met so far."""
    col: dict[int, int] = {}
    piv: dict[int, int] = {}
    rows = 0
    for m in multipliers(N, l, kind, D - 2):
        for f in eqs:
            acc: dict[int, int] = {}
            for mono in f:
                p = mono | m
                acc[p] = acc.get(p, 0) ^ 1
            r = 0
            for p, c in acc.items():
                if c:
                    if p not in col:
                        col[p] = len(col) + 1  # column 0 is the constant monomial
                    r ^= 1 << (0 if p == 0 else col[p])
            rows += 1
            while r:
                h = r.bit_length() - 1
                if h not in piv:
                    piv[h] = r
                    break
                r ^= piv[h]
    refuted = 0 in piv and piv[0] == 1
    return {"kind": kind, "D": D, "rows": rows, "cols": len(col) + 1, "rank": len(piv), "refuted": refuted}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--n", type=int, required=True)
    ap.add_argument("--l", type=int, nargs="+", required=True)
    ap.add_argument("--family", default="geomtraceu")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--targets", type=int, default=4)
    ap.add_argument("--kinds", nargs="+", default=["t", "x", "xt"])
    ap.add_argument("--D", type=int, nargs="+", default=[3, 4])
    ap.add_argument("--out", default="")
    args = ap.parse_args()
    C = ToyCurve(args.n)
    for l in args.l:
        basis, _ = family_basis(C, args.family, l, args.seed)
        fb = SimpleNamespace(curve=C, basis=basis, l=l, digest=sha256_hex([args.family, l, args.seed, basis]))
        sv = HalfTraceSolver(fb)
        rng = random.Random(f"certificate|{fb.digest}")
        for ti in range(args.targets):
            _, R = C.random_subgroup_point(rng)
            truth = bool(sv.decompose(R))
            for rs in residual_systems(sv, R[0]):
                eqs = boolean_equations(sv.n, rs["mono"])
                for kind in args.kinds:
                    for D in args.D:
                        t0 = time.perf_counter()
                        res = certificate(rs["N"], l, eqs, kind, D)
                        rec = {"n": args.n, "l": l, "d": rs["d"], "target": ti, "eps": rs["eps"],
                               "decomposable": truth, **res, "wall_s": round(time.perf_counter() - t0, 3)}
                        print(json.dumps(rec, sort_keys=True), flush=True)
                        if args.out:
                            with open(args.out, "a") as fh:
                                fh.write(json.dumps(rec, sort_keys=True, separators=(",", ":")) + "\n")
                        if res["refuted"]:
                            break


if __name__ == "__main__":
    main()

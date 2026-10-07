#!/usr/bin/env python3
"""Time the optimized C enumeration of the residual space (htenum.c) on the same targets as
cms_scan.py (same random streams), and record which targets decompose (exact, any d)."""

from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from residual import HalfTraceSolver, ToyCurve, canonical, htenum, residual_systems  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cells", nargs="+", required=True)
    ap.add_argument("--family", default="geomtraceu")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--targets", type=int, default=8)
    ap.add_argument("--out", default="")
    args = ap.parse_args()
    from factor_base import family_basis

    for cell in args.cells:
        n, l = (int(v) for v in cell.split(":"))
        C = ToyCurve(n)
        basis, _ = family_basis(C, args.family, l, args.seed)
        sv = HalfTraceSolver(SimpleNamespace(curve=C, basis=basis, l=l))
        rng = random.Random(f"cms|{n}|{l}|{args.family}|{args.seed}")
        for _ in range(args.targets):
            _, R = C.random_subgroup_point(rng)
            wall, hits, cand, d = 0, 0, 0, None
            for rs in residual_systems(sv, R[0]):
                r = htenum(sv, rs, R[0])
                wall += r["wall_ns"]
                hits += r["hits"]
                cand += r["candidates"]
                d = rs["d"] if d is None else max(d, rs["d"])
            rec = {"n": n, "l": l, "family": args.family, "seed": args.seed, "d": d, "enum_wall_ns": wall,
                   "candidates": cand, "decomposable": hits > 0, "hits": hits}
            print(canonical(rec), flush=True)
            if args.out:
                with open(args.out, "a") as fh:
                    fh.write(canonical(rec) + "\n")


if __name__ == "__main__":
    main()

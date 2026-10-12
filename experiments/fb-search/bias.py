#!/usr/bin/env python3
"""Where do decompositions sit inside the residual space? A test of guided enumeration.

For decomposable targets, express each hit u as u0 + sum_k t_k f_k (echelon free basis from
residual_systems) and record the Hamming weight of t and its rank in the Gray-code order that
htenum.c walks. With no positional bias, weight ~ Binomial(d, 1/2) and rank / 2^d ~ U(0, 1),
so no ordering of the residual space finds solutions earlier than plain enumeration.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import statistics
import sys
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from residual import HalfTraceSolver, ToyCurve, htenum, residual_systems  # noqa: E402


def coords(u: int, u0: int, fs: list[int]) -> int:
    """t with u = u0 + sum t_k f_k, by elimination on the (independent) f_k."""
    piv: dict[int, tuple[int, int]] = {}
    for k, f in enumerate(fs):
        v, tag = f, 1 << k
        for h, (pv, pt) in piv.items():
            if (v >> h) & 1:
                v, tag = v ^ pv, tag ^ pt
        h = v.bit_length() - 1
        for h2, (pv, pt) in list(piv.items()):
            if (pv >> h) & 1:
                piv[h2] = (pv ^ v, pt ^ tag)
        piv[h] = (v, tag)
    v, t = u ^ u0, 0
    for h, (pv, pt) in piv.items():
        if (v >> h) & 1:
            v, t = v ^ pv, t ^ pt
    assert v == 0
    return t


def gray_rank(g: int) -> int:
    b = 0
    while g:
        b ^= g
        g >>= 1
    return b


def main() -> None:
    from factor_base import family_basis

    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--n", type=int, default=41)
    ap.add_argument("--l", type=int, nargs="+", default=[17, 18])
    ap.add_argument("--family", default="geomtraceu")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--hits", type=int, default=200)
    ap.add_argument("--out", default="")
    args = ap.parse_args()
    C = ToyCurve(args.n)
    for l in args.l:
        basis, _ = family_basis(C, args.family, l, args.seed)
        sv = HalfTraceSolver(SimpleNamespace(curve=C, basis=basis, l=l))
        rng = random.Random(f"bias|{args.n}|{l}|{args.family}|{args.seed}")
        weights, ranks, ds, targets = [], [], set(), 0
        while len(weights) < args.hits:
            _, R = C.random_subgroup_point(rng)
            targets += 1
            for rs in residual_systems(sv, R[0]):
                d = rs["d"]
                for u in htenum(sv, rs, R[0])["u_hits"]:
                    t = coords(u, rs["u0"], rs["fs"])
                    weights.append(bin(t).count("1") / d if d else 0.5)
                    ranks.append((gray_rank(t) + 0.5) / 2 ** d)
                    ds.add(d)
        k = len(weights)
        rec = {"n": args.n, "l": l, "family": args.family, "seed": args.seed, "d": sorted(ds), "targets": targets,
               "hits": k, "mean_weight_fraction": round(statistics.fmean(weights), 4),
               "mean_weight_se": round(statistics.pstdev(weights) / math.sqrt(k), 4),
               "mean_gray_rank": round(statistics.fmean(ranks), 4),
               "mean_gray_rank_se": round(statistics.pstdev(ranks) / math.sqrt(k), 4),
               "rank_deciles": [sum(1 for r in ranks if j / 10 <= r < (j + 1) / 10) for j in range(10)]}
        print(json.dumps(rec, sort_keys=True), flush=True)
        if args.out:
            with open(args.out, "a") as fh:
                fh.write(json.dumps(rec, sort_keys=True, separators=(",", ":")) + "\n")


if __name__ == "__main__":
    main()

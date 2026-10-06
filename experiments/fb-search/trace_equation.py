#!/usr/bin/env python3
"""The equation a trace-zero factor base gives up, measured.

On y^2 + xy = x^3 + 1 the third summation polynomial is S_3 = (x1 x2 + x1 x3 + x2 x3)^2 + x1 x2 x3 + 1.
With u = x1 x2 / x3,  S_3 / x3^2 = u^2 + u + x1^2 + x2^2 + 1/x3^2, so

    Tr(S_3 / x3^2) = Tr(x1) + Tr(x2) + Tr(1/x3).

A subgroup point R = (xR, yR) has Tr(xR) = 0 (it lies in 2E) and lifts, so Tr(xR + 1/xR^2) = 0 and
Tr(1/xR) = 0.  Every descent system therefore contains the linear equation Tr(x1) + Tr(x2) = 0 (the
combination Tr(S_3 / xR^2) of its n coordinate equations).  For V inside ker(Tr) that combination
vanishes identically: the system keeps n - 1 independent equations in the same 2l unknowns.  The
same linear condition is why a trace-zero base doubles the decomposition yield (every pair passes
it), so yield and degree trade one for one.

For each base this records, over the same ordinary queries: the F_2-rank of the n equations, the
MXL solving degree split by outcome, and the Macaulay cost of refuted and solved queries.

    python3 trace_equation.py --n 19 --l 6 7 --queries 120 --out results/trace-equation.jsonl
"""

from __future__ import annotations

import argparse
import random
import statistics
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "pdp-degree-heuristics"))

import macaulay  # noqa: E402
from descent import Pieces  # noqa: E402
from factor_base import FactorBase, product_profile, reduce_basis  # noqa: E402
from toycurve import ToyCurve, canonical  # noqa: E402

LIMITS = macaulay.Limits(d_max=10, max_cols=40_000, max_rows=200_000)


def equation_rank(system) -> int:
    idx = {int(m): i for i, m in enumerate(system.masks.tolist())}
    return len(reduce_basis(sum(1 << idx[int(m)] for m in eq.tolist()) for eq in system.equations))


def measure(C: ToyCurve, family: str, l: int, seed: int, queries: int) -> dict:
    fb = FactorBase(C, family, l, seed)
    P = Pieces(fb, 2)
    rng = random.Random(f"fbsearch-trace|{C.curve_id}")
    ranks, degrees = Counter(), Counter()
    cost = {"refuted": [], "solved": []}
    for _ in range(queries):
        _, R = C.random_subgroup_point(rng)
        s = P.system(R[0])
        ranks[equation_rank(s)] += 1
        S, _ = s.solutions()
        scan = macaulay.degree_scan(s, S, LIMITS, mode="mxl")
        kind = "solved" if S else "refuted"
        degrees[f"{kind}_D{scan['D_solve']}"] += 1
        cost[kind].append(scan["xors"] + scan["build_ops"])
    prof = product_profile(C.K, fb.basis, 2)
    return {
        "schema": "fb-search-trace-equation/1",
        "kind": "stage",
        "candidate_id": None,
        "curve_id": C.curve_id,
        "factor_base_sha256": fb.digest,
        "cell": {"n": C.n, "m": 2, "l": l, "family": family, "seed": seed, "mode": "mxl"},
        "trace_zero": all(C.K.trace(b) == 0 for b in fb.basis),
        "dim_V2": prof[1],
        "queries": queries,
        "query_stream": f"fbsearch-trace|{C.curve_id}",
        "equation_rank_hist": dict(sorted(ranks.items())),
        "degree_hist": dict(sorted(degrees.items())),
        "refuted_mac_ops_mean": statistics.fmean(cost["refuted"]) if cost["refuted"] else None,
        "solved_mac_ops_mean": statistics.fmean(cost["solved"]) if cost["solved"] else None,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--n", type=int, required=True)
    ap.add_argument("--l", type=int, nargs="+", required=True)
    ap.add_argument("--queries", type=int, default=120)
    ap.add_argument("--seeds", type=int, default=3)
    ap.add_argument("--out", default="")
    args = ap.parse_args()
    C = ToyCurve(args.n)
    fams = [("prefix", [1])] + [(f, list(range(1, args.seeds + 1))) for f in ("geometric", "geomtraceu", "kertrace",
                                                                           "random")]
    for l in args.l:
        for fam, seeds in fams:
            for sd in seeds:
                rec = measure(C, fam, l, sd, args.queries)
                print(f"n{args.n} l{l} {fam:10s} s{sd} trace0={int(rec['trace_zero'])} V2={rec['dim_V2']:2d} "
                      f"rank={rec['equation_rank_hist']} D={rec['degree_hist']} "
                      f"refuted={rec['refuted_mac_ops_mean']:.3g}", flush=True)
                if args.out:
                    with open(args.out, "a") as fh:
                        fh.write(canonical(rec) + "\n")


if __name__ == "__main__":
    main()

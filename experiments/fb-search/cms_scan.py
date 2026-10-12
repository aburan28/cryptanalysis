#!/usr/bin/env python3
"""CryptoMiniSat (XOR + Gauss-Jordan) on the residual system above the linearization limit.

Each record is one target: the total CMS wall time over its consistent eps branches, the status,
and (for SAT) whether the model rebuilds a genuine decomposition P1 + P2 = R.  Optionally the
2^d half-trace enumeration is timed on the same target as the reference.

    python3 cms_scan.py --cells 41:18 41:20 47:23 53:26 --targets 8 --out results/cms-scan.jsonl
"""

from __future__ import annotations

import argparse
import random
import sys
import time
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from residual import HalfTraceSolver, ToyCurve, boolean_equations, canonical, cms_solve, residual_systems, verify_model  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cells", nargs="+", required=True, help="n:l pairs")
    ap.add_argument("--family", default="geomtraceu")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--targets", type=int, default=8)
    ap.add_argument("--enum-max-d", type=int, default=18, help="also time 2^d enumeration up to this d")
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
            systems = residual_systems(sv, R[0])
            d = max((rs["d"] for rs in systems), default=None)
            wall, sat, ok = 0, False, None
            for rs in systems:
                r = cms_solve(rs["N"], boolean_equations(sv.n, rs["mono"]))
                wall += r["wall_ns"]
                if r["status"] == "sat":
                    sat = True
                    ok = verify_model(sv, rs, r["bits"], R)
            enum_ns = truth = None
            if d is not None and d <= args.enum_max_d:
                t0 = time.perf_counter_ns()
                truth = bool(sv.decompose(R))
                enum_ns = time.perf_counter_ns() - t0
            rec = {"n": n, "l": l, "family": args.family, "seed": args.seed, "d": d,
                   "N": l + d if d is not None else None, "cms_wall_ns": wall, "sat": sat,
                   "model_verified": ok, "enum_wall_ns": enum_ns, "enum_decomposable": truth}
            print(canonical(rec), flush=True)
            if args.out:
                with open(args.out, "a") as fh:
                    fh.write(canonical(rec) + "\n")


if __name__ == "__main__":
    main()

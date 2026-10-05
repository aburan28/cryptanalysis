#!/usr/bin/env python3
"""One-target online cost of m = 2 subspace IC around and above the linearization limit, with the
fastest exact oracle here (PDP2ht projection + htenum.c enumeration), against plain rho measured
on this host and the Bernstein-Lange precomputation-rho estimate.  Exploratory wall times."""

from __future__ import annotations

import json
import math
import random
import statistics
import sys
import time
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "ic-bench"))

from residual import HalfTraceSolver, ToyCurve, canonical, htenum, residual_systems  # noqa: E402


def main() -> None:
    import bench
    from factor_base import FactorBase
    from relations import predicted_yield

    n = int(sys.argv[1]) if len(sys.argv) > 1 else 41
    ls = [int(v) for v in sys.argv[2].split(",")] if len(sys.argv) > 2 else list(range(13, 21))
    C, K = ToyCurve(n), ToyCurve(n).K
    rng = random.Random("online-above")
    # rho on this host: two measured one-target solves, and the per-addition wall time
    rho_walls, rho_steps = [], []
    for _ in range(2):
        _, Q = C.random_subgroup_point(rng)
        r = bench.rho_one_target(C, Q, f"online-above|{Q[0]}")
        assert r["verified"]
        rho_walls.append(r["online_wall_ns"])
        rho_steps.append(r["steps"])
    ns_per_step = sum(rho_walls) / sum(rho_steps)
    bl_ns = 1.77 * C.r ** (1 / 3) * ns_per_step
    expected_rho_ns = math.sqrt(math.pi * C.r / 2) * ns_per_step
    t0 = time.perf_counter_ns()
    P = K.add(C.G, C.G)
    add_ns = (time.perf_counter_ns() - t0)
    for l in ls:
        fb = FactorBase(C, "geomtraceu", l, 1)
        p = predicted_yield(fb, 2)["p_decomposable"]
        sv = HalfTraceSolver(fb)
        walls, ds = [], []
        for _ in range(6):
            _, R = C.random_subgroup_point(rng)
            w = 0
            for rs in residual_systems(sv, R[0]):
                w += htenum(sv, rs, R[0])["wall_ns"]
                ds.append(rs["d"])
            walls.append(w)
        per_attempt = statistics.median(walls) + 2000  # + residual setup and one walk addition (about 2 us)
        online = per_attempt / p
        rec = {"n": n, "l": l, "limit": (n + 2) / 3, "d": max(ds) if ds else 0, "p_decomposable": p,
               "attempts": 1 / p, "per_attempt_ns": per_attempt, "online_ns": online,
               "rho_measured_ns": statistics.fmean(rho_walls), "rho_expected_ns": expected_rho_ns,
               "bernstein_lange_online_ns": bl_ns, "note": "exploratory wall times, unisolated host"}
        print(canonical(rec), flush=True)
        with open(HERE / "results" / f"online-above-n{n}.jsonl", "a") as fh:
            fh.write(canonical(rec) + "\n")


if __name__ == "__main__":
    main()

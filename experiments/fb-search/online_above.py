#!/usr/bin/env python3
"""One-target online cost of m = 2 subspace IC around and above the linearization limit, against
plain rho and the Bernstein-Lange precomputation-rho estimate, with every cost measured in C on
this host (exploratory wall times on an unisolated host).

- IC attempt: one walk addition (the batched affine addition below) plus a whole PDP2ht attempt in
  C (htenum.c ht_attempt_batch: projection for both eps, then the residual enumeration), timed
  over many targets in one call.
- Attempts per relation: 1 / p_decomposable (psi-class prediction, relations.predicted_yield),
  which the measured hit rate over the same targets checks.
- Rho step: batched affine r-adding walk in C (htenum.c ec_walk_batch, one Montgomery inversion
  per round of W walks). Plain rho: sqrt(pi r / 2) steps; Bernstein-Lange online: 1.77 r^(1/3).

The comparison is not an IC1 run: it combines measured stage costs with a predicted number of
attempts (ABOVE_LIMIT.md Sec. 4e).
"""

from __future__ import annotations

import json
import math
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from residual import HalfTraceSolver, ToyCurve, canonical, ec_walk, ht_attempts  # noqa: E402


def main() -> None:
    from factor_base import FactorBase
    from relations import predicted_yield

    n = int(sys.argv[1]) if len(sys.argv) > 1 else 41
    ls = [int(v) for v in sys.argv[2].split(",")] if len(sys.argv) > 2 else list(range(13, 21))
    C = ToyCurve(n)
    rng = random.Random("online-above-c")
    walks = [C.random_subgroup_point(rng)[1] for _ in range(256)]
    table = [C.random_subgroup_point(rng)[1] for _ in range(32)]
    ec_walk(C, walks, table, 20)
    step = min(ec_walk(C, walks, table, 2000)["ns_per_add"] for _ in range(3))
    rho_ns = math.sqrt(math.pi * C.r / 2) * step
    bl_ns = 1.77 * C.r ** (1 / 3) * step
    out = HERE / "results" / f"online-above-c-n{n}.jsonl"
    for l in ls:
        fb = FactorBase(C, "geomtraceu", l, 1)
        p = predicted_yield(fb, 2)["p_decomposable"]
        sv = HalfTraceSolver(fb)
        count = max(64, min(20000, int(4e8 / (2 ** max(0, 3 * l - n - 2) * 400 + 2000))))
        xs = [C.random_subgroup_point(rng)[1][0] for _ in range(count)]
        ht_attempts(sv, xs[:8])
        res = ht_attempts(sv, xs)
        per_attempt = res["wall_ns"] / count + step
        hit_rate = sum(1 for h in res["hits"] if h) / count
        online = per_attempt / p
        rec = {"n": n, "l": l, "limit": (n + 2) / 3, "d": max(0, l + sv.dim_V2 - n - 1 + int(all(C.K.trace(v) == 0 for v in fb.basis))), "targets": count,
               "p_decomposable": p, "measured_hit_rate": hit_rate, "attempts": 1 / p,
               "pdp_ns_per_attempt": res["wall_ns"] / count, "walk_ns_per_attempt": step,
               "candidates_per_attempt": res["candidates"] / count, "online_ns": online,
               "rho_step_ns": step, "rho_expected_ns": rho_ns, "bernstein_lange_online_ns": bl_ns,
               "online_vs_rho": rho_ns / online, "online_vs_bl": bl_ns / online,
               "note": "exploratory C wall times, unisolated host; attempts from the predicted p_decomposable"}
        print(canonical(rec), flush=True)
        with open(out, "a") as fh:
            fh.write(canonical(rec) + "\n")


if __name__ == "__main__":
    main()

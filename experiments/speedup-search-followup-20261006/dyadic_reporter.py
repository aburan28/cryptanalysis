"""Exact dyadic heavy-cell reporter over a selected-product data structure.

Construction (correct, parameter-screened).
Given nonnegative X in R^{N x D}, Y in R^{D x N}, add every dyadic interval
as an aggregated row / column:

    Xbar[I, k] = sum_{i in I} X[i, k],      Ybar[k, J] = sum_{j in J} Y[k, j].

There are fewer than 2N intervals per axis and (Xbar Ybar)[I, J] is the sum
of (XY) over the rectangle I x J.  Because XY is nonnegative, a rectangle
whose sum is below a threshold tau contains no cell >= tau, so recursively
splitting only rectangles with sum >= tau reports every heavy cell.  At each
of the log2 N levels the rectangles that are split are disjoint and each
carries mass >= tau, so there are at most M/tau of them (M = total mass) and
the reporter issues at most

    1 + 4 (M/tau) log2 N        selected-entry queries.

Total modelled cost with the AVW data structure on the (2N) x D aggregates:

    O~( N^2 / D^0.063  +  (M/tau) D^0.437  +  N D ).

Screen.  For an NFS log sieve M = N^(2+o(1)) log y and tau ~ u log y with
u = N^o(1), so M/tau = N^(2-o(1)): the reporter makes about as many queries as
there are cells, and a polynomially growing D would need u >> D^0.437 to beat
a plain scan — which does not happen at NFS parameters.  The construction is
sound; the parameters are not.

What this module does.
  * Implements the reporter and checks it against brute force (exact) on
    random nonnegative instances and on sieve-shaped instances built from the
    selected-resieve matrices.
  * Checks the query bound on every instance (exact).
  * Reports queries / cells for sieve-shaped instances as N grows, which is
    the measured face of the N^(2-o(1)) screen.
"""

from __future__ import annotations

import json
import math
import os
import random

import numpy as np

from avw_model import PRE_EXP, QUERY_EXP
from selected_resieve import build_X, build_Y, primes_upto

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "results", "dyadic_reporter.json")


class DyadicReporter:
    def __init__(self, X: np.ndarray, Y: np.ndarray):
        self.N = X.shape[0]
        assert self.N & (self.N - 1) == 0, "N must be a power of two"
        assert Y.shape[1] == self.N
        self.levels = int(math.log2(self.N))
        # xbar[level][i] = sum of X rows over the i-th interval of length 2^level
        self.xbar = [X.astype(np.int64)]
        self.ybar = [Y.astype(np.int64)]
        for _ in range(self.levels):
            px = self.xbar[-1]
            self.xbar.append(px[0::2] + px[1::2])
            py = self.ybar[-1]
            self.ybar.append(py[:, 0::2] + py[:, 1::2])
        self.queries = 0

    def query(self, level: int, i: int, j: int) -> int:
        """Selected entry (Xbar Ybar)[I, J] for the level-`level` intervals i, j."""
        self.queries += 1
        return int(self.xbar[level][i] @ self.ybar[level][:, j])

    def report(self, tau: int) -> set[tuple[int, int]]:
        self.queries = 0
        heavy = set()
        stack = [(self.levels, 0, 0, self.query(self.levels, 0, 0))]
        while stack:
            level, i, j, s = stack.pop()
            if s < tau:
                continue
            if level == 0:
                heavy.add((i, j))
                continue
            for ci in (2 * i, 2 * i + 1):
                for cj in (2 * j, 2 * j + 1):
                    stack.append((level - 1, ci, cj, self.query(level - 1, ci, cj)))
        return heavy


def brute_heavy(X, Y, tau):
    P = X.astype(np.int64) @ Y.astype(np.int64)
    return {(int(i), int(j)) for i, j in zip(*np.nonzero(P >= tau))}, int(P.sum())


def random_instances(rng: random.Random) -> list[dict]:
    rows = []
    for _ in range(25):
        N = 2 ** rng.randint(1, 6)
        D = rng.randint(1, 12)
        density = rng.choice([0.05, 0.2, 0.6])
        X = np.array([[rng.randint(0, 5) if rng.random() < density else 0 for _ in range(D)] for _ in range(N)])
        Y = np.array([[rng.randint(0, 5) if rng.random() < density else 0 for _ in range(N)] for _ in range(D)])
        pmax = int((X.astype(np.int64) @ Y.astype(np.int64)).max())
        tau = rng.randint(1, max(1, pmax) + 2)
        truth, M = brute_heavy(X, Y, tau)
        rep = DyadicReporter(X, Y)
        got = rep.report(tau)
        bound = 1 + 4 * (M / tau) * max(1, int(math.log2(N)))
        ok = got == truth and rep.queries <= bound
        rows.append({"N": N, "D": D, "tau": tau, "M": M, "heavy": len(truth), "queries": rep.queries, "bound": round(bound, 1), "status": "checked" if ok else "FAIL"})
        if not ok:
            raise AssertionError(rows[-1])
    return rows


def sieve_instances(rng: random.Random) -> list[dict]:
    """Sieve-shaped X, Y: positions x residue states, residue states x lines."""
    rows = []
    y = 47
    primes = primes_upto(y)
    weights = {p: round(100 * math.log(p)) for p in primes}
    for N in (16, 32, 64, 128, 256, 512):
        lines = N
        root_sets = [{p: set(rng.sample(range(p), 2 if p > 2 else 1)) for p in primes} for _ in range(lines)]
        X = np.array(build_X(N, primes))
        Y = np.array(build_Y(primes, root_sets, weights))
        D = X.shape[1]
        P = X.astype(np.int64) @ Y.astype(np.int64)
        M = int(P.sum())
        mean_score = M / (N * lines)
        for u in (1.0, 2.0, 4.0, 8.0):
            tau = int(u * 100 * math.log(y))  # "u log y" threshold, same 100x scaling as the weights
            truth = {(int(i), int(j)) for i, j in zip(*np.nonzero(P >= tau))}
            rep = DyadicReporter(X, Y)
            got = rep.report(tau)
            assert got == truth
            bound = 1 + 4 * (M / tau) * int(math.log2(N))
            assert rep.queries <= bound
            cells = N * lines
            rows.append(
                {
                    "N": N,
                    "lines": lines,
                    "D": D,
                    "y": y,
                    "mean_score_over_log_y": round(mean_score / (100 * math.log(y)), 3),
                    "u": u,
                    "tau": tau,
                    "M_over_tau": round(M / tau, 1),
                    "heavy_cells": len(truth),
                    "heavy_fraction": round(len(truth) / cells, 4),
                    "queries": rep.queries,
                    "queries_over_cells": round(rep.queries / cells, 3),
                    "bound_1+4(M/tau)log2N": round(bound, 1),
                    "modelled_cost_terms": {
                        "N^2/D^0.063": round(N**2 / D**PRE_EXP, 1),
                        "(M/tau)*D^0.437": round((M / tau) * D**QUERY_EXP, 1),
                        "N*D": N * D,
                        "plain_scan_cells": cells,
                    },
                    "status": "checked",
                }
            )
            print(f"N={N} u={u} (mean score = {rows[-1]['mean_score_over_log_y']} log y): heavy {len(truth)}/{cells} ({rows[-1]['heavy_fraction']}), queries/cells={rows[-1]['queries_over_cells']}, M/tau={rows[-1]['M_over_tau']}")
    return rows


def main() -> None:
    rng = random.Random(20261006)
    res = {
        "construction": "dyadic aggregates as extra rows/columns; split rectangles with sum >= tau; reports all cells >= tau exactly for nonnegative scores",
        "query_bound": "queries <= 1 + 4 (M/tau) log2 N",
        "random_instances": random_instances(rng),
        "sieve_instances": sieve_instances(rng),
        "screen_derived": "NFS log sieve: M = N^(2+o(1)) log y, tau = u log y, u = N^o(1) => M/tau = N^(2-o(1)) queries; beating a scan needs u >> D^0.437",
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as fh:
        json.dump(res, fh, indent=1)
    print(f"random instances checked: {len(res['random_instances'])}")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()

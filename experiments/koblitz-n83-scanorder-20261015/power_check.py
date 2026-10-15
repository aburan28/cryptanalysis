#!/usr/bin/env python3
"""Power of the frozen decision rules, computed before freezing (model, not data).

Probe counts stand in for online time (the online interval is 99.99% PDP,
whose cost is per probe). The fixed (feistel) arm is drawn as Exp(law), the
geometric law a uniformly random order gives. The left-major arm is drawn
from the representation model of `receipt_blocks.py` (each of Poisson(lambda)
four-term representations hits 3 states in each of its 4 left-orbit blocks;
uniform start), except on the 16 fresh points, where it is B's archived
probes (fixed). Each simulated experiment applies the frozen statistic: the
section-23 ratio of means, bootstrap over targets, improvement iff the 95%
lower bound exceeds 1. Writes `analysis/power.json`.
"""

import json
import math
import random
from pathlib import Path

HERE = Path(__file__).resolve().parent
K, N = 600, 83
S, BLOCK = K * K * N, K * N
LAW = 8569786107849059 / (2 * N * S)
LAMBDA = math.comb(K * 2 * N, 4) / 8569786107849059


def left_major(rng):
    reps, p = 0, math.exp(-LAMBDA)
    cdf, u = p, rng.random()
    while u > cdf:
        reps += 1
        p *= LAMBDA / reps
        cdf += p
    hits = []
    for _ in range(reps):
        orbits = rng.sample(range(K), 4)
        hits += [a * BLOCK + b * N + rng.randrange(N) for a in orbits for b in orbits if a != b]
    s0 = rng.randrange(S)
    return (min((h - s0) % S for h in hits) + 1) * 4 * N


def lower_bound(pairs, rng, draws=1000):
    n = len(pairs)
    values = sorted(sum(a for a, _ in s) / sum(b for _, b in s)
                    for s in ([pairs[rng.randrange(n)] for _ in range(n)] for _ in range(draws)))
    return values[int(0.025 * draws)]


def main():
    rng = random.Random(20261015)
    archived = [r["probes"] for r in json.loads((HERE / "analysis/receipt_blocks.json").read_text())["rows"]
                if r["point_id"] != "q0"]
    pool = [left_major(rng) for _ in range(3000)]
    trials = 400
    out = {"law_probes": LAW, "lambda": LAMBDA, "trials": trials, "bootstrap_draws": 1000, "seed": 20261015,
           "model_left_major_mean_over_law": sum(pool) / len(pool) / LAW}
    wins = 0
    for _ in range(trials):
        pairs = [(b, rng.expovariate(1 / LAW)) for b in archived]
        wins += lower_bound(pairs, rng) > 1
    out["primary_16_fresh_points"] = {"power": wins / trials,
                                      "baseline": "B's archived probes (fixed)", "fixed": "Exp(law)"}
    for npts in (64, 192, 384):
        wins = 0
        for _ in range(trials // 2):
            pairs = [(rng.choice(pool), rng.expovariate(1 / LAW)) for _ in range(npts)]
            wins += lower_bound(pairs, rng) > 1
        out["heldout_%d_points" % npts] = {"power": wins / (trials // 2),
                                            "baseline": "representation model", "fixed": "Exp(law)"}
    (HERE / "analysis" / "power.json").write_text(json.dumps(out, indent=1, sort_keys=True) + "\n")
    print(json.dumps(out, sort_keys=True))


if __name__ == "__main__":
    main()

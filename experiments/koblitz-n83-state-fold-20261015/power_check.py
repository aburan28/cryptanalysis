#!/usr/bin/env python3
"""Power of the frozen primary before freezing (`analysis/power.json`).

Model (a simulation over the prior `inputs/power_prior.json`, measured on
run 38786433493's Tier 1 runner):

* baseline cold total per point = one process setup drawn from the 96
  measured one-target IC setups + one online time drawn from the 384
  measured Feistel held-out online times, divided by 1.5 (lift_scan);
* the folded arm uses the same point's online time (the fold reproduces the
  baseline's relation exactly) times 1.02 (a 2% online slowdown allowance),
  and its own setup draw divided by k, with k chosen so that the expected
  cold-total ratio of means equals the effect `delta`;
* the A/A arm is a second folded draw.

Per simulated experiment: the frozen statistic (ratio of mean cold totals,
baseline / folded, bootstrap over points, 2,000 resamples here, 10,000 in the
real verifier) and the A/A gate (point estimate inside [0.97, 1.03]). Power
is P(lower bound > 1 and A/A passes). The panel size is the smallest size in
SIZES whose power at the minimal effect of interest MIN_DELTA is at least
0.80 after subtracting two Monte Carlo standard errors.
"""

import json
import math
import random
import statistics
from pathlib import Path

HERE = Path(__file__).resolve().parent
SIZES = (8, 12, 16, 24, 32)
DELTAS = (1.03, 1.05, 1.10, 1.50)
MIN_DELTA = 1.05
SIMS = 400
BOOT = 2000
SEED = 2026101599


def ratio_of_means(pairs):
    return sum(b for b, _ in pairs) / sum(f for _, f in pairs)


def one(rng, size, delta, setups, onlines):
    mean_setup = statistics.mean(setups)
    mean_online = statistics.mean(onlines) / 1.5
    # E[B] / E[F] = delta  ->  (s + o) / (s / k + 1.02 o) = delta
    k = mean_setup / ((mean_setup + mean_online) / delta - 1.02 * mean_online)
    pairs, aa = [], []
    for _ in range(size):
        online = rng.choice(onlines) / 1.5
        base = rng.choice(setups) + online
        fold = rng.choice(setups) / k + 1.02 * online
        fold_aa = rng.choice(setups) / k + 1.02 * online
        pairs.append((base, fold))
        aa.append((fold, fold_aa))
    draws = sorted(ratio_of_means([pairs[rng.randrange(size)] for _ in range(size)]) for _ in range(BOOT))
    lower = draws[int(0.025 * BOOT)]
    aa_ok = 0.97 <= ratio_of_means(aa) <= 1.03
    return lower > 1.0 and aa_ok


def main():
    prior = json.loads((HERE / "inputs" / "power_prior.json").read_text())
    setups, onlines = prior["setup_ms"], prior["online_ms"]
    rng = random.Random(SEED)
    table = {}
    for delta in DELTAS:
        for size in SIZES:
            hits = sum(one(rng, size, delta, setups, onlines) for _ in range(SIMS))
            power = hits / SIMS
            table["%s@%d" % (delta, size)] = {"power": power,
                                              "mc_se": math.sqrt(power * (1 - power) / SIMS)}
    chosen = next(size for size in SIZES
                  if table["%s@%d" % (MIN_DELTA, size)]["power"]
                  - 2 * table["%s@%d" % (MIN_DELTA, size)]["mc_se"] >= 0.80)
    out = {"schema": 1, "model": __doc__.strip(), "sizes": SIZES, "deltas": DELTAS,
           "min_delta": MIN_DELTA, "simulations": SIMS, "bootstrap": BOOT, "seed": SEED,
           "prior_setup_mean_ms": statistics.mean(setups),
           "prior_setup_cv": statistics.stdev(setups) / statistics.mean(setups),
           "prior_online_mean_ms_lift": statistics.mean(onlines) / 1.5,
           "power": table, "chosen_panel_size": chosen,
           "expected_effect_note": ("local smoke (no timing claim) put the folded index build at about "
                                    "half the unfolded one; at the prior's setup that is a cold ratio "
                                    "near 1.7-1.9, far above MIN_DELTA")}
    (HERE / "analysis" / "power.json").write_text(json.dumps(out, indent=1, sort_keys=True) + "\n")
    print(json.dumps({"chosen_panel_size": chosen,
                      "power_at_min_delta": {s: table["%s@%d" % (MIN_DELTA, s)]["power"] for s in SIZES}}))


if __name__ == "__main__":
    main()

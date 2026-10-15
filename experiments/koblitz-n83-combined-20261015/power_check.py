#!/usr/bin/env python3
"""Power of the frozen primary rule, computed before freezing (simulation, not data).

The target population is the earlier 384-point held-out panel of
`claude/n83-scan-order` run 38786433493 (`inputs/power_prior.json`): for each
of its targets, the measured left-major full-scan online time `tB` and the
Feistel full-scan online time `tP`. A simulated target is one row drawn with
replacement. Its four arms are

* B  = tB                (left-major, full scan),
* L  = tB / k1           (left-major, lift_scan),
* F  = tP                (Feistel, full scan),
* LF = tP / k2           (Feistel, lift_scan),

with k1, k2 drawn from the 16 per-point full / lift_scan online ratios of
`claude/n83-liftscan` run 38776966036 (lift_scan leaves the probes and the
relation unchanged, so it divides the time), and every arm multiplied by an
independent lognormal timing noise of sigma 0.02 (larger than the A/A spread
of either run). Each simulated experiment applies the frozen primary rule to
N targets: the ratio of means R_m = min(mean L, mean F) / mean LF and the
ratio of geometric means R_g = min(gm L, gm F) / gm LF, the minimum taken
inside every bootstrap resample (10,000 in the protocol, 2,000 here), and an
improvement iff both 95% lower bounds exceed 1.

Two effect scenarios:

* `measured`: the rows as measured (held-out B/F ratio of means 1.45,
  geometric means 1.27);
* `shrunk`: every tB scaled by one constant so that the B/F ratio of
  means is 1.30 (the low end of the representation model's 1.33-1.36),
  which also shrinks the geometric-mean ratio by the same factor; a stress
  test of the size choice, not the sizing scenario.

The panel size is the smallest N in SIZES whose simulated power for the
rule (both bounds) in the `measured` scenario is at least 80% after
subtracting two Monte Carlo standard errors (sqrt(p(1-p)/TRIALS)), so the
80% floor is not met by simulation noise alone.

Writes `analysis/power.json`. numpy is used for speed; the frozen verifier
itself is pure Python.
"""

import json
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
SIZES = (256, 384, 448, 512, 576, 640)
TRIALS = 400
DRAWS = 2000
SIGMA = 0.02
SEED = 2026101599


def lower_bounds(arms, rng):
    """95% lower bounds of R_m and R_g over DRAWS resamples of the N targets."""
    n = arms.shape[1]
    idx = rng.integers(0, n, size=(DRAWS, n))
    sample = arms[:, idx]                      # (4, DRAWS, n): B, L, F, LF
    means = sample.mean(axis=2)
    logs = np.log(sample).mean(axis=2)
    r_m = np.minimum(means[1], means[2]) / means[3]
    r_g = np.exp(np.minimum(logs[1], logs[2]) - logs[3])
    k = int(0.025 * DRAWS)
    return np.sort(r_m)[k], np.sort(r_g)[k]


def simulate(tb, tp, ks, n, rng):
    pick = rng.integers(0, len(tb), size=n)
    b, p = tb[pick], tp[pick]
    k1, k2 = rng.choice(ks, size=n), rng.choice(ks, size=n)
    arms = np.stack([b, b / k1, p, p / k2])
    return arms * np.exp(rng.normal(0.0, SIGMA, size=arms.shape))


def main():
    prior = json.loads((HERE / "inputs" / "power_prior.json").read_text())
    rows = prior["scanorder_heldout"]["rows"]
    tb = np.array([r["left_major_full_online_ms"] for r in rows])
    tp = np.array([r["feistel_full_online_ms"] for r in rows])
    ks = np.array(prior["liftscan_fresh"]["per_unit"])
    scenarios = {"measured": tb, "shrunk": tb * (1.30 * tp.mean() / tb.mean())}
    rng = np.random.default_rng(SEED)
    out = {"seed": SEED, "trials": TRIALS, "bootstrap_draws": DRAWS, "timing_noise_sigma": SIGMA,
           "rule": "improvement iff the 95% lower bounds of both R_m = min(mean L, mean F) / mean LF and "
                   "R_g = min(gm L, gm F) / gm LF exceed 1 (min inside each resample)",
           "lift_ratio_mean": float(ks.mean()), "scenarios": {}}
    for name, base in scenarios.items():
        population = {"B_over_F_ratio_of_means": float(base.mean() / tp.mean()),
                      "B_over_F_ratio_of_geomeans": float(np.exp(np.log(base).mean() - np.log(tp).mean())),
                      "expected_R_m": float(min(base.mean() / ks.mean(), tp.mean()) / (tp.mean() / ks.mean())),
                      "expected_R_g": float(np.exp(min(np.log(base).mean(), np.log(tp).mean() + np.log(ks).mean())
                                                   - np.log(tp).mean())),
                      "power": {}}
        for n in SIZES:
            wins_m = wins_g = wins = 0
            for _ in range(TRIALS):
                lb_m, lb_g = lower_bounds(simulate(base, tp, ks, n, rng), rng)
                wins_m += lb_m > 1
                wins_g += lb_g > 1
                wins += lb_m > 1 and lb_g > 1
            population["power"][str(n)] = {"ratio_of_means": wins_m / TRIALS, "geomeans": wins_g / TRIALS,
                                           "both": wins / TRIALS}
            print(name, n, population["power"][str(n)], flush=True)
        out["scenarios"][name] = population
    def floor(p):
        return p - 2 * (p * (1 - p) / TRIALS) ** 0.5
    out["power_floor_rule"] = "power - 2 * sqrt(power * (1 - power) / trials) >= 0.80, measured scenario, both bounds"
    out["chosen_panel_size"] = min(n for n in SIZES
                                   if floor(out["scenarios"]["measured"]["power"][str(n)]["both"]) >= 0.8)
    (HERE / "analysis").mkdir(exist_ok=True)
    (HERE / "analysis" / "power.json").write_text(json.dumps(out, indent=1, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Power of the frozen primary rule, computed before freezing (simulation, not data).

Primary rule: improvement iff the 95% lower bound of R_m = mean pC / mean pP
(ratio of means of online time over the primary points, bootstrap over
points) exceeds 1.

Population (`inputs/power_prior.json`, copied from `claude/n83-combined`):
the 384 old held-out targets' measured Feistel full-scan online times
(`claude/n83-scan-order` run 38786433493), divided by the measured mean
full / lift_scan ratio (run 38776966036), as a stand-in for the combined
producer's per-target time. A simulated target is one row drawn with
replacement. The pipeline leaves the probes and relation unchanged, so it
divides the time: pP = pC / k, where k is the effect scenario times a
per-point factor drawn from the 16 measured full / lift_scan ratios
normalized to mean 1 (the dispersion of a measured probe-preserving
per-probe change, one outlier included). Timing noise: an independent
lognormal sigma 0.02 per arm and target, and a process-level lognormal
sigma 0.01 shared by the 64 targets of one arm's slice process.

Effect scenarios: the minimal effect of interest 1.03 (the A/A band's
edge, the sizing scenario) and 1.10 (reported).

The panel size is the smallest N in SIZES whose power in the 1.03
scenario is at least 80% after subtracting two Monte Carlo standard
errors, raised to the design floor of 384 points (six 64-point slices, so
that the slice-level sensitivity bootstrap has six clusters).

Writes `analysis/power.json`. numpy is used for speed; the frozen verifier
itself is pure Python.
"""

import json
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
SIZES = (64, 128, 192, 256, 320, 384)
FLOOR = 384
SLICE = 64
TRIALS = 400
DRAWS = 2000
SIGMA = 0.02
SIGMA_PROCESS = 0.01
SEED = 2026101577
SCENARIOS = {"mei_1.03": 1.03, "effect_1.10": 1.10}


def lower_bound(c, p, rng):
    n = c.shape[0]
    idx = rng.integers(0, n, size=(DRAWS, n))
    r = c[idx].sum(axis=1) / p[idx].sum(axis=1)
    return np.sort(r)[int(0.025 * DRAWS)]


def simulate(times, spread, effect, n, rng):
    pick = rng.integers(0, len(times), size=n)
    c = times[pick]
    k = effect * rng.choice(spread, size=n)
    p = c / k
    slices = (n + SLICE - 1) // SLICE
    shifts = np.exp(rng.normal(0.0, SIGMA_PROCESS, size=(2, slices)))
    which = np.arange(n) // SLICE
    c = c * shifts[0][which] * np.exp(rng.normal(0.0, SIGMA, size=n))
    p = p * shifts[1][which] * np.exp(rng.normal(0.0, SIGMA, size=n))
    return c, p


def main():
    prior = json.loads((HERE / "inputs" / "power_prior.json").read_text())
    ks = np.array(prior["liftscan_fresh"]["per_unit"])
    times = np.array([r["feistel_full_online_ms"] for r in prior["scanorder_heldout"]["rows"]]) / ks.mean()
    spread = ks / ks.mean()
    rng = np.random.default_rng(SEED)
    out = {"seed": SEED, "trials": TRIALS, "bootstrap_draws": DRAWS, "timing_noise_sigma": SIGMA,
           "process_noise_sigma": SIGMA_PROCESS, "slice": SLICE,
           "rule": "improvement iff the 95% lower bound of R_m = mean pC / mean pP exceeds 1",
           "per_point_effect_spread_cv": float(spread.std()), "population_mean_ms": float(times.mean()),
           "scenarios": {}}
    for name, effect in SCENARIOS.items():
        power = {}
        for n in SIZES:
            wins = sum(lower_bound(*simulate(times, spread, effect, n, rng), rng) > 1 for _ in range(TRIALS))
            power[str(n)] = wins / TRIALS
            print(name, n, power[str(n)], flush=True)
        out["scenarios"][name] = {"effect": effect, "power": power}

    def floor(p):
        return p - 2 * (p * (1 - p) / TRIALS) ** 0.5
    powered = [n for n in SIZES if floor(out["scenarios"]["mei_1.03"]["power"][str(n)]) >= 0.8]
    out["power_floor_rule"] = ("power - 2 * sqrt(power * (1 - power) / trials) >= 0.80 in the 1.03 scenario; "
                               "then at least the design floor of %d points" % FLOOR)
    out["smallest_powered_size"] = min(powered) if powered else None
    out["chosen_panel_size"] = max(FLOOR, out["smallest_powered_size"] or FLOOR)
    if not powered or floor(out["scenarios"]["mei_1.03"]["power"][str(out["chosen_panel_size"])]) < 0.8:
        raise SystemExit("no size in SIZES reaches the power floor")
    (HERE / "analysis").mkdir(exist_ok=True)
    (HERE / "analysis" / "power.json").write_text(json.dumps(out, indent=1, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()

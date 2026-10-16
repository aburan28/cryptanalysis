#!/usr/bin/env python3
"""Power of the frozen primary before freezing (`analysis/power.json`).

Prior: `inputs/power_prior.json` (run 38819494806's 16 cold points and four
rank-stage processes, plus three measured online factors from main's runs).

Model of one simulated experiment with N cold points and B = 2 rank blocks:

* baseline pP, per point: cold = a setup drawn from the unfolded cB setups
  + that point's cB online time / 1.4001 (the probe pipeline); rank stage per
  block = the sum of 600 attempts drawn from B's kB attempts (pP's rank stage
  is B's, on the 32-byte table, unchanged);
* stack, per point: cold = a setup drawn from the folded cF setups / 1.0364
  (16-byte slots, setup) / k + the same point's pP online time / 0.9490 (the
  fold's online cost) / 1.0581 (the slots' online gain); rank stage per
  block = the sum of 600 attempts drawn from the folded lift + Feistel kN
  attempts / (1.4001 x 1.0581) / k (the pipeline and the slots on the rank
  scan; kN already has the fold);
* k = 1 is the prior's expected stack; for a power curve k is chosen so
  that the expected end-to-end ratio equals delta;
* an A/A stack arm repeats the stack: independent setup draws, and the
  same rank attempts (the same rank seeds give the same attempt sequence)
  with lognormal timing noise sigma 0.01 per rank process.

Per simulated experiment: the frozen statistic R = E2E(pP) / E2E(stack),
E2E = mean rank stage + mean cold, with its bootstrap (points resampled with
replacement, attempts resampled within each rank process), BOOT draws here
(10,000 in the verifier), and the A/A gate (point estimate inside
[0.97, 1.03]). Power = P(lower bound > 1 and A/A passes). The chosen size is
the smallest size in SIZES with power - 2 MC SE >= 0.80 at MIN_DELTA.

MIN_DELTA = 1.15. The rank stage dominates both arms' end-to-end cost and
each arm has two rank processes, so the attempt-level variance of the rank
stage, not the number of points, limits the resolution (a third block was
simulated: power at 1.15 rose from about 0.91 to 0.95 for about 32 more
minutes of runner time, so it was not added). The prior's own expected
ratio (`expected_e2e_ratio_under_prior`) is far above MIN_DELTA; every
component of the stack was already promoted separately, so the question
here is the size of the end-to-end move, not whether a 5% effect exists.

A secondary power figure: the fold's online cost inside the stack (online
stack-minus-fold / stack, expected 0.949), as a paired per-point online
ratio with lognormal process noise sigma 0.02 per arm: P(the 95% interval
excludes 1).
"""

import json
import math
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
SIZES = (4, 8, 12, 16, 20)
DELTAS = (1.10, 1.15, 1.25, 1.50)
MIN_DELTA = 1.15
SIMS = 300
BOOT = 1000
SEED = 2026101601
ATTEMPTS = 600
BLOCKS = 2


def load():
    prior = json.loads((HERE / "inputs" / "power_prior.json").read_text())
    f = prior["factors"]
    cb = prior["cold"]["cB"]
    cf = prior["cold"]["cF"]
    online_p = np.array([cb[k]["online_ms"] for k in sorted(cb)]) / f["probe_pipeline_online"]
    setup_p = np.array([v["setup_ms"] for v in cb.values()])
    setup_s = np.array([v["setup_ms"] for v in cf.values()]) / f["compact_slot_setup_pP_over_pK"]
    online_factor_s = 1.0 / f["fold_online_cB_over_cF"] / f["compact_slot_online"]
    att_p = np.concatenate([np.array(r["attempt_ns"], float) for r in prior["rank"]["kB"]]) / 1e6
    att_s = (np.concatenate([np.array(r["attempt_ns"], float) for r in prior["rank"]["kN"]]) / 1e6
             / (f["probe_pipeline_online"] * f["compact_slot_online"]))
    return online_p, setup_p, setup_s, online_factor_s, att_p, att_s


def expected(online_p, setup_p, setup_s, of, att_p, att_s, k):
    e2e_p = ATTEMPTS * att_p.mean() + setup_p.mean() + online_p.mean()
    e2e_s = (ATTEMPTS * att_s.mean() + setup_s.mean()) / k + of * online_p.mean()
    return e2e_p / e2e_s


def k_for(delta, *prior):
    lo, hi = 1e-3, 1e3
    for _ in range(200):
        mid = math.sqrt(lo * hi)
        if expected(*prior, mid) > delta:
            hi = mid
        else:
            lo = mid
    return math.sqrt(lo * hi)


def simulate(rng, size, k, online_p, setup_p, setup_s, of, att_p, att_s):
    point = rng.integers(0, len(online_p), size)
    onl = online_p[point]
    cold_p = rng.choice(setup_p, size) + onl
    cold_s = rng.choice(setup_s, size) / k + of * onl
    cold_aa = rng.choice(setup_s, size) / k + of * onl
    blocks_p = rng.choice(att_p, (BLOCKS, ATTEMPTS))
    blocks_s = rng.choice(att_s, (BLOCKS, ATTEMPTS)) / k
    # The A/A rank arm runs the same rank seeds, so the same attempts; only
    # timing noise (lognormal, sigma 0.01 per process) differs.
    blocks_aa = blocks_s * np.exp(rng.normal(0.0, 0.01, (BLOCKS, 1)))
    e2e = lambda blocks, cold: blocks.sum(axis=-1).mean(axis=-1) + cold.mean(axis=-1)
    estimate_aa = e2e(blocks_s, cold_s) / e2e(blocks_aa, cold_aa)
    idx = rng.integers(0, size, (BOOT, size))
    rp = np.take_along_axis(blocks_p[None].repeat(BOOT, 0),
                            rng.integers(0, ATTEMPTS, (BOOT, BLOCKS, ATTEMPTS)), axis=2)
    rs = np.take_along_axis(blocks_s[None].repeat(BOOT, 0),
                            rng.integers(0, ATTEMPTS, (BOOT, BLOCKS, ATTEMPTS)), axis=2)
    ratios = e2e(rp, cold_p[idx]) / e2e(rs, cold_s[idx])
    lower = np.quantile(ratios, 0.025)
    return bool(lower > 1.0 and 0.97 <= estimate_aa <= 1.03)


def fold_online_power(rng, size, sims=SIMS):
    hits = 0
    for _ in range(sims):
        base = rng.lognormal(0.0, 1.0, size)
        stack = base * np.exp(rng.normal(0, 0.02, size))
        minus_fold = base * 0.949 * np.exp(rng.normal(0, 0.02, size))
        idx = rng.integers(0, size, (BOOT, size))
        draws = minus_fold[idx].sum(1) / stack[idx].sum(1)
        hi = np.quantile(draws, 0.975)
        hits += hi < 1.0
    return hits / sims


def main():
    prior = load()
    rng = np.random.default_rng(SEED)
    expected_ratio = expected(*prior, 1.0)
    table = {}
    for delta in DELTAS:
        k = k_for(delta, *prior)
        for size in SIZES:
            hits = sum(simulate(rng, size, k, *prior) for _ in range(SIMS))
            power = hits / SIMS
            table["%s@%d" % (delta, size)] = {"power": power, "mc_se": math.sqrt(power * (1 - power) / SIMS),
                                              "k": k}
    chosen = next(size for size in SIZES
                  if table["%s@%d" % (MIN_DELTA, size)]["power"]
                  - 2 * table["%s@%d" % (MIN_DELTA, size)]["mc_se"] >= 0.80)
    fold_power = {str(size): fold_online_power(rng, size) for size in (8, 16, 20)}
    online_p, setup_p, setup_s, of, att_p, att_s = prior
    out = {"schema": 1, "model": __doc__.strip(), "sizes": SIZES, "deltas": DELTAS,
           "min_delta": MIN_DELTA, "simulations": SIMS, "bootstrap": BOOT, "seed": SEED,
           "numpy": np.__version__,
           "expected_e2e_ratio_under_prior": expected_ratio,
           "expected_ms": {"pP_rank_stage": ATTEMPTS * float(att_p.mean()),
                           "stack_rank_stage": ATTEMPTS * float(att_s.mean()),
                           "pP_cold": float(setup_p.mean() + online_p.mean()),
                           "stack_cold": float(setup_s.mean() + of * online_p.mean())},
           "power": table, "chosen_panel_size": chosen,
           "secondary_fold_online_cost_power": fold_power}
    path = HERE / "analysis" / "power.json"
    path.write_text(json.dumps(out, indent=1, sort_keys=True) + "\n")
    print(json.dumps({"chosen_panel_size": chosen, "expected_e2e_ratio_under_prior": expected_ratio,
                      "power_at_min_delta": {s: table["%s@%d" % (MIN_DELTA, s)]["power"] for s in SIZES},
                      "fold_online_power": fold_power}, sort_keys=True))


if __name__ == "__main__":
    main()

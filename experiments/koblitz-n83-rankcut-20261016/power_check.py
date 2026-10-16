#!/usr/bin/env python3
"""Power of the frozen primary rule for the number of rank blocks (before any timing).

Simulates the primary statistic R = E2E(kS, cS) / E2E(kR, cR) with the
frozen bootstrap (`verify_receipt.py`: rank blocks resampled, then attempt
indices resampled within each drawn block and paired across kS and kR, and
the cold points resampled, paired across cS and cR) from the prior
`inputs/power_prior.json` (run 38862448935):

* a simulated block draws one archived block (seed 101 or 102) and resamples
  its 600 attempts; kS_i is the archived kS attempt, and the candidate's
  attempt is kR_i = kS_i * (kSaa_i / kS_i) / e, i.e. the archived paired A/A
  noise of that attempt divided by the rank-stage effect e; each block also
  gets a process-level factor drawn from the archived per-process A/A ratios;
* cold: 20 points resampled from the archived 20; cS = archived cS, cR =
  archived cSaa (the candidate's cold path is the baseline's code).

The rank-stage effect e is set so that the END-TO-END ratio equals the
effect of interest. Power = share of simulations whose 95% lower bound
exceeds 1. The chosen block count is the smallest of BLOCKS whose power at
the minimal effect of interest (MIN_DELTA, end to end) minus two Monte Carlo
standard errors is at least 0.80, and at least MIN_BLOCKS; the design runs
it if it fits the runner's time budget. `--quick` is for development only.
"""

import argparse
import json
import math
import random
import statistics
from pathlib import Path

HERE = Path(__file__).resolve().parent
PRIOR = HERE / "inputs" / "power_prior.json"
OUT = HERE / "analysis" / "power.json"
BLOCKS = (2, 3, 4)
MIN_BLOCKS = 4
EFFECTS = (1.0, 1.03, 1.05, 1.10)
MIN_DELTA = 1.05
SIMULATIONS = 200
DRAWS = 300
POINTS = 20
SEED = 2026101690


def e2e_bootstrap(blocks, cold, rng, draws):
    """blocks: [(rest_a, rest_b, [(a_i, b_i)])]; cold: [(ca, cb)]. Returns (estimate, lo, hi)."""
    def value(block_draw, attempt_draws, cold_draw):
        rank_a = rank_b = 0.0
        for (rest_a, rest_b, attempts), picks in zip(block_draw, attempt_draws):
            rank_a += rest_a + sum(attempts[i][0] for i in picks)
            rank_b += rest_b + sum(attempts[i][1] for i in picks)
        k = len(block_draw)
        return (rank_a / k + statistics.mean(c[0] for c in cold_draw)) / (
            rank_b / k + statistics.mean(c[1] for c in cold_draw))

    full = [range(len(b[2])) for b in blocks]
    point = value(blocks, full, cold)
    values = []
    for _ in range(draws):
        bd = [blocks[rng.randrange(len(blocks))] for _ in blocks]
        ad = [[rng.randrange(len(b[2])) for _ in range(len(b[2]))] for b in bd]
        cd = [cold[rng.randrange(len(cold))] for _ in cold]
        values.append(value(bd, ad, cd))
    values.sort()
    return point, values[int(0.025 * draws)], values[int(0.975 * draws) - 1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quick", action="store_true")
    args = parser.parse_args()
    sims = 40 if args.quick else SIMULATIONS
    prior = json.loads(PRIOR.read_text())
    archived = []
    for seed, b in sorted(prior["rank_blocks"].items()):
        pairs = list(zip(b["kS_attempt_ns"], b["kSaa_attempt_ns"]))
        archived.append({"rest": b["kS_non_attempt_ms"],
                         "kS_ms": [a / 1e6 for a, _ in pairs],
                         "noise": [aa / a for a, aa in pairs],
                         "process_aa": sum(aa for _, aa in pairs) / sum(a for a, _ in pairs)})
    process_factors = [blk["process_aa"] for blk in archived]
    cold = [(v["cS"], v["cSaa"]) for _, v in sorted(prior["cold_ms"].items())]
    mean_rank = statistics.mean(blk["rest"] + sum(blk["kS_ms"]) for blk in archived)
    mean_cold = statistics.mean(c[0] for c in cold)

    def rank_effect(e2e_effect):
        # (rank + cold) / (rank / e + cold) = E  ->  e = rank / ((rank + cold) / E - cold)
        return mean_rank / ((mean_rank + mean_cold) / e2e_effect - mean_cold)

    rng = random.Random(SEED)
    table = {}
    for effect in EFFECTS:
        e = rank_effect(effect)
        row = {}
        for k in BLOCKS:
            hits = 0
            for _ in range(sims):
                blocks = []
                for _ in range(k):
                    blk = archived[rng.randrange(len(archived))]
                    factor = process_factors[rng.randrange(len(process_factors))]
                    idx = [rng.randrange(len(blk["kS_ms"])) for _ in blk["kS_ms"]]
                    attempts = [(blk["kS_ms"][i], blk["kS_ms"][i] * blk["noise"][i] * factor / e) for i in idx]
                    blocks.append((blk["rest"], blk["rest"], attempts))
                pts = [cold[rng.randrange(len(cold))] for _ in range(POINTS)]
                _, lo, _ = e2e_bootstrap(blocks, pts, rng, DRAWS)
                hits += lo > 1.0
            power = hits / sims
            row[str(k)] = {"power": power, "mc_se": math.sqrt(max(power * (1 - power), 1e-12) / sims)}
        table["%.2f" % effect] = {"rank_stage_effect": e, "by_blocks": row}
    at_min = table["%.2f" % MIN_DELTA]["by_blocks"]
    passing = [k for k in BLOCKS if at_min[str(k)]["power"] - 2 * at_min[str(k)]["mc_se"] >= 0.80]
    chosen = max(MIN_BLOCKS, min(passing)) if passing else None
    result = {"schema": 1, "prior": "inputs/power_prior.json", "prior_source": prior["source"],
              "statistic": "R = E2E(kS, cS) / E2E(kR, cR), 95% lower bound > 1",
              "bootstrap": ("rank blocks resampled; attempt indices resampled within each drawn block, paired "
                            "across kS and kR; cold points resampled, paired; %d draws per simulation "
                            "(10,000 in the frozen verifier)" % DRAWS),
              "simulations": sims, "points": POINTS, "min_delta": MIN_DELTA, "min_blocks": MIN_BLOCKS,
              "mean_rank_stage_ms_prior": mean_rank, "mean_cold_ms_prior": mean_cold,
              "power": table, "chosen_rank_blocks": chosen,
              "type_i_at_1.00": {k: v["power"] for k, v in table["1.00"]["by_blocks"].items()},
              "expected_e2e_ratio_under_local_profile": (
                  "about 1.2-1.3 if the local per-probe ratio (about 1.3-1.4, smoke/, diagnostic) holds on the "
                  "runner; not an input of this check"),
              "quick": args.quick}
    if not args.quick:
        OUT.write_text(json.dumps(result, indent=1, sort_keys=True) + "\n")
    print(json.dumps({"chosen_rank_blocks": chosen,
                      "power": {e: {k: round(v["power"], 3) for k, v in t["by_blocks"].items()}
                                for e, t in table.items()}}, sort_keys=True))


if __name__ == "__main__":
    main()

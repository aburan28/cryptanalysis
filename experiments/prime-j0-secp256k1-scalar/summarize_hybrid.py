#!/usr/bin/env python3
"""Descriptive paired input-law uncertainty for the hybrid holdout."""

import json
from pathlib import Path
import random
import statistics


HERE = Path(__file__).resolve().parent
SEED = 0x20261007
RESAMPLES = 10_000


def main():
    result = json.loads((HERE / "hybrid-holdout-result.json").read_text())
    assert result["verified"] and len(result["rows"]) == 64
    deltas = [
        row["arms"]["width4"]["actual_source_cost"]["m_plus_s_excluding_inversion"] -
        row["arms"]["fixed_hybrid"]["actual_source_cost"]["m_plus_s_excluding_inversion"]
        for row in result["rows"]
    ]
    rng = random.Random(SEED)
    means = sorted(statistics.mean(rng.choices(deltas, k=len(deltas)))
                   for _ in range(RESAMPLES))
    print(json.dumps({
        "cases": len(deltas), "seed_hex": hex(SEED),
        "resamples": RESAMPLES,
        "mean_saved_m_plus_s": statistics.mean(deltas),
        "median_saved_m_plus_s": statistics.median(deltas),
        "sample_sd_m_plus_s": statistics.stdev(deltas),
        "descriptive_bootstrap_95_mean": [means[249], means[9749]],
        "cpu_timing_uncertainty": None,
    }, sort_keys=True))


if __name__ == "__main__":
    main()

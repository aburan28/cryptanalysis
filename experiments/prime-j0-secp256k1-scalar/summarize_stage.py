#!/usr/bin/env python3
"""Recompute descriptive paired uncertainty from frozen stage-result.json."""

import json
import random
import statistics
from pathlib import Path


HERE = Path(__file__).resolve().parent
RESAMPLES = 10000
SEED = 0x45120261007


def main():
    result = json.loads((HERE / "stage-result.json").read_text())
    rows = result["cases"]
    saved = [row["formula_m_saved"] for row in rows]
    control = [row["control_formula_m"] for row in rows]
    assert len(rows) == 128 and all(row["verified"] for row in rows)
    assert sum(saved) == result["totals"]["m_saved"]
    assert sum(control) == result["totals"]["control_m"]
    rng = random.Random(SEED)
    mean_samples, ratio_samples = [], []
    for _ in range(RESAMPLES):
        indexes = [rng.randrange(len(rows)) for _ in rows]
        sample_saved = sum(saved[index] for index in indexes)
        sample_control = sum(control[index] for index in indexes)
        mean_samples.append(sample_saved / len(rows))
        ratio_samples.append(100 * sample_saved / sample_control)
    mean_samples.sort()
    ratio_samples.sort()
    summary = {
        "cases": len(rows), "saved_total": sum(saved),
        "control_total": sum(control),
        "saved_median": statistics.median(saved),
        "saved_range": [min(saved), max(saved)],
        "saved_per_case_mean_95pct": [mean_samples[250], mean_samples[9749]],
        "aggregate_ratio_95pct": [ratio_samples[250], ratio_samples[9749]],
        "resamples": RESAMPLES, "seed_hex": hex(SEED),
    }
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main()

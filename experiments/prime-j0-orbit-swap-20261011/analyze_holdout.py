#!/usr/bin/env python3
"""Paired descriptive uncertainty for the frozen swap-cover panel."""

from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import random


HERE = Path(__file__).resolve().parent
SOURCE = HERE / "phase_cost.py"
SPEC = importlib.util.spec_from_file_location("swap_uncertainty_phase", SOURCE)
phase = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(phase)
BOOTSTRAPS = 5000
SEED = 20261011235917


def digest(raw):
    return sha256(raw).hexdigest()


def interval(values):
    ordered = sorted(values)
    return [ordered[int(0.025 * BOOTSTRAPS)],
            ordered[int(0.975 * BOOTSTRAPS) - 1]]


def main():
    raw = (HERE / "holdout-paths.jsonl").read_bytes()
    screen = json.loads((HERE / "holdout-screen.json").read_bytes())
    assert digest(raw) == screen["certificate_sha256"]
    terminal = phase.TERMINAL.read_bytes()
    differences = []
    for line in raw.splitlines():
        row = json.loads(line)
        old, new = row["priority"], row["swapped"]
        _, old_rotations = phase.phases(old, terminal)
        _, new_rotations = phase.phases(new, terminal)
        differences.append((int(old["rho_terms"] > 0) -
                            int(new["rho_terms"] > 0),
                            old["rho_terms"] - new["rho_terms"],
                            old_rotations - new_rotations))
    assert len(differences) == screen["cases"] == 4096
    totals = [sum(row[column] for row in differences) for column in range(3)]
    assert totals[:2] == [screen["priority"]["active_rho"] -
                          screen["swapped"]["active_rho"],
                          screen["priority"]["rho_terms"] -
                          screen["swapped"]["rho_terms"]]
    phase_result = json.loads((HERE / "phase-cost.json").read_bytes())
    assert totals[2] == phase_result["priority"]["gauge_rotations"] - \
        phase_result["swapped"]["gauge_rotations"]
    rng = random.Random(SEED)
    draws = [[], [], []]
    for _ in range(BOOTSTRAPS):
        sums = [0, 0, 0]
        for _ in range(len(differences)):
            row = differences[rng.randrange(len(differences))]
            for column in range(3):
                sums[column] += row[column]
        for column in range(3):
            draws[column].append(sums[column] / len(differences))
    names = ("rho_activation", "rho_digits", "gauge_rotations")
    result = {"schema": 1, "status": "descriptive_paired_bootstrap",
              "cases": len(differences), "resamples": BOOTSTRAPS, "seed": SEED,
              "saved_total": dict(zip(names, totals)),
              "saved_mean_per_scalar": dict(zip(
                  names, [value / len(differences) for value in totals])),
              "mean_95pct_interval": dict(zip(
                  names, [interval(values) for values in draws])),
              "certificate_sha256": digest(raw),
              "source_sha256": digest(Path(__file__).read_bytes())}
    (HERE / "paired-analysis.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
